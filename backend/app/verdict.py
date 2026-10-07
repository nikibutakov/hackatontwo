# ============================================================
# РОЛЬ: Backend-разработчик
#
# ЧТО ЗДЕСЬ: Verdict Engine — превращает список детекций в
# бизнес-решение: ГОДЕН / ПРЕДУПРЕЖДЕНИЕ / БРАК.
# Это слой, который жюри видит как "умную систему", а не просто
# нейросеть с рамками. Отнеситесь к формулировкам reason серьёзно —
# их читают с экрана на демо.
#
# ЧТО СДЕЛАТЬ (TODO):
# 1. Базовая логика уже работает. Улучшите её:
#    - количество: N warning-дефектов одного класса => reject
#    - площадь: pcb_damage меньше 1% платы => warning, больше => reject
#      (площадь можно оценить через bbox относительно image_size)
# 2. Подготовьте ЧЕЛОВЕКОПОНЯТНЫЕ названия классов для UI
#    (RU_LABELS ниже) — проверьте, что покрыты все классы обеих моделей.
# 3. При изменении правил — обновите примеры в docs/API.md.
# ============================================================

from . import config

# Русские подписи классов для фронтенда и отчётов
RU_LABELS = {
    "dry_joint": "непропаянный элемент",
    "short_circuit": "короткое замыкание",
    "incorrect_installation": "неправильная установка компонента",
    "pcb_damage": "повреждение платы",
    "open_circuit": "разрыв дорожки",
    "missing_hole": "отсутствующее отверстие",
    "spurious_copper": "лишняя медь",
    "mouse_bite": "дефект края дорожки («мышиный укус»)",
    "spur": "заусенец дорожки",
}

STATUS_LABELS = {
    "ok": "ГОДЕН",
    "warning": "ПРЕДУПРЕЖДЕНИЕ",
    "reject": "БРАК",
}


def build_summary(detections: list[dict]) -> dict:
    """Сводка: сколько всего дефектов и по каким классам."""
    by_class: dict[str, int] = {}
    for det in detections:
        by_class[det["class_name"]] = by_class.get(det["class_name"], 0) + 1
    return {"total": len(detections), "by_class": by_class}


def build_verdict(detections: list[dict], image_size: tuple[int, int] | None = None) -> dict:
    """Строит вердикт по правилам из config.VERDICT_RULES.

    Текущая логика (простая):
      - есть хоть один reject-класс  -> брак
      - иначе есть warning-класс     -> предупреждение
      - иначе                        -> годен
    TODO [Backend]: расширить количеством/площадью (см. шапку файла).
    """
    if not detections:
        return {"status": "ok", "reason": "Дефектов не обнаружено"}

    found_reject = []
    found_warning = []
    for det in detections:
        rule = config.VERDICT_RULES.get(det["class_name"], "warning")
        label = RU_LABELS.get(det["class_name"], det["class_name"])
        if rule == "reject":
            found_reject.append(label)
        elif rule == "warning":
            found_warning.append(label)

    if found_reject:
        # перечисляем уникальные критичные дефекты
        unique = list(dict.fromkeys(found_reject))
        return {
            "status": "reject",
            "reason": "Брак: обнаружено — " + ", ".join(unique),
        }
    if found_warning:
        unique = list(dict.fromkeys(found_warning))
        return {
            "status": "warning",
            "reason": "Требует проверки оператора: " + ", ".join(unique),
        }
    return {"status": "ok", "reason": "Критичных дефектов нет"}
