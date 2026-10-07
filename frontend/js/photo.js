// ============================================================
// РОЛЬ: Frontend-разработчик
// ЧТО ЗДЕСЬ: вкладка «Фото» — выбор/перетаскивание файла,
// отправка на /api/analyze, отрисовка результата и таблицы,
// вердикт-бейдж.
//
// ЧТО СДЕЛАТЬ (TODO):
// 1. Индикатор загрузки на время запроса (крутящаяся точка на кнопке).
// 2. Примеры изображений для быстрого теста: кнопка «Загрузить пример»
//    с картинками из ml/data (удобно для репетиции демо).
// 3. Клик по строке таблицы — подсветить соответствующую детекцию на canvas.
// ============================================================

const photoTab = (() => {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("photo-input");
  const canvas = document.getElementById("photo-canvas");
  const ctx = canvas.getContext("2d");
  const emptyHint = document.getElementById("photo-empty-hint");
  const verdictBox = document.getElementById("photo-verdict");
  const verdictStatus = document.getElementById("photo-verdict-status");
  const verdictReason = document.getElementById("photo-verdict-reason");
  const tbody = document.getElementById("photo-detections-body");
  const metaLine = document.getElementById("photo-meta");

  // Запоминаем масштаб отрисовки, чтобы клики по таблице могли
  // переводить экранные координаты в координаты изображения
  let currentScale = 1;

  async function analyzeFile(file) {
    emptyHint.hidden = true;
    metaLine.textContent = "Анализирую…";
    try {
      const result = await apiAnalyzeImage(file);
      drawResult(file, result);
    } catch (err) {
      metaLine.textContent = "Ошибка: " + err.message;
    }
  }

  function drawResult(file, result) {
    const img = new Image();
    img.onload = () => {
      // вписываем изображение в canvas (максимум 900px по ширине)
      const maxWidth = 900;
      currentScale = Math.min(1, maxWidth / img.width);
      canvas.width = Math.round(img.width * currentScale);
      canvas.height = Math.round(img.height * currentScale);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      // детекции приходят в координатах оригинала — масштабируем
      drawDetections(ctx, result.detections, currentScale);

      // вердикт
      const map = { ok: "ГОДЕН", warning: "ПРЕДУПРЕЖДЕНИЕ", reject: "БРАК" };
      verdictBox.className = "verdict verdict--" + result.verdict.status;
      verdictStatus.textContent = map[result.verdict.status] || result.verdict.status;
      verdictReason.textContent = result.verdict.reason;

      // таблица детекций
      tbody.innerHTML = "";
      for (const det of result.detections) {
        const tr = document.createElement("tr");
        const colorDot = `<span style="color:${classColor(det.class_name)}">●</span>`;
        tr.innerHTML = `
          <td>${colorDot} ${classLabel(det.class_name)}</td>
          <td>${(det.confidence * 100).toFixed(1)}%</td>
          <td>${det.bbox.map((v) => v.toFixed(0)).join(", ")}</td>`;
        tbody.appendChild(tr);
      }
      if (result.detections.length === 0) {
        tbody.innerHTML = `<tr><td colspan="3" style="color:var(--muted)">Дефектов не найдено</td></tr>`;
      }

      metaLine.textContent =
        `Модель: ${result.model} · инференс ${result.time_ms} мс · ` +
        `размер ${result.image_size.width}×${result.image_size.height}`;
    };
    img.src = URL.createObjectURL(file);
  }

  // ---- события ----
  fileInput.addEventListener("change", () => {
    if (fileInput.files.length) analyzeFile(fileInput.files[0]);
  });

  ["dragenter", "dragover"].forEach((ev) =>
    dropzone.addEventListener(ev, (e) => {
      e.preventDefault();
      dropzone.classList.add("dropzone--over");
    }));
  ["dragleave", "drop"].forEach((ev) =>
    dropzone.addEventListener(ev, (e) => {
      e.preventDefault();
      dropzone.classList.remove("dropzone--over");
    }));
  dropzone.addEventListener("drop", (e) => {
    if (e.dataTransfer.files.length) analyzeFile(e.dataTransfer.files[0]);
  });

  return { analyzeFile };
})();
