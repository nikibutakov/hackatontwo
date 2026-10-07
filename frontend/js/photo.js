// ============================================================
// РОЛЬ: Frontend-разработчик
// ЧТО ЗДЕСЬ: вкладка «Фото» — выбор/перетаскивание файла,
// отправка на /api/analyze, отрисовка результата и таблицы,
// вердикт-бейдж с разбором по классам.
//
// КАК РАБОТАЕТ:
//   - картинка декодируется параллельно с запросом к API;
//   - каждый запуск анализа получает номер (requestId): если пользователь
//     успел выбрать новый файл, ответ по старому выбрасывается;
//   - наведение на строку таблицы перерисовывает canvas с выделенной
//     детекцией (остальные приглушены);
//   - блок «Проверка по ТЗ» — чек-лист по пунктам задания 4 из
//     result.tz_checklist (состояния считает бэкенд, см. verdict.py);
//   - «Примеры» — миниатюры картинок из папки examples/ (GET /api/examples);
//     клик скачивает картинку и прогоняет её через тот же analyzeFile.
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
  const verdictDefects = document.getElementById("photo-verdict-defects");
  const tbody = document.getElementById("photo-detections-body");
  const metaLine = document.getElementById("photo-meta");
  const tzBox = document.getElementById("photo-tz");
  const tzList = document.getElementById("photo-tz-list");
  const examplesBox = document.getElementById("photo-examples");
  const examplesList = document.getElementById("photo-examples-list");

  const STATUS_TEXT = { ok: "ГОДЕН", warning: "ПРЕДУПРЕЖДЕНИЕ", reject: "БРАК" };
  // Значок и подпись состояния пункта ТЗ
  const TZ_STATE = {
    reject:      { icon: "✖", text: "найдено" },
    warning:     { icon: "!", text: "на проверку" },
    clear:       { icon: "✓", text: "не найдено" },
    not_checked: { icon: "—", text: "не проверяется" },
  };
  const MAX_CANVAS_WIDTH = 900;

  let requestId = 0;      // номер последнего запуска анализа
  let current = null;     // { img, result, scale } — что сейчас на экране

  /** Декодирует файл в <img>; blob-URL освобождается сразу после загрузки. */
  function loadImage(file) {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
      img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("не удалось открыть изображение")); };
      img.src = url;
    });
  }

  function setBusy(busy) {
    dropzone.classList.toggle("dropzone--busy", busy);
  }

  async function analyzeFile(file) {
    const myRequest = ++requestId;
    emptyHint.hidden = true;
    metaLine.textContent = "Анализирую…";
    setBusy(true);
    try {
      // запрос и декодирование картинки идут параллельно
      const [result, img] = await Promise.all([apiAnalyzeImage(file), loadImage(file)]);
      if (myRequest !== requestId) return; // уже выбрали другой файл
      showResult(img, result);
    } catch (err) {
      if (myRequest !== requestId) return;
      current = null;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      emptyHint.hidden = false;
      verdictBox.className = "verdict verdict--hidden";
      tzBox.hidden = true;
      tbody.innerHTML = "";
      metaLine.textContent = "Ошибка: " + err.message;
    } finally {
      if (myRequest === requestId) setBusy(false);
    }
  }

  /** Рисует картинку и детекции; highlight — индекс выделенной детекции. */
  function render(highlight = null) {
    if (!current) return;
    ctx.drawImage(current.img, 0, 0, canvas.width, canvas.height);
    // детекции приходят в координатах оригинала — масштабируем
    drawDetections(ctx, current.result.detections, current.scale, { highlight });
  }

  function showResult(img, result) {
    // вписываем изображение в canvas (максимум MAX_CANVAS_WIDTH по ширине)
    const scale = Math.min(1, MAX_CANVAS_WIDTH / img.width);
    canvas.width = Math.round(img.width * scale);
    canvas.height = Math.round(img.height * scale);
    current = { img, result, scale };
    render();

    renderVerdict(result.verdict);
    renderTzChecklist(result.tz_checklist || []);
    renderTable(result.detections);

    metaLine.textContent =
      `Модель: ${result.model} · инференс ${result.time_ms} мс · ` +
      `размер ${result.image_size.width}×${result.image_size.height}`;
  }

  function renderVerdict(verdict) {
    verdictBox.className = "verdict verdict--" + verdict.status;
    verdictStatus.textContent = STATUS_TEXT[verdict.status] || verdict.status;
    verdictReason.textContent = verdict.reason;

    // разбор по классам: точка статуса, название, количество, площадь
    verdictDefects.innerHTML = (verdict.defects || []).map((g) => {
      const parts = [`×${g.count}`];
      if (g.area_pct !== null && g.area_pct !== undefined) parts.push(`${String(g.area_pct).replace(".", ",")}% площади`);
      return `<li class="verdict__defect verdict__defect--${escapeHtml(g.status)}">
                <span class="verdict__defect-dot"></span>
                <span>${escapeHtml(g.label)}</span>
                <span class="verdict__defect-meta">${parts.join(" · ")}</span>
              </li>`;
    }).join("");
  }

  /** Чек-лист по пунктам ТЗ: значок состояния, формулировка, что найдено / пояснение. */
  function renderTzChecklist(items) {
    tzBox.hidden = items.length === 0;
    tzList.innerHTML = items.map((item) => {
      const state = TZ_STATE[item.state] || { icon: "?", text: item.state };
      const details = item.found.length
        ? item.found.map(escapeHtml).join("; ")
        : state.text;
      const note = item.note ? `<div class="tz__note">${escapeHtml(item.note)}</div>` : "";
      return `<li class="tz__item tz__item--${escapeHtml(item.state)}">
                <span class="tz__icon" title="${escapeHtml(state.text)}">${state.icon}</span>
                <div class="tz__body">
                  <div class="tz__name">${escapeHtml(item.title)}</div>
                  <div class="tz__details">${details}</div>
                  ${note}
                </div>
              </li>`;
    }).join("");
  }

  function renderTable(detections) {
    tbody.innerHTML = "";
    if (detections.length === 0) {
      tbody.innerHTML = `<tr><td colspan="3" style="color:var(--muted)">Дефектов не найдено</td></tr>`;
      return;
    }
    detections.forEach((det, index) => {
      const tr = document.createElement("tr");
      tr.className = "detections-table__row";
      tr.innerHTML = `
        <td><span style="color:${classColor(det.class_name)}">●</span> ${escapeHtml(classLabel(det.class_name))}</td>
        <td>${(det.confidence * 100).toFixed(1)}%</td>
        <td>${det.bbox.map((v) => v.toFixed(0)).join(", ")}</td>`;
      // наведение на строку — выделить детекцию на картинке
      tr.addEventListener("mouseenter", () => render(index));
      tr.addEventListener("mouseleave", () => render());
      tbody.appendChild(tr);
    });
  }

  // ---- примеры из папки examples/ ----
  async function loadExamples() {
    let examples = [];
    try {
      examples = await apiGetExamples();
    } catch (_) { /* нет примеров или API недоступен — блок просто не показываем */ }
    examplesBox.hidden = examples.length === 0;
    examplesList.innerHTML = "";
    for (const ex of examples) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "example";
      button.title = `Проанализировать ${ex.name} (${ex.size_kb} КБ)`;
      button.innerHTML = `<img src="${exampleUrl(ex.name)}" alt="" loading="lazy">
                          <span>${escapeHtml(ex.name)}</span>`;
      button.addEventListener("click", () => analyzeExample(ex.name));
      examplesList.appendChild(button);
    }
  }

  async function analyzeExample(name) {
    try {
      const response = await fetch(exampleUrl(name));
      if (!response.ok) throw new Error(response.status + " " + response.statusText);
      const blob = await response.blob();
      // тот же путь, что у файла с диска: File с именем -> analyzeFile
      await analyzeFile(new File([blob], name, { type: blob.type }));
    } catch (err) {
      showToast(`Не удалось загрузить пример ${name}: ${err.message}`, "error");
    }
  }

  // ---- события ----
  fileInput.addEventListener("change", () => {
    if (fileInput.files.length) analyzeFile(fileInput.files[0]);
    fileInput.value = ""; // повторный выбор того же файла тоже запустит анализ
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

  loadExamples();

  return { analyzeFile, loadExamples };
})();
