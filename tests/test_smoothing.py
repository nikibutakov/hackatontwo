"""Сглаживание потока камеры (backend/app/smoothing.py)."""

from backend.app.smoothing import FrameSmoother, iou
from tests.conftest import det


def smoother(hold_ms=10_000):
    return FrameSmoother(confirm_frames=2, hold_ms=hold_ms, iou_match=0.3)


def test_iou():
    assert iou([0, 0, 10, 10], [0, 0, 10, 10]) == 1
    assert iou([0, 0, 10, 10], [20, 20, 30, 30]) == 0
    assert abs(iou([0, 0, 10, 10], [5, 0, 15, 10]) - 1 / 3) < 1e-9


def test_needs_confirmation_frames():
    s = smoother()
    assert s.process([det("a")]) == []
    assert len(s.process([det("a", x=1)])) == 1


def test_same_class_in_different_places_are_independent():
    # регрессия: раньше счётчик был по классу — два дефекта давали +2 за кадр
    # и "подтверждались" с первого кадра
    s = smoother()
    assert s.process([det("a", x=0), det("a", x=500)]) == []
    assert len(s.process([det("a", x=2), det("a", x=502)])) == 2


def test_different_classes_do_not_match():
    s = smoother()
    s.process([det("a")])
    assert s.process([det("b")]) == []   # другой класс в том же месте — новый трек


def test_hold_keeps_vanished_defect():
    s = smoother(hold_ms=10_000)
    s.process([det("a")])
    s.process([det("a")])
    assert len(s.process([])) == 1


def test_zero_hold_hides_immediately():
    # регрессия: "0 or HOLD_MS" превращал hold_ms=0 в 500
    s = smoother(hold_ms=0)
    s.process([det("a")])
    s.process([det("a")])
    assert s.process([]) == []


def test_reset_clears_state():
    s = smoother()
    s.process([det("a")])
    s.process([det("a")])
    s.reset()
    assert s.process([]) == []
    assert s.process([det("a")]) == []   # подтверждение заново
