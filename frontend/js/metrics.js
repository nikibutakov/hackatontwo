// ============================================================
// РОЛЬ: Frontend-разработчик
// ЧТО ЗДЕСЬ: вкладка «Метрики». Данные — GET /api/metrics
// (ml/metrics.json, заполняет ML-участник, + справочник классов
// и пунктов ТЗ с бэкенда). Три блока:
//   1. Модели — карточки с крупным mAP@0.5 (box / mask), пометки
//      «бейзлайн» / «наша модель» / «активна», прирост к бейзлайну.
//   2. Покрытие пунктов ТЗ — какая модель какой пункт задания 4
//      закрывает (и с каким mAP). Объясняет, зачем две модели.
//   3. mAP@0.5 по классам — горизонтальные столбики, сортировка по
//      убыванию, линия порога 0,5; слабые классы (< 0,5) — янтарным
//      цветом СО значком и подписью (цвет не единственный признак).
//
// ЧТО СДЕЛАТЬ (TODO):
// 1. [ML] Заменить заглушку в ml/metrics.json реальными цифрами —
//    пока там "placeholder": true, вкладка показывает предупреждение.
// ============================================================

const metricsTab = (() => {
  const container = document.getElementById("metrics-container");
  const WEAK_THRESHOLD = 0.5;   // ниже — класс считается слабым

  /** 0.568 -> "0,568" */
  function fmt(value, digits = 3) {
    return Number(value).toFixed(digits).replace(".", ",");
  }

  async function load() {
    container.innerHTML = `<p class="empty-hint">Загрузка метрик…</p>`;
    try {
      // активную модель берём из /api/models; её недоступность — не повод не показать метрики
      const [data, models] = await Promise.all([
        apiGetMetrics(),
        apiGetModels().catch(() => []),
      ]);
      const activeId = (models.find((m) => m.active) || {}).id;
      render(data, activeId);
    } catch (err) {
      container.innerHTML = `<p class="empty-hint">Не удалось загрузить метрики: ${escapeHtml(err.message)}</p>`;
    }
  }

  function render(data, activeId) {
    const entries = Object.entries(data.models || {});
    if (entries.length === 0) {
      container.innerHTML = `<p class="empty-hint">Метрик пока нет</p>`;
      return;
    }
    const classInfo = data.class_info || {};
    const baseline = entries.find(([, m]) => m.baseline);

    let html = "";
    if (entries.some(([, m]) => m.placeholder)) {
      html += `<div class="metrics-banner">⚠ Часть метрик — временная заглушка
               (<code>"placeholder": true</code> в ml/metrics.json).
               Реальные цифры появятся после обучения и валидации моделей.</div>`;
    }

    html += `<section class="metrics-section">
               <h2 class="metrics-section__title">Модели</h2>
               <div class="metrics-models">
                 ${entries.map(([id, m]) => modelCard(id, m, activeId, baseline)).join("")}
               </div>
               ${entries.length === 1 ? `<p class="meta-line">Своя модель на DeepPCB появится здесь после обучения —
                 будет видно сравнение с бейзлайном.</p>` : ""}
             </section>`;

    if ((data.tz_categories || []).length) {
      html += tzCoverage(entries, data.tz_categories, classInfo);
    }

    html += `<section class="metrics-section">
               <h2 class="metrics-section__title">mAP@0.5 по классам</h2>
               <p class="meta-line">Столбик — mAP@0.5 класса (шкала 0–1), пунктир — порог ${fmt(WEAK_THRESHOLD, 1)}.
                 Ниже порога — <span class="metrics-weak-label">⚠ слабый класс</span>.</p>
               <div class="metrics-models">
                 ${entries.map(([id, m]) => perClassChart(id, m, classInfo)).join("")}
               </div>
             </section>`;

    container.innerHTML = html;
  }

  /** Карточка модели: крупные цифры mAP, пометки, прирост к бейзлайну. */
  function modelCard(id, m, activeId, baseline) {
    const badges = [
      m.baseline
        ? `<span class="chip">бейзлайн (Hugging Face)</span>`
        : `<span class="chip chip--accent">наша модель</span>`,
      id === activeId ? `<span class="chip chip--ok">● активна</span>` : "",
      m.placeholder ? `<span class="chip chip--warning">заглушка</span>` : "",
    ].join("");

    const stat = (title, value, baseValue) => {
      if (value === undefined || value === null) return "";
      let delta = "";
      if (baseValue !== undefined && baseValue !== null) {
        const d = value - baseValue;
        delta = `<div class="stat__delta">${d >= 0 ? "+" : "−"}${fmt(Math.abs(d))} к бейзлайну</div>`;
      }
      return `<div class="stat">
                <div class="stat__value">${fmt(value)}</div>
                <div class="stat__label">${title}</div>
                ${delta}
              </div>`;
    };
    // прирост показываем только у "нашей" модели и только если бейзлайн есть
    const base = !m.baseline && baseline ? baseline[1] : {};

    return `<div class="metric-card">
              <h3>${escapeHtml(m.name || id)}</h3>
              <div class="metric-card__chips">${badges}</div>
              <div class="stats">
                ${stat("mAP@0.5 · рамки", m.map50_box, base.map50_box)}
                ${stat("mAP@0.5 · маски", m.map50_mask, base.map50_mask)}
              </div>
              <p class="meta-line">Датасет: ${escapeHtml(m.dataset || "—")}</p>
            </div>`;
  }

  /** Таблица: строки — пункты ТЗ, столбцы — модели; в ячейке классы модели этого пункта с mAP. */
  function tzCoverage(entries, categories, classInfo) {
    const header = entries.map(([id, m]) => `<th>${escapeHtml(m.name || id)}</th>`).join("");
    const rows = categories.map((cat) => {
      const cells = entries.map(([, m]) => {
        const classes = Object.entries(m.per_class || {})
          .filter(([cls]) => (classInfo[cls] || {}).category === cat.id);
        if (classes.length === 0) {
          return `<td class="tz-cover tz-cover--none">— не распознаёт</td>`;
        }
        const items = classes.map(([cls, val]) => {
          const info = classInfo[cls] || {};
          const approx = info.approximate ? ` <span class="tz-cover__approx" title="закрывает пункт приближённо">≈</span>` : "";
          return `<div>${escapeHtml(info.label || cls)}${approx} · ${fmt(val, 2)}</div>`;
        }).join("");
        return `<td class="tz-cover"><span class="tz-cover__icon">✓</span>${items}</td>`;
      }).join("");
      return `<tr><th scope="row">${escapeHtml(cat.title)}</th>${cells}</tr>`;
    }).join("");

    return `<section class="metrics-section">
              <h2 class="metrics-section__title">Покрытие пунктов ТЗ</h2>
              <div class="table-scroll">
                <table class="detections-table tz-cover-table">
                  <thead><tr><th>Пункт задания 4</th>${header}</tr></thead>
                  <tbody>${rows}</tbody>
                </table>
              </div>
              <p class="meta-line">«≈» — пункт закрыт классом-приближением. Числа — mAP@0.5 класса.</p>
            </section>`;
  }

  /** Горизонтальные столбики mAP по классам одной модели, по убыванию. */
  function perClassChart(id, m, classInfo) {
    const perClass = Object.entries(m.per_class || {}).sort((a, b) => b[1] - a[1]);
    if (perClass.length === 0) {
      return `<div class="metric-card"><h3>${escapeHtml(m.name || id)}</h3>
              <p class="meta-line">Нет данных по классам</p></div>`;
    }
    const rows = perClass.map(([cls, val]) => {
      const info = classInfo[cls] || {};
      const name = info.label || cls;
      const weak = val < WEAK_THRESHOLD;
      const pct = Math.max(0, Math.min(1, val)) * 100;
      const tip = `${name} (${cls}): mAP@0.5 = ${fmt(val)}` + (weak ? " — ниже порога" : "");
      return `<div class="bar-row${weak ? " bar-row--weak" : ""}" title="${escapeHtml(tip)}">
                <div class="bar-row__label">${escapeHtml(name)}</div>
                <div class="bar-row__track">
                  <div class="bar-row__fill" style="width:${pct}%"></div>
                  <div class="bar-row__threshold" style="left:${WEAK_THRESHOLD * 100}%"></div>
                </div>
                <div class="bar-row__value">${fmt(val, 2)}${weak ? ` <span class="metrics-weak-label">⚠ слабый</span>` : ""}</div>
              </div>`;
    }).join("");

    return `<div class="metric-card">
              <h3>${escapeHtml(m.name || id)}</h3>
              <div class="bar-chart">${rows}</div>
            </div>`;
  }

  // загружаем при открытии вкладки (вызов из app.js)
  return { load };
})();
