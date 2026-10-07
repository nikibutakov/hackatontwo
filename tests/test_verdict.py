"""Правила вердикта (backend/app/verdict.py)."""

from backend.app import config
from backend.app.verdict import build_summary, build_verdict, detection_area
from tests.conftest import det

IMAGE_1000 = (1000, 1000)  # 1% площади кадра = 10 000 px²


def test_no_detections_is_ok(fixed_rules):
    verdict = build_verdict([], IMAGE_1000)
    assert verdict["status"] == "ok"
    assert verdict["defects"] == []


def test_reject_class(fixed_rules):
    verdict = build_verdict([det("hard")], IMAGE_1000)
    assert verdict["status"] == "reject"
    assert verdict["reason"].startswith("Брак")


def test_count_threshold_escalates_warning(fixed_rules):
    two = build_verdict([det("soft"), det("soft", x=50)], IMAGE_1000)
    three = build_verdict([det("soft", x=i * 50) for i in range(3)], IMAGE_1000)
    assert two["status"] == "warning"
    assert three["status"] == "reject"
    assert "3 шт. (порог брака — 3)" in three["reason"]


def test_area_threshold_escalates_warning(fixed_rules):
    small = build_verdict([det("area", w=50, h=100)], IMAGE_1000)    # 0,5%
    large = build_verdict([det("area", w=200, h=100)], IMAGE_1000)   # 2%
    assert small["status"] == "warning"
    assert large["status"] == "reject"
    assert large["defects"][0]["area_pct"] == 2.0
    assert "2% площади (порог брака — 1%)" in large["reason"]


def test_area_threshold_needs_image_size(fixed_rules):
    verdict = build_verdict([det("area", w=200, h=100)], None)
    assert verdict["status"] == "warning"
    assert verdict["defects"][0]["area_pct"] is None


def test_unknown_class_is_warning(fixed_rules):
    verdict = build_verdict([det("alien_blob")], IMAGE_1000)
    assert verdict["status"] == "warning"
    assert verdict["defects"][0]["category"] == config.DEFAULT_CATEGORY


def test_ok_severity_does_not_affect_verdict(fixed_rules):
    verdict = build_verdict([det("harmless")], IMAGE_1000)
    assert verdict["status"] == "ok"


def test_reject_with_warning_mentions_both(fixed_rules):
    verdict = build_verdict([det("soft"), det("hard")], IMAGE_1000)
    assert verdict["status"] == "reject"
    assert "Также проверить" in verdict["reason"]
    # самые серьёзные — первыми
    assert [g["status"] for g in verdict["defects"]] == ["reject", "warning"]


def test_polygon_area_preferred_over_bbox():
    triangle = det("x", w=100, h=100, polygon=[[0, 0], [100, 0], [0, 100]])
    assert detection_area(triangle) == 5000           # по маске
    assert detection_area(det("x", w=100, h=100)) == 10000  # по рамке


def test_summary_counts_by_class():
    summary = build_summary([det("a"), det("a"), det("b")])
    assert summary == {"total": 3, "by_class": {"a": 2, "b": 1}}


# ---- реальный конфиг: защита от регрессий ----

def test_deeppcb_short_is_reject():
    # В разметке DeepPCB короткое замыкание называется "short" (ml/pcb.yaml);
    # без своего правила оно молча становилось предупреждением.
    verdict = build_verdict([det("short")], IMAGE_1000)
    assert verdict["status"] == "reject"
    assert verdict["defects"][0]["label"] == "короткое замыкание"


def test_every_rule_has_valid_category():
    valid = {c["id"] for c in config.TZ_CATEGORIES}
    for class_name, rule in config.VERDICT_RULES.items():
        assert rule["severity"] in ("ok", "warning", "reject"), class_name
        assert rule.get("category", config.DEFAULT_CATEGORY) in valid, class_name
