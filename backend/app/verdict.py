# ============================================================
# РОЛЬ: Backend-разработчик
#
# ЧТО ЗДЕСЬ: Verdict Engine — превращает список детекций в
# бизнес-решение: ГОДЕН / ПРЕДУПРЕЖДЕНИЕ / БРАК.
# Это слой, который жюри видит как "умную систему", а не просто
# нейросеть с рамками. Отнеситесь к формулировкам reason серьёзно —
# их читают с экрана на демо.
#
# КАК РАБОТАЕТ:
#   1. Детекции группируются по классу: количество + суммарная
#      площадь в % от кадра (по полигону маски или по рамке).
#   2. Статус группы = severity из config.VERDICT_RULES, который
#      повышается warning -> reject, если превышен reject_count
#      или reject_area_pct.
#   3. Итог = худший статус среди групп; reason перечисляет
#      причины брака и (отдельно) что ещё стоит проверить.
#   Разбор по группам уходит на фронтенд в verdict.defects.
#
# ЧТО СДЕЛАТЬ (TODO):
# 1. Уточнить пороги в config.VERDICT_RULES на реальных фото.
# 2. При изменении правил — обновите примеры в docs/API.md.
# ============================================================

from typing import Optional

from . import config

# Русские подписи классов для отчётов. Фронтенд получает их готовыми
# в verdict.defects[].label — второй копии на JS поддерживать не нужно.
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

# Порядок "тяжести" статусов: итог по детали — максимум по группам
SEVERITY_ORDER = {"ok": 0, "warning": 1, "reject": 2}

# Правило для класса, которого нет в VERDICT_RULES
DEFAULT_RULE = {"severity": "warning"}


def label(class_name: str) -> str:
    return RU_LABELS.get(class_name, class_name)


def _fmt(value: float) -> str:
    """1.25 -> '1,3', 2.0 -> '2' — по-русски, с запятой, без лишнего ',0'."""
    return f"{value:.1f}".rstrip("0").rstrip(".").replace(".", ",")


def _polygon_area(points: list[list[float]]) -> float:
    """Площадь многоугольника по формуле шнурования (Гаусса)."""
    total = 0.0
    for i in range(len(points)):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % len(points)]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2


def detection_area(det: dict) -> float:
    """Площадь дефекта в пикселях: по маске, если есть, иначе по рамке.
    Маска точнее: рамка вокруг тонкой диагональной трещины в разы больше её самой."""
    polygon = det.get("polygon")
    if polygon and len(polygon) >= 3:
        return _polygon_area(polygon)
    x1, y1, x2, y2 = det["bbox"]
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def build_summary(detections: list[dict]) -> dict:
    """Сводка: сколько всего дефектов и по каким классам."""
    by_class: dict[str, int] = {}
    for det in detections:
        by_class[det["class_name"]] = by_class.get(det["class_name"], 0) + 1
    return {"total": len(detections), "by_class": by_class}


def _evaluate_group(class_name: str, dets: list[dict], image_area: Optional[float]) -> dict:
    """Статус одной группы дефектов (одного класса) + пояснение, почему так."""
    rule = config.VERDICT_RULES.get(class_name, DEFAULT_RULE)
    count = len(dets)
    area_pct = None
    if image_area:
        area_pct = round(sum(detection_area(d) for d in dets) / image_area * 100, 2)

    status = rule["severity"]
    note = None  # пояснение для reason, если сработал порог
    if status == "warning":
        reject_count = rule.get("reject_count")
        reject_area = rule.get("reject_area_pct")
        if reject_count and count >= reject_count:
            status = "reject"
            note = f"{count} шт. (порог брака — {reject_count})"
        elif reject_area and area_pct is not None and area_pct >= reject_area:
            status = "reject"
            note = f"{_fmt(area_pct)}% площади (порог брака — {_fmt(reject_area)}%)"

    return {
        "class_name": class_name,
        "label": label(class_name),
        "category": rule.get("category", config.DEFAULT_CATEGORY),
        "count": count,
        "area_pct": area_pct,
        "status": status,
        "note": note,
    }


