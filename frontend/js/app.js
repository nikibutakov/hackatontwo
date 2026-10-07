// ============================================================
// РОЛЬ: Frontend-разработчик
// ЧТО ЗДЕСЬ: инициализация страницы — переключение вкладок,
// переключатель моделей в шапке, индикатор живости API.
//
// Уход с вкладки «Камера» останавливает поток: иначе он невидимо
// продолжал бы грузить сервер и держать камеру включённой.
// Переключение модели: селектор блокируется на время загрузки весов,
// результат — во всплывающем уведомлении; при ошибке селектор
// возвращается на модель, которая реально осталась активной.
//
// ЧТО СДЕЛАТЬ (TODO):
// 1. Индикатор: зелёный = API жив, красный = недоступен (уже опрашивает
//    /api/health каждые 10 секунд — проверьте порог на практике).
// ============================================================

(() => {
  // ---- Вкладки ----
  const tabs = document.querySelectorAll(".tab");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      if (tab.dataset.tab !== "camera" && cameraTab.isRunning()) cameraTab.stop();
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

  function renderModels(models) {
    modelSelect.innerHTML = "";
    for (const m of models) {
      const option = document.createElement("option");
      option.value = m.id;
      option.textContent = m.id + (m.type === "segmentation" ? " (сегм.)" :
                                   m.type === "detection" ? " (детекция)" : "") +
                           (m.error ? " ⚠" : "");
      if (m.error) option.title = "Ошибка загрузки: " + m.error;
      option.selected = m.active;
      modelSelect.appendChild(option);
    }
  }

  async function refreshModels() {
    try {
      renderModels(await apiGetModels());
    } catch (_) {
      modelSelect.innerHTML = `<option>недоступно</option>`;
    }
  }

  modelSelect.addEventListener("change", async () => {
    const modelId = modelSelect.value;
    modelSelect.disabled = true;
    showToast(`Загружаю модель ${modelId}…`, "info", 2500);
    try {
      // ответ — уже обновлённый список с новой активной моделью
      renderModels(await apiActivateModel(modelId));
      showToast(`Активна модель ${modelId}`, "ok");
    } catch (err) {
      showToast("Не удалось переключить модель: " + err.message, "error", 7000);
      await refreshModels(); // вернуть селектор на реально активную модель
    } finally {
      modelSelect.disabled = false;
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
