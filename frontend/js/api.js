// ============================================================
// РОЛЬ: Frontend-разработчик
// ЧТО ЗДЕСЬ: единый клиент API. Все запросы — только через этот файл.
// Базовый адрес = адрес страницы, поэтому работает и на localhost,
// и через Tailscale/Cloudflare (фронт и API на одном сервере).
//
// ЧТО СДЕЛАТЬ (TODO):
// 1. Добавить человекопонятные сообщения об ошибках (сейчас throw).
// 2. Если API "молчит" больше N секунд — индикатор в шапке красный
//    (обработчик уже опрашивает /api/health в app.js).
// ============================================================

const API_BASE = window.location.origin + "/api";

/** Низкоуровневый запрос с единой обработкой ошибок. */
async function apiFetch(path, options = {}) {
  let response;
  try {
    response = await fetch(API_BASE + path, options);
  } catch (networkError) {
    throw new Error("Сервер недоступен: " + networkError.message);
  }
  if (!response.ok) {
    let detail = response.status + " " + response.statusText;
    try {
      const body = await response.json();
      if (body.detail) detail = body.detail;
    } catch (_) { /* тело не JSON — оставляем статус */ }
    throw new Error(detail);
  }
  return response.json();
}

/** POST /api/analyze — полный анализ фотографии. */
async function apiAnalyzeImage(file, conf = null) {
  const form = new FormData();
  form.append("image", file);
  const query = conf ? `?conf=${encodeURIComponent(conf)}` : "";
  return apiFetch("/analyze" + query, { method: "POST", body: form });
}

/** POST /api/frame — кадр живого потока (сглаженные детекции).
 *  conf — порог уверенности для кадра (null — порог модели из реестра). */
async function apiPostFrame(jpegBlob, conf = null) {
  const form = new FormData();
  form.append("image", jpegBlob, "frame.jpg");
  const query = conf ? `?conf=${encodeURIComponent(conf)}` : "";
  return apiFetch("/frame" + query, { method: "POST", body: form });
}

/** GET /api/models — список моделей. */
async function apiGetModels() {
  return apiFetch("/models");
}

/** POST /api/models/{id}/activate — переключить активную модель. */
async function apiActivateModel(modelId) {
  return apiFetch(`/models/${encodeURIComponent(modelId)}/activate`, { method: "POST" });
}

/** GET /api/metrics — метрики валидации моделей. */
async function apiGetMetrics() {
  return apiFetch("/metrics");
}

/** GET /api/examples — список примеров фото из папки examples/. */
async function apiGetExamples() {
  return apiFetch("/examples");
}

/** Адрес картинки-примера (для <img src> и fetch). */
function exampleUrl(name) {
  return API_BASE + "/examples/" + encodeURIComponent(name);
}

/** GET /api/health — живость API. */
async function apiGetHealth() {
  return apiFetch("/health");
}
