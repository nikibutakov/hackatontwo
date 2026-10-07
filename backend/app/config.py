# ============================================================
# РОЛЬ: Backend-разработчик (дописывает по мере надобности)
#       ML-участник (настройки моделей и порогов)
#
# ЧТО ЗДЕСЬ: все настройки проекта в одном месте — пороги
# уверенности, бизнес-правила вердикта, реестр моделей,
# параметры сглаживания живого потока.
#
# ЧТО СДЕЛАТЬ (TODO):
# 1. [ML]     После загрузки/обучения моделей добавить их в MODEL_REGISTRY
#             и выставить USE_MOCK=false (или через переменную окружения).
# 2. [Backend] Уточнить пороги VERDICT_RULES (reject_count / reject_area_pct)
#             на реальных фото плат.
# 3. [Backend] Подобрать CONFIRM_FRAMES / HOLD_MS на реальном потоке камеры.
# ============================================================

import os
from pathlib import Path

# Корень репозитория (backend/app/config.py -> ../../)
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ---------- Режим инференса ----------

# true  = заглушка (фейковые детекции, ML не нужен) — режим разработки фронтенда
# false = настоящая модель из MODEL_REGISTRY (active)
# Можно переопределить переменной окружения USE_MOCK=false
USE_MOCK = os.getenv("USE_MOCK", "true").lower() in ("1", "true", "yes")

# ---------- Пороги инференса (подбирает ML) ----------

CONF_THRESHOLD = 0.25   # минимальная уверенность, ниже — детекция отбрасывается
IOU_THRESHOLD = 0.45    # порог NMS (слияния пересекающихся рамок)
INPUT_SIZE = 640        # размер, в который модель сжимает кадр

# ---------- Реестр моделей ----------
# Каждая запись: id (короткое имя для API), тип, путь к весам.
# АКТИВНАЯ модель выбирается ключом ACTIVE_MODEL.
# TODO [ML]: после обучения своей модели на DeepPCB добавьте сюда вторую запись,
#   например: {"id": "pcb-deepcbs-yolov8s", "type": "detection", "path": "ml/weights/pcb_yolov8s.pt"}
#   и научитесь переключаться через UI (POST /api/models/{id}/activate).
MODEL_REGISTRY: list[dict] = [
    {
        "id": "hf-keremberke-yolov8m-seg",
        "type": "segmentation",   # выдаёт маски (полигоны)
        "path": "ml/weights/hf_yolov8m_seg.pt",
        "description": "Бейзлайн с Hugging Face: dry_joint, incorrect_installation, pcb_damage, short_circuit",
    },
]

ACTIVE_MODEL = "hf-keremberke-yolov8m-seg"

# ---------- Бизнес-правила вердикта ----------
#
# Правило класса — словарь:
#   "severity":        базовая критичность одного дефекта:
#                        "reject"  -> деталь в брак
#                        "warning" -> предупреждение (решает оператор)
#                        "ok"      -> класс не считается дефектом
#   "reject_count":    (необяз.) столько дефектов класса и больше => брак
#   "reject_area_pct": (необяз.) суммарная площадь дефектов класса в % от
#                      площади кадра, начиная с которой => брак
#   "category":        пункт ТЗ, к которому относится класс (id из TZ_CATEGORIES)
#   "approximate":     (необяз.) True — класс закрывает пункт ТЗ лишь
#                      приблизительно (в отчёте это честно помечается)
# Пороги только ПОВЫШАЮТ warning до reject. Класс, которого нет в таблице,
# считается warning и относится к "иным дефектам" (неизвестное — показать
# оператору, но не браковать).
# Площадь считается по полигону маски, у моделей детекции — по рамке.
# ВАЖНО: % берётся от КАДРА, а не от платы — для фото крупным планом,
# где плата занимает почти весь кадр, это близкие величины.
VERDICT_RULES: dict[str, dict] = {
    # --- классы бейзлайн-модели с HF ---
    "dry_joint":              {"severity": "reject", "category": "unsoldered"},   # непропай — брак
    "short_circuit":          {"severity": "reject", "category": "other"},        # короткое замыкание — брак
    # компонент стоит не там/не так — брак. Ближайшее к "повреждению компонентов",
    # но это не то же самое — отсюда approximate
    "incorrect_installation": {"severity": "reject", "category": "component_damage", "approximate": True},
    # повреждение САМОЙ ПЛАТЫ (не компонента): мелкое — проверка, крупное — брак
    "pcb_damage":             {"severity": "warning", "reject_area_pct": 1.0, "category": "other"},
    # --- классы своей модели на DeepPCB ---
    "open_circuit":           {"severity": "reject", "category": "open_circuit"},  # РАЗРЫВ ДОРОЖКИ — прямое требование ТЗ
    "missing_hole":           {"severity": "reject", "category": "other"},
    # в разметке DeepPCB (ml/pcb.yaml) короткое замыкание называется "short",
    # у модели с HF — "short_circuit"; правило одно и то же
    "short":                  {"severity": "reject", "category": "other"},
    "spurious_copper":        {"severity": "warning", "reject_count": 3, "reject_area_pct": 1.0, "category": "other"},
    "mouse_bite":             {"severity": "warning", "reject_count": 3, "category": "other"},
    "spur":                   {"severity": "warning", "reject_count": 3, "category": "other"},
}

# ---------- Пункты ТЗ (задание 4) ----------
# Порядок и формулировки — как в тексте задания: "разрыв на дорожках платы,
# наличие не пропаянных элементов, повреждение компонентов, иные дефекты".
# По ним строится чек-лист "Проверка по ТЗ" в ответе /api/analyze.
# Новый класс модели -> укажите его "category" в VERDICT_RULES.
TZ_CATEGORIES: list[dict] = [
    {"id": "open_circuit",     "title": "Разрыв на дорожках платы"},
    {"id": "unsoldered",       "title": "Непропаянные элементы"},
    {"id": "component_damage", "title": "Повреждение компонентов"},
    {"id": "other",            "title": "Иные дефекты"},
]
DEFAULT_CATEGORY = "other"

# ---------- Сглаживание живого потока (анти-мерцание масок) ----------
# Дефект показывается на экране только если подтверждён CONFIRM_FRAMES
# кадров подряд, и остаётся ещё HOLD_MS миллисекунд после пропадания.
CONFIRM_FRAMES = 2
HOLD_MS = 500
# Насколько рамки соседних кадров должны перекрываться (IoU 0..1), чтобы
# считаться одним и тем же дефектом. Меньше — терпимее к тряске камеры,
# но выше шанс склеить два соседних дефекта.
SMOOTH_IOU_MATCH = 0.3

# ---------- Примеры для вкладки «Фото» ----------
# Отобранные фото плат для быстрого демо (кнопки-миниатюры под зоной загрузки).
# Положите сюда 3-5 снимков, на которых модель уверенно находит дефекты.
EXAMPLES_DIR = PROJECT_ROOT / "examples"
EXAMPLE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

# ---------- Метрики ----------
METRICS_FILE = PROJECT_ROOT / "ml" / "metrics.json"
