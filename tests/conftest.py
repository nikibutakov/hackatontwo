# ============================================================
# Общие фикстуры тестов.
#
# Тесты идут в режиме ЗАГЛУШКИ (USE_MOCK=true): ML и веса не нужны,
# MockModel отдаёт три детекции — dry_joint, short_circuit, pcb_damage.
# Переменная выставляется ДО импорта приложения: config читает её
# при импорте.
# ============================================================

import io
import os

os.environ["USE_MOCK"] = "true"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from backend.app import config  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app.smoothing import frame_smoother  # noqa: E402


@pytest.fixture
def client():
    # with — чтобы отработал lifespan (прогрев модели), как на настоящем сервере
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_smoother():
    """Сглаживатель — глобальный объект; между тестами его состояние не должно течь."""
    frame_smoother.reset()
    yield
    frame_smoother.reset()


@pytest.fixture
def fixed_rules(monkeypatch):
    """Фиксированные правила вердикта: тесты не ломаются, когда команда
    подбирает пороги в config.VERDICT_RULES под реальные фото."""
    rules = {
        "hard": {"severity": "reject", "category": "open_circuit"},
        "soft": {"severity": "warning", "reject_count": 3, "category": "other"},
        "area": {"severity": "warning", "reject_area_pct": 1.0, "category": "other"},
        "approx": {"severity": "reject", "category": "component_damage", "approximate": True},
        "harmless": {"severity": "ok", "category": "other"},
    }
    monkeypatch.setattr(config, "VERDICT_RULES", rules)
    return rules


def make_image_bytes(width=320, height=240, fmt="JPEG", color=(30, 90, 45), exif=None) -> bytes:
    image = Image.new("RGB", (width, height), color)
    buffer = io.BytesIO()
    kwargs = {"exif": exif} if exif is not None else {}
    image.save(buffer, fmt, **kwargs)
    return buffer.getvalue()


def det(class_name, x=0, y=0, w=10, h=10, confidence=0.8, polygon=None) -> dict:
    """Детекция в формате, который отдают модели."""
    return {
        "class_name": class_name,
        "confidence": confidence,
        "bbox": [x, y, x + w, y + h],
        "polygon": polygon,
    }
