// ============================================================
// РОЛЬ: Frontend-разработчик — ЭТО ГЛАВНАЯ ФИШКА ДЕМО, файл важный
// ЧТО ЗДЕСЬ: вкладка «Живая камера»:
//   источник (камера или видео-файл) -> скрытый <video>
//   цикл: кадр видео -> offscreen canvas ≤960px -> JPEG -> POST /api/frame
//         -> детекции рисуются поверх видео на видимом canvas
//   Отрисовка видео идёт на requestAnimationFrame (гладко, 30-60 FPS),
//   отправка кадров — отдельным циклом "ответил -> шлю следующий"
//   (обычно 4-10 FPS, зависит от скорости модели).
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

  // offscreen-canvas: сюда снимается кадр для отправки (сжатие до 960px)
  const offscreen = document.createElement("canvas");
  const offCtx = offscreen.getContext("2d");

  // 960 (было 640): наша PKU-модель работает на 960 — кадр 640 терял мелкие
  // дефекты, детекции становились неустойчивыми и мерцали
  const SEND_MAX_WIDTH = 960;    // ширина отправляемого кадра

  let running = false;
  let session = 0;               // номер текущего запуска (см. шапку)
  let stream = null;             // MediaStream камеры
  let videoUrl = null;           // blob:-URL видео-файла (освобождаем при остановке)
  let sourceLabel = "";          // "Камера" / "Видео: name.mp4" — для статуса
  // Последний ответ API ВМЕСТЕ с шириной кадра, по которому он посчитан:
  // координаты детекций — в пикселях отправленного кадра, и масштаб
  // нужно брать от него, а не от текущего offscreen (тот мог измениться).
  let lastResult = null;         // { detections, sentWidth }
  let frameTimes = [];           // для скользящего среднего FPS

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
    const videoConstraints = { width: { ideal: 1280 }, height: { ideal: 720 } };
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

    running = true;
    sourceLabel = label;
    lastResult = null;
    frameTimes = [];
    emptyHint.hidden = true;
    startBtn.disabled = true;
    stopBtn.disabled = false;
    statusEl.textContent = sourceLabel + " · поток запущен";

    requestAnimationFrame(() => drawLoop(mySession));  // отрисовка (гладкая)
    sendLoop(mySession);                                // отправка кадров (по темпу модели)
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
    statusEl.textContent = "Поток остановлен";
    fpsEl.textContent = "";
  }

  // Гладкая отрисовка: видео + последний результат детекции
  function drawLoop(mySession) {
    if (!running || mySession !== session) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    if (lastResult) {
      // детекции в координатах отправленного (сжатого) кадра -> к размеру canvas
      drawDetections(ctx, lastResult.detections, canvas.width / lastResult.sentWidth);
    }
    requestAnimationFrame(() => drawLoop(mySession));
  }

  // Отправка: следующий кадр — только после ответа на предыдущий
  async function sendLoop(mySession) {
    while (running && mySession === session) {
      const t0 = performance.now();
      try {
        // маленькое видео не растягиваем — шлём как есть
        const sentWidth = Math.min(SEND_MAX_WIDTH, video.videoWidth);
        offscreen.width = sentWidth;
        offscreen.height = Math.round(video.videoHeight * (sentWidth / video.videoWidth));
        offCtx.drawImage(video, 0, 0, offscreen.width, offscreen.height);

        const blob = await new Promise((resolve) =>
          offscreen.toBlob(resolve, "image/jpeg", 0.8));

        const result = await apiPostFrame(blob);
        if (mySession !== session) return; // ответ пришёл уже после остановки
        lastResult = { detections: result.detections, sentWidth };
        statusEl.textContent = sourceLabel + " · поток запущен";

        // FPS: скользящее среднее по последним 10 кадрам
        frameTimes.push(performance.now() - t0);
        if (frameTimes.length > 10) frameTimes.shift();
        const avg = frameTimes.reduce((a, b) => a + b, 0) / frameTimes.length;
        fpsEl.textContent = (1000 / avg).toFixed(1) + " FPS · инференс " + result.time_ms + " мс";
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

  return { startCamera, startFile, stop, isRunning };
})();