def _describe(group: dict) -> str:
    """'разрыв дорожки ×2' / 'повреждение платы — 2,4% площади (порог брака — 1%)'."""
    text = group["label"]
    if group["note"]:
        return f"{text} — {group['note']}"
    if group["count"] > 1:
        text += f" ×{group['count']}"
    return text


def build_verdict(detections: list[dict], image_size: tuple[int, int] | None = None) -> dict:
    """Строит вердикт по правилам из config.VERDICT_RULES.

    image_size — (width, height) кадра; без него пороги по площади не работают.
    Возвращает {"status", "reason", "defects": [разбор по классам]}.
    """
    if not detections:
        return {"status": "ok", "reason": "Дефектов не обнаружено", "defects": []}

    image_area = image_size[0] * image_size[1] if image_size else None

    groups: dict[str, list[dict]] = {}
    for det in detections:
        groups.setdefault(det["class_name"], []).append(det)
    defects = [_evaluate_group(name, dets, image_area) for name, dets in groups.items()]
    # Сначала самые серьёзные — в таком порядке они и в reason, и в таблице UI
    defects.sort(key=lambda g: (-SEVERITY_ORDER[g["status"]], -g["count"]))

    rejects = [g for g in defects if g["status"] == "reject"]
    warnings = [g for g in defects if g["status"] == "warning"]

    if rejects:
        reason = "Брак: " + "; ".join(_describe(g) for g in rejects)
        if warnings:
            reason += ". Также проверить: " + "; ".join(_describe(g) for g in warnings)
        status = "reject"
    elif warnings:
        reason = "Требует проверки оператора: " + "; ".join(_describe(g) for g in warnings)
        status = "warning"
    else:
        reason = "Критичных дефектов нет"
        status = "ok"

    return {"status": status, "reason": reason, "defects": defects}


def _category_of(class_name: str) -> str:
    return config.VERDICT_RULES.get(class_name, DEFAULT_RULE).get("category", config.DEFAULT_CATEGORY)


def build_tz_checklist(defects: list[dict], model_classes: Optional[list[str]]) -> list[dict]:
    """Чек-лист по пунктам ТЗ (config.TZ_CATEGORIES) для отчёта по фото.

    defects       — разбор из build_verdict()["defects"];
    model_classes — классы, которые умеет находить модель (None — неизвестно,
                    тогда считаем, что проверяются все пункты).

    state пункта:
      "reject" / "warning" — найдены дефекты (худший статус среди них);
      "clear"              — модель этот пункт проверяет, дефектов нет;
      "not_checked"        — у модели нет ни одного класса этого пункта:
                             честнее сказать "не проверяется", чем "не найдено".
    """
    items = []
    for cat in config.TZ_CATEGORIES:
        groups = [g for g in defects
                  if g["category"] == cat["id"] and g["status"] != "ok"]

        if model_classes is None:
            covering = None
        else:
            covering = [c for c in model_classes if _category_of(c) == cat["id"]]
        # "иные дефекты" проверяются всегда, когда модель вообще что-то находит
        checked = covering is None or bool(covering) or bool(groups)
        # приближение: все классы модели, закрывающие пункт, помечены approximate
        approximate = bool(covering) and all(
            config.VERDICT_RULES.get(c, {}).get("approximate") for c in covering)

        if groups:
            worst = max(groups, key=lambda g: SEVERITY_ORDER[g["status"]])
            state = worst["status"]
        elif checked:
            state = "clear"
        else:
            state = "not_checked"

        note = None
        if approximate:
            names = ", ".join(label(c) for c in covering)
            note = f"приближённо: модель распознаёт «{names}»"
        elif state == "not_checked":
            note = "активная модель не распознаёт дефекты этого типа"

        items.append({
            "id": cat["id"],
            "title": cat["title"],
            "state": state,
            "found": [_describe(g) for g in groups],
            "approximate": approximate,
            "note": note,
        })
    return items
