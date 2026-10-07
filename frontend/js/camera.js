// ============================================================
// РОЛЬ: Frontend-разработчик — ЭТО ГЛАВНАЯ ФИШКА ДЕМО, файл важный
// ЧТО ЗДЕСЬ: вкладка «Живая камера»:
//   getUserMedia -> скрытый <video>
//   цикл: кадр видео -> offscreen canvas 640px -> JPEG -> POST /api/frame
//         -> детекции рисуются поверх видео на видимом canvas
//   Отрисовка видео идёт на requestAnimationFrame (гладко, 30-60 FPS),
//   отправка кадров — отдельным циклом "ответил -> шлю следующий"
//   (обычно 4-10 FPS, зависит от скорости модели).
//
// ВАЖНО ПРО HTTPS: getUserMedia работает ТОЛЬКО на https:// или
// http://localhost. Если страница открыта по http://100.x.x.x:8000 —
// камера заблокируется. Решения — docs/ARCHITECTURE.md, раздел
// «Удалённый сервер и камера».
//
// ЧТО СДЕЛАТЬ (TODO):
// 1. Проверить FPS на целевом ноутбуке (счётчик уже есть).
// 2. Добавить выбор камеры (facingMode/deviceId), если на демо-ноутбуке
//    их две — фронтальная и внешняя.
// 3. Режим «видео-файл» как запасной: <input type="file" accept="video/*">,
//    тот же цикл, но источник — <video> с локальным роликом. Это офлайн-фолбэк.
// ============================================================

const cameraTab = (() => {
  const video = document.getElementById("camera-video");
  const canvas = document.getElementById("camera-canvas");
  const ctx = canvas.getContext("2d");
  const emptyHint = document.getElementById("camera-empty-hint");
  const startBtn = document.getElementById("camera-start");
  const stopBtn = document.getElementById("camera-stop");
  const statusEl = document.getElementById("camera-status");
  const fpsEl = document.getElementById("camera-fps");
  const warningEl = document.getElementById("camera-warning");

  // offscreen-canvas: сюда снимается кадр для отправки (сжатие до 640px)
  const offscreen = document.createElement("canvas");
  const offCtx = offscreen.getContext("2d");

  let running = false;
  let stream = null;
  let lastDetections = [];       // последний ответ API
  let lastFrameTimes = [];       // кольцевой буфер для подсчёта FPS
  const SEND_MAX_WIDTH = 640;    // ширина отправляемого кадра

  function warn(text) {
    warningEl.hidden = false;
    warningEl.textContent = text;
  }

  async function start() {
    warningEl.hidden = true;

    // Проверка secure context — самая частая причина «камера не работает»
    if (!window.isSecureContext) {
      warn("Камера доступна только на https:// или http://localhost. " +
           "Откройте страницу по localhost или через tailscale serve / Cloudflare Tunnel " +
           "(docs/ARCHITECTURE.md).");
      return;
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      warn("Браузер не поддерживает getUserMedia.");
      return;
    }

    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      });
    } catch (err) {
      warn("Не удалось получить доступ к камере: " + err.message +
           " (проверьте разрешения браузера)");
      return;
    }

    video.srcObject = stream;
    await video.play();

    // размер видимого canvas = размер видео
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    running = true;
    emptyHint.hidden = true;
    startBtn.disabled = true;
    stopBtn.disabled = false;
    statusEl.textContent = "Поток запущен";

    requestAnimationFrame(drawLoop);  // отрисовка (гладкая)
    sendLoop();                        // отправка кадров (по темпу модели)
  }

  function stop() {
    running = false;
    if (stream) stream.getTracks().forEach((t) => t.stop());
    stream = null;
    lastDetections = [];
    startBtn.disabled = false;
    stopBtn.disabled = true;
    statusEl.textContent = "Камера остановлена";
    fpsEl.textContent = "";
  }

  // Гладкая отрисовка: видео + последний результат детекции
  function drawLoop() {
    if (!running) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    // детекции приходят в координатах отправленного (сжатого) кадра —
    // масштабируем к размеру видимого canvas
    const scale = canvas.width / offscreen.width;
    drawDetections(ctx, lastDetections, scale);
    requestAnimationFrame(drawLoop);
  }

  // Отправка: следующий кадр — только после ответа на предыдущий
  async function sendLoop() {
    while (running) {
      const t0 = performance.now();
      try {
        offscreen.width = SEND_MAX_WIDTH;
        offscreen.height = Math.round(
          video.videoHeight * (SEND_MAX_WIDTH / video.videoWidth));
        offCtx.drawImage(video, 0, 0, offscreen.width, offscreen.height);

        const blob = await new Promise((resolve) =>
          offscreen.toBlob(resolve, "image/jpeg", 0.7));

        const result = await apiPostFrame(blob);
        lastDetections = result.detections;

        // FPS: скользящее среднее по последним кадрам
        const dt = performance.now() - t0;
        lastFrameTimes.push(dt);
        if (lastFrameTimes.length > 10) lastFrameTimes.shift();
        const avg = lastFrameTimes.reduce((a, b) => a + b, 0) / lastFrameTimes.length;
        fpsEl.textContent = (1000 / avg).toFixed(1) + " FPS · инференс " + result.time_ms + " мс";
      } catch (err) {
        statusEl.textContent = "Ошибка потока: " + err.message;
        await new Promise((r) => setTimeout(r, 1000)); // пауза перед повтором
      }
    }
  }

  startBtn.addEventListener("click", start);
  stopBtn.addEventListener("click", stop);

  return { start, stop };
})();
