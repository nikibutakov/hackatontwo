// Презентация PCB Defect Inspector — хакатон «Осенний Хакатон 2026», задание 4
// Тема: тёмная, в визуальном языке сервиса (тёмно-синий + статусы годен/проверка/брак)
const pptxgen = require("pptxgenjs");

const W = 13.33, H = 7.5, M = 0.6;
const BG = "0F1620", PANEL = "1A2332", PANEL2 = "223046", CODE = "0B1017";
const PRIMARY = "4A9EFF", ACCENT = "2ECC71", WARN = "F39C12", REJECT = "E74C3C";
const TEXT = "E8EDF4", MUTED = "8B98A9", LINE_C = "2C3542";
const FONT = "Segoe UI", MONO = "Consolas";

const p = new pptxgen();
p.layout = "LAYOUT_WIDE";
p.author = "PCB Defect Inspector team";
p.title = "PCB Defect Inspector — сервис контроля качества печатных плат";

const shadow = () => ({ type: "outer", color: "000000", blur: 7, offset: 2, angle: 90, opacity: 0.35 });
const bu = () => ({ code: "2013", indent: 12 });

function base(kicker, title) {
  const s = p.addSlide();
  s.background = { color: BG };
  if (kicker) s.addText(kicker, { x: M, y: 0.42, w: W - 2 * M, h: 0.3, fontFace: FONT, fontSize: 12,
    color: PRIMARY, bold: true, charSpacing: 3, margin: 0 });
  if (title) s.addText(title, { x: M, y: 0.72, w: W - 2 * M, h: 0.62, fontFace: FONT, fontSize: 30,
    color: TEXT, bold: true, margin: 0 });
  return s;
}
function dot(s, x, y, color) {
  s.addShape(p.shapes.OVAL, { x, y, w: 0.16, h: 0.16, fill: { color } });
}
function card(s, x, y, w, h, fill = PANEL) {
  s.addShape(p.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, rectRadius: 0.07,
    line: { color: LINE_C, width: 0.75 }, shadow: shadow() });
}
function arrow(s, x, y, w) {
  s.addShape(p.shapes.LINE, { x, y, w, h: 0, line: { color: PRIMARY, width: 2, endArrowType: "triangle" } });
}
function chip(s, x, y, w, txt) {
  s.addShape(p.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 0.52, fill: { color: PANEL }, rectRadius: 0.26,
    line: { color: LINE_C, width: 0.75 } });
  s.addText(txt, { x, y, w, h: 0.52, fontFace: FONT, fontSize: 14, bold: true, color: ACCENT,
    align: "center", valign: "middle", margin: 0 });
}

// ================= 1. ТИТУЛ =================
{
  const s = base(null, null);
  s.addText("ХАКАТОН «ОСЕННИЙ ХАКАТОН 2026» · ЗАДАНИЕ 4", { x: M, y: 1.35, w: 7.2, h: 0.35,
    fontFace: FONT, fontSize: 13, color: MUTED, bold: true, charSpacing: 3, margin: 0 });
  s.addText("PCB Defect\nInspector", { x: M, y: 1.85, w: 7.2, h: 2.1, fontFace: FONT, fontSize: 60,
    color: TEXT, bold: true, margin: 0, lineSpacingMultiple: 0.98 });
  s.addText("Сервис контроля качества печатных плат\nдля производства", { x: M, y: 4.15, w: 7.0, h: 0.95,
    fontFace: FONT, fontSize: 21, color: PRIMARY, margin: 0, lineSpacingMultiple: 1.1 });
  s.addText("Команда: ML · Backend · Frontend", { x: M, y: 5.2, w: 7.0, h: 0.35,
    fontFace: FONT, fontSize: 14, color: MUTED, margin: 0 });
  chip(s, M, 6.35, 2.35, "45–50 FPS");
  chip(s, M + 2.55, 6.35, 2.6, "10 классов");
  chip(s, M + 5.35, 6.35, 2.15, "6 моделей");

  s.addImage({ path: "slides_build/title_detect.jpg", x: 8.45, y: 0.95, w: 4.28, h: 3.86, shadow: shadow() });
  s.addText("Разрыв дорожки (open_circuit) — детекция нашей моделью, живой скриншот сервиса",
    { x: 8.45, y: 4.95, w: 4.28, h: 0.6, fontFace: FONT, fontSize: 11, color: MUTED, margin: 0 });
  s.addNotes("Задание 4 — сервис определения дефектов печатных плат. Мы сделали его для главного места, где дефекты стоят денег — производства.");
}

