"""Чек-лист по пунктам ТЗ (verdict.build_tz_checklist)."""

from backend.app.verdict import build_tz_checklist, build_verdict
from tests.conftest import det


def checklist(detections, model_classes):
    defects = build_verdict(detections, (1000, 1000))["defects"]
    return {item["id"]: item for item in build_tz_checklist(defects, model_classes)}


def test_items_follow_tz_order():
    items = build_tz_checklist([], None)
    assert [i["id"] for i in items] == ["open_circuit", "unsoldered", "component_damage", "other"]


def test_found_defect_marks_item(fixed_rules):
    items = checklist([det("hard"), det("hard", x=50)], ["hard"])
    assert items["open_circuit"]["state"] == "reject"
    assert items["open_circuit"]["found"] == ["hard ×2"]


def test_not_checked_when_model_lacks_classes(fixed_rules):
    # модель вообще не умеет искать разрывы — это "не проверяется", а не "не найдено"
    items = checklist([], ["soft"])
    assert items["open_circuit"]["state"] == "not_checked"
    assert items["open_circuit"]["note"]
    assert items["other"]["state"] == "clear"


def test_clear_when_model_checks_and_finds_nothing(fixed_rules):
    items = checklist([], ["hard"])
    assert items["open_circuit"]["state"] == "clear"


def test_unknown_model_classes_mean_everything_checked(fixed_rules):
    items = checklist([], None)
    assert all(item["state"] == "clear" for item in items.values())


def test_approximate_coverage_is_flagged(fixed_rules):
    items = checklist([], ["approx"])
    assert items["component_damage"]["approximate"] is True
    assert "приближённо" in items["component_damage"]["note"]


def test_worst_status_wins(fixed_rules):
    items = checklist([det("soft"), det("harmless")], ["soft", "harmless"])
    assert items["other"]["state"] == "warning"   # ok-класс не считается найденным дефектом
