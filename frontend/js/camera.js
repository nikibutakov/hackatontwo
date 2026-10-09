// ============================================================
// РОЛЬ: Frontend-разработчик — ЭТО ГЛАВНАЯ ФИШКА ДЕМО, файл важный
// ЧТО ЗДЕСЬ: вкладка «Живая камера»:
//   источник (камера или видео-файл) -> скрытый <video>
//   цикл: центр кадра (цифровой зум) -> offscreen canvas размером с вход
//         модели (imgsz) -> JPEG -> POST /api/frame
//         -> детекции рисуются поверх видео на видимом canvas
//   Отрисовка видео идёт на requestAnimationFrame (гладко, 30-60 FPS),
//   отправка кадров — цикл "ответил -> шлю следующий"; если сеть медленнее
//   модели, включается второй такой цикл (см. PIPELINE_*).
//   Счётчик показывает FPS и разбивку "модель X мс · сеть Y мс" —
//   по ней видно, что тормозит: сервер или канал (Tailscale).
//
// ЗУМ: модели уходит только центр кадра в полном разрешении камеры, и на
// экране показан ровно он. Без зума плата занимает часть кадра, а после
// сжатия до imgsz мелкие дефекты становятся 3–5 пикселями — модель их не видит.
//
// ИСТОЧНИКИ:
//   - камера (getUserMedia), с выбором устройства, если их несколько;
//   - видео-файл (запасной офлайн-режим): тот же пайплайн, ролик крутится
//     по кругу. Работает и без HTTPS — камера для него не нужна.
//
// СЕССИИ: каждый запуск получает номер (session). Циклы и ответы API
// "старой" сессии, долетевшие после остановки/смены источника,
// игнорируются — иначе на новом видео мелькали бы рамки от старого.
//
// ВАЖНО ПРО HTTPS: getUserMedia работает ТОЛЬКО на https:// или
// http://localhost. Если страница открыта по http://100.x.x.x:8000 —
// камера заблокируется. Решения — docs/ARCHITECTURE.md, раздел
// «Удалённый сервер и камера».
//
// ЧТО СДЕЛАТЬ (TODO):
// 1. Проверить FPS на целевом ноутбуке (счётчик уже есть).
// ============================================================