// ================= 2. ПРОБЛЕМА =================
{
  const s = base("ПРОБЛЕМА", "Контроль качества плат на производстве");
  const cw = 3.85, ch = 3.7, y0 = 1.75, gap = 0.34;
  const cols = [
    { name: "AOI-комплекс", c: PRIMARY, fill: PANEL, rows: [
      "Эталон отрасли по точности", "Миллионы рублей за линию",
      "Настройка под каждую плату", "Далеко не всем доступен"] },
    { name: "Ручной контроль (ОТК)", c: WARN, fill: PANEL, rows: [
      "Дёшево на старте", "Глаза устают к обеду",
      "Секунды на каждую плату", "Человеческий фактор"] },
    { name: "Наш сервис", c: ACCENT, fill: PANEL2, rows: [
      "Любое рабочее место с камерой", "Вердикт за десятки миллисекунд",
      "24/7, без усталости", "Офисный ПК с одной GPU"] },
  ];
  cols.forEach((col, i) => {
    const x = M + i * (cw + gap);
    card(s, x, y0, cw, ch, col.fill);
    dot(s, x + 0.3, y0 + 0.42, col.c);
    s.addText(col.name, { x: x + 0.58, y: y0 + 0.22, w: cw - 0.8, h: 0.5, fontFace: FONT,
      fontSize: 18, bold: true, color: TEXT, margin: 0 });
    s.addText(col.rows.map((t, j) => ({ text: t, options: { bullet: bu(), breakLine: j < col.rows.length - 1 } })),
      { x: x + 0.3, y: y0 + 0.95, w: cw - 0.6, h: ch - 1.2, fontFace: FONT, fontSize: 14,
        color: MUTED, paraSpaceAfter: 10, margin: 0 });
  });
  s.addText([
    { text: "Ловим дефекты из ТЗ:  ", options: { color: MUTED, bold: false } },
    { text: "разрывы дорожек · непропаи · повреждения компонентов · иные дефекты", options: { color: TEXT, bold: true } },
  ], { x: M, y: 5.85, w: W - 2 * M, h: 0.45, fontFace: FONT, fontSize: 15, margin: 0 });
  s.addNotes("На линии электроники контроль — это ОТК или AOI-комплекс. AOI — миллионы и настройка под плату, поэтому на малых производствах контроль остаётся ручным. Наш сервис — контроль, который ставится на любое рабочее место.");
}

