// ============================================================
// РОЛЬ: Frontend-разработчик
// ЧТО ЗДЕСЬ: инициализация страницы — переключение вкладок,
// переключатель моделей в шапке, индикатор живости API.
//
// ЧТО СДЕЛАТЬ (TODO):
// 1. При переключении модели во время активного потока камеры —
//    предупредить, что первое время инференс будет паузой (грузятся веса).
// 2. Индикатор: зелёный = API жив, красный = недоступен (уже опрашивает
//    /api/health каждые 10 секунд — проверьте порог на практике).
// ============================================================

(() => {
  // ---- Вкладки ----
  const tabs = document.querySelectorAll(".tab");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("tab--active"));
      document.querySelectorAll(".tab-content").forEach((c) =>
        c.classList.remove("tab-content--active"));
      tab.classList.add("tab--active");
      document.getElementById("tab-" + tab.dataset.tab)
        .classList.add("tab-content--active");

      // ленивая загрузка данных вкладкой «Метрики»
      if (tab.dataset.tab === "metrics") metricsTab.load();
    });
  });

  // ---- Переключатель моделей ----
  const modelSelect = document.getElementById("model-select");

  async function refreshModels() {
    try {
      const models = await apiGetModels();
      modelSelect.innerHTML = "";
      for (const m of models) {
        const option = document.createElement("option");
        option.value = m.id;
        option.textContent = m.id + (m.type === "segmentation" ? " (сегм.)" :
                                     m.type === "detection" ? " (детекция)" : "");
        option.selected = m.active;
        modelSelect.appendChild(option);
      }
    } catch (_) {
      modelSelect.innerHTML = `<option>недоступно</option>`;
    }
  }

  modelSelect.addEventListener("change", async () => {
    try {
      await apiActivateModel(modelSelect.value);
      // после переключения список придёт с новой активной моделью
      await refreshModels();
    } catch (err) {
      alert("Не удалось переключить модель: " + err.message);
    }
  });

  // ---- Индикатор живости API ----
  const healthDot = document.getElementById("health-dot");
  async function checkHealth() {
    try {
      const h = await apiGetHealth();
      healthDot.className = "health-dot health-dot--ok";
      healthDot.title = `API жив · модель: ${h.active_model}` +
        (h.mock_mode ? " (ЗАГЛУШКА)" : "");
    } catch (_) {
      healthDot.className = "health-dot health-dot--down";
      healthDot.title = "API недоступен";
    }
  }

  refreshModels();
  checkHealth();
  setInterval(checkHealth, 10000);
})();
