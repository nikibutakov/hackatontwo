// ============================================================
// РОЛЬ: Frontend-разработчик
// ЧТО ЗДЕСЬ: вкладка «Метрики» — карточка на каждую модель:
// mAP@0.5, таблица per-class, пометка «бейзлайн» / «наша модель».
// Данные из GET /api/metrics (это содержимое ml/metrics.json,
// который заполняет ML-участник после обучения).
//
// ЧТО СДЕЛАТЬ (TODO):
// 1. Сейчас минимальная отрисовка. Улучшить: столбики-бары per-class,
//    сортировка классов по mAP, красная подсветка слабых классов (< 0.5).
// 2. Если пришло "placeholder": true — показать жёлтую пометку
//    «метрики временные, реальные появятся после обучения» (уже сделано,
//     проверьте текст).
// ============================================================

const metricsTab = (() => {
  const container = document.getElementById("metrics-container");

  async function load() {
    container.innerHTML = `<p class="empty-hint">Загрузка метрик…</p>`;
    try {
      const data = await apiGetMetrics();
      render(data.models);
    } catch (err) {
      container.innerHTML = `<p class="empty-hint">Не удалось загрузить метрики: ${err.message}</p>`;
    }
  }

  function render(models) {
    const entries = Object.entries(models);
    if (entries.length === 0) {
      container.innerHTML = `<p class="empty-hint">Метрик пока нет</p>`;
      return;
    }
    container.innerHTML = "";
    for (const [modelId, m] of entries) {
      const card = document.createElement("div");
      card.className = "metric-card";

      const badge = m.baseline
        ? `<span style="color:var(--muted)">бейзлайн (Hugging Face)</span>`
        : `<span style="color:var(--accent)">наша модель</span>`;

      let perClass = "";
      if (m.per_class) {
        perClass = `<table class="detections-table"><thead>
            <tr><th>Класс</th><th>mAP@0.5</th></tr></thead><tbody>` +
          Object.entries(m.per_class).map(([cls, val]) =>
            `<tr><td>${classLabel(cls)}</td><td>${Number(val).toFixed(3)}</td></tr>`).join("") +
          `</tbody></table>`;
      }

      card.innerHTML = `
        <h3>${m.name || modelId}</h3>
        <p>${badge}</p>
        <p><b>mAP@0.5 (box):</b> ${m.map50_box !== undefined ? Number(m.map50_box).toFixed(3) : "—"}</p>
        ${m.map50_mask !== undefined ? `<p><b>mAP@0.5 (mask):</b> ${Number(m.map50_mask).toFixed(3)}</p>` : ""}
        <p class="meta-line">Датасет: ${m.dataset || "—"}</p>
        ${perClass}
        ${m.placeholder ? `<p class="placeholder-note">⚠ Заглушка: реальные метрики появятся после обучения модели</p>` : ""}
      `;
      container.appendChild(card);
    }
  }

  // загружаем при первом открытии вкладки (вызов из app.js)
  return { load };
})();