// ================= 3. АРХИТЕКТУРА =================
{
  const s = base("РЕШЕНИЕ", "Как устроено");
  const bw = 2.16, bh = 1.55, y0 = 2.05, gap = 0.32;
  const boxes = [
    ["Фото / камера", "браузер рабочего места"],
    ["Сервис FastAPI", "REST API"],
    ["Модели YOLO ×6", "переключение на лету"],
    ["Вердикт-движок", "годен · проверка · брак"],
    ["Отчёт и чек-лист", "пункты ТЗ в ответе"],
  ];
  boxes.forEach((b, i) => {
    const x = M + i * (bw + gap);
    card(s, x, y0, bw, bh, i === 2 ? PANEL2 : PANEL);
    s.addText(b[0], { x: x + 0.1, y: y0 + 0.28, w: bw - 0.2, h: 0.5, fontFace: FONT, fontSize: 15,
      bold: true, color: TEXT, align: "center", margin: 0 });
    s.addText(b[1], { x: x + 0.1, y: y0 + 0.82, w: bw - 0.2, h: 0.45, fontFace: FONT, fontSize: 11,
      color: MUTED, align: "center", margin: 0 });
    if (i < boxes.length - 1) arrow(s, x + bw + 0.04, y0 + bh / 2, gap - 0.08);
  });
  const stats = [
    ["45–50", "кадров в секунду на одной RTX 3050", ACCENT],
    ["11 мс", "инференс кадра — real-time с запасом", PRIMARY],
    ["10", "классов дефектов, включая «иные» из ТЗ", WARN],
  ];
  stats.forEach((st, i) => {
    const x = M + i * ((W - 2 * M) / 3);
    s.addText(st[0], { x, y: 4.35, w: 3.6, h: 0.85, fontFace: FONT, fontSize: 44, bold: true,
      color: st[2], margin: 0 });
    s.addText(st[1], { x, y: 5.25, w: 3.6, h: 0.6, fontFace: FONT, fontSize: 13, color: MUTED, margin: 0 });
  });
  s.addText("Тяжёлый инференс — на сервере с GPU; на рабочем месте контролёра — только браузер и камера",
    { x: M, y: 6.35, w: W - 2 * M, h: 0.4, fontFace: FONT, fontSize: 12.5, color: MUTED, margin: 0 });
  s.addNotes("Веб-сервис: FastAPI, веб-интерфейс и библиотека моделей, которую можно менять под задачу. Два режима: анализ фотографии с отчётом и живая камера. Инференс на удалённой GPU.");
}

// ================= 4. ДЕМО =================
{
  const s = base(null, null);
  s.addText("Живая демонстрация", { x: M, y: 1.3, w: W - 2 * M, h: 1.0, fontFace: FONT,
    fontSize: 48, bold: true, color: TEXT, align: "center", margin: 0 });
  s.addText("всё, что вы увидите, считается в реальном времени", { x: M, y: 2.35, w: W - 2 * M, h: 0.4,
    fontFace: FONT, fontSize: 17, color: MUTED, align: "center", margin: 0 });
  s.addImage({ path: "slides_build/demo_dry_joint.jpg", x: M, y: 3.15, w: 4.45, h: 3.34, shadow: shadow() });
  s.addText("непропаянные элементы — 9 из 9 на реальном фото", { x: M, y: 6.55, w: 4.45, h: 0.35,
    fontFace: FONT, fontSize: 11, color: MUTED, margin: 0 });
  const rows = [
    [ACCENT, "Анализ фотографии", "вердикт «годен / проверка / брак» + чек-лист пунктов ТЗ"],
    [PRIMARY, "Живая камера", "маски дефектов в реальном времени, поток стабилизирован"],
    [WARN, "Переключение моделей", "одна плата — две честные интерпретации"],
  ];
  rows.forEach((r, i) => {
    const y = 3.35 + i * 1.05;
    dot(s, 5.7, y + 0.08, r[0]);
    s.addText(r[1], { x: 6.0, y: y - 0.08, w: 6.5, h: 0.4, fontFace: FONT, fontSize: 18, bold: true,
      color: TEXT, margin: 0 });
    s.addText(r[2], { x: 6.0, y: y + 0.32, w: 6.5, h: 0.4, fontFace: FONT, fontSize: 13.5,
      color: MUTED, margin: 0 });
  });
  s.addNotes("Демонстрация: фото-анализ с чек-листом ТЗ, живая камера (палец закрывает дефект — детекция гаснет), переключение моделей на одной плате.");
}