const cameraTab = (() => {
  const video = document.getElementById("camera-video");
  const canvas = document.getElementById("camera-canvas");
  const ctx = canvas.getContext("2d");
  const emptyHint = document.getElementById("camera-empty-hint");
  const startBtn = document.getElementById("camera-start");
  const stopBtn = document.getElementById("camera-stop");
  const deviceSelect = document.getElementById("camera-device");
  const fileInput = document.getElementById("camera-video-file");
  const statusEl = document.getElementById("camera-status");
  const fpsEl = document.getElementById("camera-fps");
  const warningEl = document.getElementById("camera-warning");
  const zoomSelect = document.getElementById("camera-zoom");
  const confSelect = document.getElementById("camera-conf");
  const snapshotBtn = document.getElementById("camera-snapshot");

  // offscreen-canvas: сюда снимается кадр для отправки
  const offscreen = document.createElement("canvas");
  const offCtx = offscreen.getContext("2d");

  // Размер отправляемого кадра = размер входа АКТИВНОЙ модели (imgsz из
  // /api/models): кадр крупнее сервер всё равно сожмёт, а лишние пиксели
  // только нагружают сеть. Раньше слали всегда 960 — для модели на 640
  // это больше половины впустую потраченного трафика через Tailscale.
  let modelInputSize = 640;

  // Второй кадр "в пути" — ТОЛЬКО когда тормозит сеть, а не модель.
  // Замер (сервер на CPU, модель ~240 мс): 1 в пути — 4,0 FPS, 2 в пути —
  // 2,6 FPS: параллельные запросы мешают друг другу на процессоре. Если же
  // сеть (Tailscale) медленнее модели, второй кадр едет по сети, пока сервер
  // считает первый. Поэтому стартуем с одного, а второй отправитель
  // включается сам, когда после разгона сеть стабильно дольше модели.
  const PIPELINE_WARMUP = 15;      // кадров замера до решения
  const PIPELINE_RATIO = 1.2;      // сеть дольше модели в столько раз -> включить
  const JPEG_QUALITY = 0.75;
  let pipelined = false;
  let measuredFrames = 0;         // кадров замера в текущем запуске

  let running = false;
  let session = 0;               // номер текущего запуска (см. шапку)
  let stream = null;             // MediaStream камеры
  let videoUrl = null;           // blob:-URL видео-файла (освобождаем при остановке)
  let sourceLabel = "";          // "Камера" / "Видео: name.mp4" — для статуса
  // Последний ответ API ВМЕСТЕ с шириной кадра, по которому он посчитан:
  // координаты детекций — в пикселях отправленного кадра, и масштаб
  // нужно брать от него, а не от текущего offscreen (тот мог измениться).
  let lastResult = null;         // { detections, sentWidth, zoom }
  // Номера кадров: при двух отправителях ответы могут прийти не по порядку —
  // более старый ответ не должен затереть более свежий
  let frameSeq = 0;
  let appliedSeq = 0;
  let arrivals = [];             // время прихода ответов — для FPS
  let timings = [];              // [полное время, время модели] — разбивка сеть/модель

  /** Текущий зум и прямоугольник центра кадра, который видит модель. */
  function currentCrop() {
    const zoom = Number(zoomSelect.value) || 1;
    const w = video.videoWidth / zoom;
    const h = video.videoHeight / zoom;
    return { zoom, x: (video.videoWidth - w) / 2, y: (video.videoHeight - h) / 2, w, h };
  }

  /** Узнать imgsz активной модели (при старте потока и после смены модели). */
  async function refreshModelInfo() {
    try {
      const active = (await apiGetModels()).find((m) => m.active);
      if (active && active.imgsz) modelInputSize = active.imgsz;
    } catch (_) { /* API недоступен — останется прежнее значение */ }
  }

  function warn(text) {
    warningEl.hidden = false;
    warningEl.textContent = text;
  }

  function isRunning() {
    return running;
  }

  // ---------- Источник: камера ----------
  async function startCamera() {
    warningEl.hidden = true;

    // Проверка secure context — самая частая причина «камера не работает»
    if (!window.isSecureContext) {
      warn("Камера доступна только на https:// или http://localhost. " +
           "Откройте страницу по localhost или через tailscale serve / Cloudflare Tunnel " +
           "(docs/ARCHITECTURE.md). Видео-файл работает и так.");
      return;
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      warn("Браузер не поддерживает getUserMedia. Используйте режим «Видео-файл».");
      return;
    }

    stop();
    // Просим максимум, что даст камера: при зуме 2× из 1920×1080 модели уходит
    // центр 960×540 в родном разрешении, а не растянутые пиксели. Сеть это
    // не нагружает — отправляется только центр, сжатый до imgsz модели.
    const videoConstraints = { width: { ideal: 1920 }, height: { ideal: 1080 } };
    if (deviceSelect.value) videoConstraints.deviceId = { exact: deviceSelect.value };

    let newStream;
    try {
      newStream = await navigator.mediaDevices.getUserMedia({ video: videoConstraints, audio: false });
    } catch (err) {
      warn("Не удалось получить доступ к камере: " + err.message +
           " (проверьте разрешения браузера)");
      return;
    }

    stream = newStream;
    video.loop = false;
    video.srcObject = stream;
    await begin("Камера");
    // Названия устройств доступны только после разрешения — заполняем список сейчас
    await fillDeviceList(stream.getVideoTracks()[0]?.getSettings().deviceId);
  }

  async function fillDeviceList(activeId) {
    let devices = [];
    try {
      devices = (await navigator.mediaDevices.enumerateDevices())
        .filter((d) => d.kind === "videoinput");
    } catch (_) { /* нет доступа к списку — просто не показываем выбор */ }

    deviceSelect.innerHTML = "";
    devices.forEach((d, i) => {
      const option = document.createElement("option");
      option.value = d.deviceId;
      option.textContent = d.label || `Камера ${i + 1}`;
      option.selected = d.deviceId === activeId;
      deviceSelect.appendChild(option);
    });
    // выбор нужен, только если камер больше одной
    deviceSelect.hidden = devices.length < 2;
  }

  // ---------- Источник: видео-файл (офлайн-фолбэк) ----------
  async function startFile(file) {
    warningEl.hidden = true;
    stop();
    videoUrl = URL.createObjectURL(file);
    video.srcObject = null;
    video.src = videoUrl;
    video.loop = true;   // ролик крутится по кругу, пока не нажмут «Остановить»
    await begin("Видео: " + file.name);
  }

  // ---------- Общий запуск/остановка ----------
  async function begin(label) {
    const mySession = ++session;
    try {
      await video.play();
    } catch (err) {
      warn("Не удалось воспроизвести источник: " + err.message);
      stop();
      return;
    }
    // размеры видео известны только после загрузки метаданных
    if (!video.videoWidth) {
      await new Promise((resolve) => video.addEventListener("loadedmetadata", resolve, { once: true }));
    }
    if (mySession !== session) return; // пока ждали, источник уже сменили

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    await refreshModelInfo();
    if (mySession !== session) return;

    running = true;
    sourceLabel = label;
    lastResult = null;
    frameSeq = 0;
    appliedSeq = 0;
    arrivals = [];
    timings = [];
    emptyHint.hidden = true;
    startBtn.disabled = true;
    stopBtn.disabled = false;
    snapshotBtn.disabled = false;
    statusEl.textContent = sourceLabel + " · поток запущен";

    requestAnimationFrame(() => drawLoop(mySession));  // отрисовка (гладкая)
    pipelined = false;
    measuredFrames = 0;
    sendLoop(mySession);   // второй отправитель — по решению maybePipeline()
  }

  function stop() {
    session++;                // все циклы и запросы старой сессии станут "чужими"
    running = false;
    if (stream) stream.getTracks().forEach((t) => t.stop());
    stream = null;
    video.pause();
    video.srcObject = null;
    video.removeAttribute("src");
    video.load();             // отпускает файл/камеру у <video>
    if (videoUrl) URL.revokeObjectURL(videoUrl);
    videoUrl = null;
    lastResult = null;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    emptyHint.hidden = false;
    startBtn.disabled = false;
    stopBtn.disabled = true;
    snapshotBtn.disabled = true;
    statusEl.textContent = "Поток остановлен";
    fpsEl.textContent = "";
  }

  // Гладкая отрисовка: на экране — ровно тот участок, что видит модель
  // (при зуме — центр кадра), плюс последний результат детекции
  function drawLoop(mySession) {
    if (!running || mySession !== session) return;
    const crop = currentCrop();
    ctx.drawImage(video, crop.x, crop.y, crop.w, crop.h, 0, 0, canvas.width, canvas.height);
    // ответ, посчитанный при другом зуме, к текущей картинке не подходит
    if (lastResult && lastResult.zoom === crop.zoom) {
      // детекции в координатах отправленного (сжатого) кадра -> к размеру canvas
      drawDetections(ctx, lastResult.detections, canvas.width / lastResult.sentWidth);
    }
    requestAnimationFrame(() => drawLoop(mySession));
  }

  /** Среднее по последним замерам: i=0 — полное время запроса, i=1 — время модели. */
  function avgOf(i) {
    return timings.reduce((s, t) => s + t[i], 0) / timings.length;
  }

  /** Включить второго отправителя, если после разгона сеть стабильно дольше модели.
   *  Решение одно на запуск потока: с двумя отправителями "сеть" в замере
   *  включает и очередь на сервере, по ней обратно выключать нельзя. */
  function maybePipeline(avgTotal, avgModel) {
    if (pipelined || timings.length < PIPELINE_WARMUP - 3 || ++measuredFrames < PIPELINE_WARMUP) return;
    if (avgTotal - avgModel > avgModel * PIPELINE_RATIO) {
      pipelined = true;
      sendLoop(session);
    }
  }

  function updateStats(totalMs, modelMs) {
    const now = performance.now();
    arrivals.push(now);
    if (arrivals.length > 12) arrivals.shift();
    timings.push([totalMs, modelMs]);
    if (timings.length > 12) timings.shift();
    if (arrivals.length < 2) return;
    const avgTotal = avgOf(0);
    const avgModel = avgOf(1);
    maybePipeline(avgTotal, avgModel);
    // FPS по фактическому темпу прихода ответов (с двумя отправителями он выше 1/время_запроса)
    const fps = (arrivals.length - 1) * 1000 / (arrivals[arrivals.length - 1] - arrivals[0]);
    // "сеть" = всё, кроме работы модели: загрузка кадра, очередь, ответ.
    // Если модель > 150 мс — упираемся в процессор/видеокарту сервера, а не в сеть.
    fpsEl.textContent = `${fps.toFixed(1)} FPS · модель ${Math.round(avgModel)} мс · ` +
                        `сеть ${Math.round(Math.max(0, avgTotal - avgModel))} мс` +
                        (pipelined ? " · 2 кадра в пути" : "");
  }

  // Отправка: каждый отправитель шлёт следующий кадр только после ответа на свой
  async function sendLoop(mySession) {
    while (running && mySession === session) {
      const t0 = performance.now();
      try {
        const crop = currentCrop();
        // кадр сжимается до входа модели по длинной стороне (как делает YOLO);
        // маленький не растягиваем
        const scale = Math.min(1, modelInputSize / Math.max(crop.w, crop.h));
        const sentWidth = Math.round(crop.w * scale);
        offscreen.width = sentWidth;
        offscreen.height = Math.round(crop.h * scale);
        offCtx.drawImage(video, crop.x, crop.y, crop.w, crop.h, 0, 0, offscreen.width, offscreen.height);
        const seq = ++frameSeq;

        const blob = await new Promise((resolve) =>
          offscreen.toBlob(resolve, "image/jpeg", JPEG_QUALITY));

        const result = await apiPostFrame(blob, confSelect.value || null);
        if (mySession !== session) return; // ответ пришёл уже после остановки
        updateStats(performance.now() - t0, result.time_ms);
        if (seq > appliedSeq) {           // более старый ответ не затирает свежий
          appliedSeq = seq;
          lastResult = { detections: result.detections, sentWidth, zoom: crop.zoom };
        }
        statusEl.textContent = sourceLabel + " · поток запущен";
      } catch (err) {
        if (mySession !== session) return;
        statusEl.textContent = "Ошибка потока: " + err.message + " · повтор через 1 с";
        await new Promise((r) => setTimeout(r, 1000)); // пауза перед повтором
      }
    }
  }

  // ---------- События ----------
  startBtn.addEventListener("click", startCamera);
  stopBtn.addEventListener("click", stop);
  // смена камеры на лету — перезапуск с новым устройством
  deviceSelect.addEventListener("change", () => {
    if (stream) startCamera();
  });
  fileInput.addEventListener("change", () => {
    if (fileInput.files.length) startFile(fileInput.files[0]);
    fileInput.value = ""; // чтобы повторный выбор того же файла тоже срабатывал
  });

  // Стоп-кадр: текущий участок кадра (с учётом зума) в ПОЛНОМ разрешении
  // камеры уходит на вкладку «Фото» — полный анализ без сглаживания, с тем
  // же порогом. Видно каждую детекцию и её уверенность: так проверяется,
  // видит ли модель дефект на живом кадре в принципе.
  async function snapshot() {
    if (!running) return;
    const crop = currentCrop();
    const shot = document.createElement("canvas");
    shot.width = Math.round(crop.w);
    shot.height = Math.round(crop.h);
    shot.getContext("2d").drawImage(video, crop.x, crop.y, crop.w, crop.h, 0, 0, shot.width, shot.height);
    const blob = await new Promise((resolve) => shot.toBlob(resolve, "image/jpeg", 0.92));
    const file = new File([blob], "stop-kadr.jpg", { type: "image/jpeg" });
    const conf = confSelect.value || null;
    document.querySelector('.tab[data-tab="photo"]').click();  // уход с вкладки остановит поток
    photoTab.analyzeFile(file, conf);
  }

  // смена зума: старые рамки к новой картинке не подходят
  zoomSelect.addEventListener("change", () => { lastResult = null; });
  snapshotBtn.addEventListener("click", snapshot);

  return { startCamera, startFile, stop, isRunning, refreshModelInfo };
})();
