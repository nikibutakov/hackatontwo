// ============================================================
// РОЛЬ: Frontend-разработчик
// ЧТО ЗДЕСЬ: общие помощники для вкладок «Фото» и «Камера»:
// цвета классов и отрисовка детекций на canvas.
//
// ЧТО СДЕЛАТЬ (TODO):
// 1. Подобрать цвета классов под финальный список (оба набора классов:
//    бейзлайн HF и своя модель на DeepPCB — уже назначены ниже).
// 2. Отрисовка меток: сейчас текст с чёрной подложкой. Можно лучше —
//    скруглённые плашки, счётчики у повторяющихся классов.
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
};

// Русские подписи классов (дублируют backend/app/verdict.py — держите синхронно!)
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
function drawDetections(ctx, detections, scale = 1) {
  for (const det of detections) {
    const color = classColor(det.class_name);
    const [x1, y1, x2, y2] = det.bbox.map((v) => v * scale);
    const label = `${classLabel(det.class_name)} ${(det.confidence * 100).toFixed(0)}%`;

    // маска (полигон), если модель сегментационная
    if (det.polygon && det.polygon.length > 2) {
      ctx.beginPath();
      det.polygon.forEach((p, i) => {
        const px = p.x !== undefined ? p.x : p[0];
        const py = p.y !== undefined ? p.y : p[1];
        i === 0 ? ctx.moveTo(px * scale, py * scale) : ctx.lineTo(px * scale, py * scale);
      });
      ctx.closePath();
      ctx.fillStyle = color + "55"; // полупрозрачная заливка
      ctx.fill();
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.stroke();
    } else {
      // рамка для моделей детекции
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
    }

    // подпись
    ctx.font = "14px 'Segoe UI', sans-serif";
    const textWidth = ctx.measureText(label).width;
    ctx.fillStyle = "#000c";
    ctx.fillRect(x1, y1 - 20, textWidth + 10, 20);
    ctx.fillStyle = color;
    ctx.fillText(label, x1 + 5, y1 - 6);
  }
}