// ================= 5. МЕТРИКИ =================
{
  const s = base("МЕТРИКИ", "Честная валидация: платы, которых модель не видела");
  s.addChart(p.charts.BAR, [{
    name: "mAP@0.5",
    labels: ["Наша v1 · PKU", "Наша v2 · PKU+DsPCBSD+", "YOLO26 · честный тест",
             "YOLOv8m · DsPCBSD+", "YOLOv8m-seg · компоненты"],
    values: [0.944, 0.927, 0.839, 0.839, 0.568],
  }], {
    x: M, y: 1.8, w: 6.9, h: 4.35, barDir: "bar", varyColors: true,
    chartColors: [ACCENT, ACCENT, "44618A", "44618A", "44618A"],
    chartArea: { fill: { color: BG } }, plotArea: { fill: { color: BG } },
    catAxisLabelColor: TEXT, catAxisLabelFontFace: FONT, catAxisLabelFontSize: 11.5,
    valAxisLabelColor: MUTED, valAxisLabelFontFace: FONT, valAxisLabelFontSize: 10,
    valAxisMinVal: 0.4, valAxisMaxVal: 1.0, valGridLine: { color: LINE_C, size: 0.5 },
    catGridLine: { style: "none" },
    showValue: true, dataLabelPosition: "outEnd", dataLabelColor: TEXT,
    dataLabelFontFace: FONT, dataLabelFontSize: 11, dataLabelFormatCode: "0.000",
    showLegend: false, showTitle: false,
  });
  card(s, 7.9, 1.8, 4.83, 4.35);
  s.addText("Ловушка утечки данных", { x: 8.2, y: 2.05, w: 4.3, h: 0.4, fontFace: FONT,
    fontSize: 17, bold: true, color: WARN, margin: 0 });
  const leak = [
    "Готовая YOLO26 (2025) показала 0.995 на нашей выборке",
    "По-платный анализ: 0.99+ на всех трёх платах — модель обучалась на них",
    "Её собственный честный тест: 0.839",
    "Наши метрики воспроизводит независимый скрипт bench_val.py",
  ];
  s.addText(leak.map((t, i) => ({ text: t, options: { bullet: bu(), breakLine: i < leak.length - 1 } })),
    { x: 8.2, y: 2.6, w: 4.25, h: 3.3, fontFace: FONT, fontSize: 13.5, color: TEXT,
      paraSpaceAfter: 12, margin: 0 });
  s.addText("Валидация: PKU-Market-PCB-corrected, board-disjoint сплит — 152 фото на платах, не встречавшихся при обучении",
    { x: M, y: 6.45, w: W - 2 * M, h: 0.35, fontFace: FONT, fontSize: 10.5, color: MUTED, margin: 0 });
  s.addNotes("Наша основная модель: 10 классов, точность 0.978. Важнее — как считали: валидация на невиданных платах. Контр-пример: YOLO26 0.995 — утечка, честно 0.839 против наших 0.944.");
}

