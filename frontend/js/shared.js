// ============================================================
// РОЛЬ: Frontend-разработчик
// ЧТО ЗДЕСЬ: общие помощники для вкладок «Фото» и «Камера»:
// цвета классов, отрисовка детекций на canvas, уведомления (toast),
// экранирование HTML.
//
// ЧТО СДЕЛАТЬ (TODO):
// 1. Подобрать цвета классов под финальный список (оба набора классов:
//    бейзлайн HF и своя модель на DeepPCB — уже назначены ниже).
// 2. Отрисовка меток: можно лучше — скруглённые плашки, счётчики
//    у повторяющихся классов.
// ============================================================

// Фиксированный цвет на класс — чтобы цвет был стабилен между кадрами
const CLASS_COLORS = {
  // бейзлайн с HF
  dry_joint: "#ff5252",
  short_circuit: "#ffb300",
  incorrect_installation: "#7c4dff",
  pcb_damage: "#00bfa5",
  // своя модель на DeepPCB
  open_circuit: "#ff1744",
  missing_hole: "#2979ff",
  spurious_copper: "#ff9100",
  mouse_bite: "#f50057",
  spur: "#c6ff00",
  short: "#ffb300",   // = short_circuit: тот же дефект, другое имя в разметке DeepPCB
};

// КОРОТКИЕ русские подписи — для меток на canvas и таблицы детекций, где
// длинные не помещаются. Полные названия приходят с бэкенда готовыми
// (verdict.defects[].label из backend/app/verdict.py). Новый класс — добавьте и сюда.
const RU_LABELS = {
  dry_joint: "непропай",
  short_circuit: "короткое замыкание",
  incorrect_installation: "неправ. установка",
  pcb_damage: "повреждение платы",
  open_circuit: "разрыв дорожки",
  missing_hole: "нет отверстия",
  spurious_copper: "лишняя медь",
  mouse_bite: "мышиный укус",
  spur: "заусенец",
  short: "короткое замыкание",
};

function classColor(name) {
  if (CLASS_COLORS[name]) return CLASS_COLORS[name];
  // неизвестный класс: детерминированный цвет из хэша имени
  let hash = 0;
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return `hsl(${hash % 360}, 85%, 60%)`;
}

function classLabel(name) {
  return RU_LABELS[name] || name;
}

/**
 * Рисует детекции на canvas поверх изображения.
 * detections — массив из ответа API; scale — множитель координат
 * (детекции приходят в координатах ОТПРАВЛЕННОГО кадра, а canvas
 * может быть другого размера).
 */
function drawDetections(ctx, detections, scale = 1, options = {}) {
  // highlight — индекс детекции, которую выделить (наведение на строку
  // таблицы); остальные при этом приглушаются.
  const { highlight = null } = options;

  // canvas часто показан уменьшенным (1280px кадр в колонке ~700px).
  // px — сколько пикселей canvas приходится на 1 экранный пиксель, чтобы
  // линии и подписи выглядели одинаково крупно при любом размере (проектор!).
  const px = ctx.canvas.clientWidth ? ctx.canvas.width / ctx.canvas.clientWidth : 1;
  const fontSize = Math.round(15 * px);

  detections.forEach((det, index) => {
    const color = classColor(det.class_name);
    const isHighlighted = highlight === index;
    const dimmed = highlight !== null && !isHighlighted;
    const [x1, y1, x2, y2] = det.bbox.map((v) => v * scale);
    const label = `${classLabel(det.class_name)} ${(det.confidence * 100).toFixed(0)}%`;

    ctx.save();
    ctx.globalAlpha = dimmed ? 0.35 : 1;
    ctx.strokeStyle = color;
    ctx.lineWidth = (isHighlighted ? 4 : 2) * px;

    // маска (полигон), если модель сегментационная
    if (det.polygon && det.polygon.length > 2) {
      ctx.beginPath();
      det.polygon.forEach((p, i) => {
        const pointX = p.x !== undefined ? p.x : p[0];
        const pointY = p.y !== undefined ? p.y : p[1];
        i === 0 ? ctx.moveTo(pointX * scale, pointY * scale) : ctx.lineTo(pointX * scale, pointY * scale);
      });
      ctx.closePath();
      // Полупрозрачность через globalAlpha, а не дописыванием "55" к цвету:
      // у неизвестных классов цвет в формате hsl(...), и "hsl(...)55" —
      // невалидный цвет, заливка молча бралась от предыдущей детекции.
      ctx.save();
      ctx.globalAlpha *= isHighlighted ? 0.5 : 0.33;
      ctx.fillStyle = color;
      ctx.fill();
      ctx.restore();
      ctx.stroke();
    } else {
      // рамка для моделей детекции
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
    }

    // подпись: над рамкой, а если рамка у верхнего края — внутри неё
    ctx.font = `${fontSize}px 'Segoe UI', sans-serif`;
    const padding = Math.round(5 * px);
    const boxHeight = fontSize + padding * 2;
    const textWidth = ctx.measureText(label).width;
    const boxY = y1 - boxHeight >= 0 ? y1 - boxHeight : y1;
    ctx.fillStyle = "#000c";
    ctx.fillRect(x1, boxY, textWidth + padding * 2, boxHeight);
    ctx.fillStyle = color;
    ctx.textBaseline = "middle";
    ctx.fillText(label, x1 + padding, boxY + boxHeight / 2);
    ctx.restore();
  });
}

/**
 * Всплывающее уведомление вместо alert(): не блокирует страницу
 * (alert останавливал бы и поток камеры), само исчезает.
 * kind: "info" | "ok" | "error".
 */
function showToast(text, kind = "info", timeoutMs = 4000) {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = "toast toast--" + kind;
  toast.textContent = text;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), timeoutMs);
}

/** Экранирование строки для вставки в innerHTML (имена классов, тексты с сервера). */
function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (ch) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}