// ================= 6. ДОКАЗАТЕЛЬСТВО ОБУЧЕНИЯ =================
{
  const s = base("ДОКАЗАТЕЛЬСТВО", "Модели обучены нами — и это проверяемо");
  const vals = [0.696,0.709,0.664,0.744,0.781,0.863,0.857,0.862,0.835,0.881,0.909,0.888,0.924,0.931,0.871,0.879,0.879,0.905,0.923,0.866,0.937,0.935,0.924,0.888,0.901,0.941,0.926,0.88,0.938,0.926,0.879,0.878,0.863,0.884,0.863,0.886,0.88,0.84,0.865,0.853,0.847,0.84,0.846,0.87,0.872,0.847,0.849,0.818,0.824,0.828,0.839,0.848,0.859,0.863,0.864,0.859,0.855,0.856,0.855,0.855];
  const labels = vals.map((_, i) => ((i + 1) % 10 === 0 || i === 0 ? String(i + 1) : ""));
  s.addChart(p.charts.LINE, [{ name: "mAP50", labels, values: vals }], {
    x: M, y: 1.8, w: 6.9, h: 3.9,
    chartColors: [PRIMARY], lineSize: 2.5, lineSmooth: false, lineDataSymbol: "none",
    chartArea: { fill: { color: BG } },
    catAxisLabelColor: MUTED, catAxisLabelFontFace: FONT, catAxisLabelFontSize: 10,
    valAxisLabelColor: MUTED, valAxisLabelFontFace: FONT, valAxisLabelFontSize: 10,
    valAxisMinVal: 0.5, valAxisMaxVal: 1.0, valGridLine: { color: LINE_C, size: 0.5 },
    catGridLine: { style: "none" }, showLegend: false, showTitle: false,
  });
  s.addText("пик 0.941 · эпоха 26 → в продакшн уходит best.pt", { x: 3.35, y: 2.15, w: 3.6, h: 0.35,
    fontFace: FONT, fontSize: 11.5, bold: true, color: ACCENT, margin: 0 });
  s.addText("mAP50 по эпохам — реальный журнал обучения объединённой модели (60 эпох, 14.6 тыс. изображений)",
    { x: M, y: 5.75, w: 6.9, h: 0.55, fontFace: FONT, fontSize: 11, color: MUTED, margin: 0 });

  card(s, 7.9, 1.8, 4.83, 1.95, CODE);
  s.addText([
    { text: "$ python -c \"import torch; ...\"", options: { color: MUTED, breakLine: true } },
    { text: "date: 2026-10-08T22:23   version: 8.4.174", options: { color: ACCENT, breakLine: true } },
    { text: "train_args: data=ml\\merged.yaml", options: { color: TEXT, breakLine: true } },
    { text: "            epochs=60  imgsz=640", options: { color: TEXT } },
  ], { x: 8.15, y: 1.98, w: 4.4, h: 1.6, fontFace: MONO, fontSize: 11, paraSpaceAfter: 6, margin: 0 });

  const proofs = [
    ["1", "Паспорт внутри файла весов: дата, датасет, эпохи — вскрываем командой на сцене за 30 секунд"],
    ["2", "Полные журналы обучения и git-история: кривые, гиперпараметры, все 6 моделей"],
    ["3", "Воспроизводимость: bench_val.py на тех же данных повторяет 0.944 / 0.927"],
  ];
  proofs.forEach((pr, i) => {
    const y = 4.05 + i * 0.78;
    s.addText(pr[0], { x: 7.95, y: y - 0.06, w: 0.5, h: 0.6, fontFace: FONT, fontSize: 26,
      bold: true, color: PRIMARY, margin: 0 });
    s.addText(pr[1], { x: 8.5, y, w: 4.25, h: 0.75, fontFace: FONT, fontSize: 12.5,
      color: TEXT, margin: 0 });
  });
  s.addNotes("Три доказательства: паспорт в весах (показываем командой), журналы обучения с кривыми, воспроизводимость бенчмарком. Плюс git-история.");
}

// ================= 7. ИТОГ =================
{
  const s = base("ИТОГ", "Готово сегодня — и следующий шаг");
  s.addText("Готово", { x: M, y: 1.8, w: 5.9, h: 0.45, fontFace: FONT, fontSize: 17, bold: true,
    color: ACCENT, margin: 0 });
  const done = [
    "Веб-сервис: фото-анализ + живая камера 45–50 FPS",
    "Своя модель на объединении датасетов: 10 классов",
    "Честные метрики: board-disjoint, бенчмарк 6 моделей",
    "Инженерия: 43 автотеста, воспроизводимость, резервирование",
  ];
  s.addText(done.map((t, i) => ({ text: t, options: { bullet: bu(), breakLine: i < done.length - 1 } })),
    { x: M + 0.05, y: 2.35, w: 5.75, h: 2.9, fontFace: FONT, fontSize: 15, color: TEXT,
      paraSpaceAfter: 14, margin: 0 });
  s.addText("Развитие", { x: 7.0, y: 1.8, w: 5.7, h: 0.45, fontFace: FONT, fontSize: 17, bold: true,
    color: PRIMARY, margin: 0 });
  const next = [
    "Дообучение под линию производства — вечер на сотню фото",
    "Собственные классы компонентов (непропай, установка)",
    "SAHI-тайлинг для крупных плат с мелкими дефектами",
    "Интеграция с учётом производства: API, MES-системы",
  ];
  s.addText(next.map((t, i) => ({ text: t, options: { bullet: bu(), breakLine: i < next.length - 1 } })),
    { x: 7.05, y: 2.35, w: 5.6, h: 2.9, fontFace: FONT, fontSize: 15, color: TEXT,
      paraSpaceAfter: 14, margin: 0 });
  s.addText("Контроль качества, который ставится\nна любое рабочее место", { x: M, y: 5.45, w: W - 2 * M,
    h: 1.3, fontFace: FONT, fontSize: 26, bold: true, color: ACCENT, align: "center", margin: 0 });
  s.addNotes("Финал: рабочий сервис, своя модель, честные метрики. Дальше — дообучение на данных конкретного производства: сотня фото и вечер работы.");
}

// ================= 8. ПРИЛОЖЕНИЕ =================
{
  const s = base("ПРИЛОЖЕНИЕ · ДЛЯ ВОПРОСОВ", "Библиотека моделей в системе");
  const hdr = { fill: { color: PANEL2 }, color: TEXT, bold: true, fontFace: FONT, fontSize: 12 };
  const c = (t, o = {}) => ({ text: t, options: { fontFace: FONT, fontSize: 11.5, color: TEXT,
    fill: { color: PANEL }, ...o } });
  const rows = [
    [c("Модель", hdr), c("Тип", hdr), c("Классы", hdr), c("mAP@0.5", hdr), c("Роль", hdr)],
    [c("pku-dspcbsd-merged (наша v2)", { bold: true, color: ACCENT }), c("детекция"), c("10"), c("0.927 *"), c("активная: дорожки + «иные дефекты»", { color: ACCENT })],
    [c("pku-yolov8s (наша v1)"), c("детекция"), c("6"), c("0.944 *"), c("максимум на классах дорожек")],
    [c("yolo26 (чужая, PKU)"), c("детекция"), c("6"), c("0.839 *"), c("бенчмарк новейшей архитектуры")],
    [c("janani · DeepPCB"), c("детекция"), c("6"), c("0.985 **"), c("бейзлайн, домен вырезок")],
    [c("janani · DsPCBSD+"), c("детекция"), c("9"), c("0.839 **"), c("бейзлайн, фрагменты AOI")],
    [c("keremberke · seg"), c("сегментация"), c("4"), c("0.568 **"), c("компоненты: непропай 9/9, установка 10/10")],
  ];
  s.addTable(rows, { x: M, y: 1.8, w: W - 2 * M, colW: [3.3, 1.5, 1.0, 1.3, 5.03],
    border: { pt: 0.75, color: LINE_C }, rowH: 0.52, valign: "middle", margin: 0.08 });
  s.addText("* наша валидация board-disjoint (152 фото)   ** метрики авторов на их валидации\nЛицензии: Ultralytics AGPL-3.0 (внутреннее использование без ограничений), датасеты CC BY 4.0 с атрибуцией",
    { x: M, y: 6.15, w: W - 2 * M, h: 0.7, fontFace: FONT, fontSize: 10.5, color: MUTED,
      lineSpacingMultiple: 1.25, margin: 0 });
  s.addNotes("Запасной слайд для вопросов: все 6 моделей, метрики и роли. Здесь же — лицензии, если спросят про прод.");
}

p.writeFile({ fileName: "PCB_Defect_Inspector.pptx" }).then(() => console.log("OK: PCB_Defect_Inspector.pptx"));
