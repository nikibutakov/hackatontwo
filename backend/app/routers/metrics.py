# ============================================================
# РОЛЬ: ML-участник (наполнение metrics.json), Frontend (отображение)
#
# ЧТО ЗДЕСЬ: GET /api/metrics — отдаёт содержимое ml/metrics.json.
# Файл заполняет ML после обучения/валидации каждой модели.
# Структура файла описана в ml/README.md.
#
# ЧТО СДЕЛАТЬ (TODO):
# 1. [ML] Заполнить metrics.json реальными цифрами (mAP, per-class).
#    Сейчас там заглушка с "placeholder": true — фронтенд на ней
#    разрабатывается, на демо должны быть НАСТОЯЩИЕ метрики.
# 2. [Frontend] Красиво отрисовать сравнение моделей на вкладке "Метрики".
# ============================================================

import json

from fastapi import APIRouter, HTTPException

from .. import config
from ..schemas import MetricsResponse
from ..verdict import label

router = APIRouter(prefix="/api", tags=["metrics"])


def _class_info(models: dict) -> dict:
    """Русское название и пункт ТЗ для каждого класса из per_class всех моделей —
    фронтенду, чтобы подписать столбики и построить таблицу покрытия ТЗ."""
    names = {cls for m in models.values() for cls in (m.get("per_class") or {})}
    return {
        cls: {
            "label": label(cls),
            "category": config.VERDICT_RULES.get(cls, {}).get("category", config.DEFAULT_CATEGORY),
            "approximate": bool(config.VERDICT_RULES.get(cls, {}).get("approximate")),
        }
        for cls in sorted(names)
    }


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics():
    """Метрики валидации всех моделей (из ml/metrics.json) + справочник классов и пунктов ТЗ."""
    try:
        data = json.loads(config.METRICS_FILE.read_text(encoding="utf-8"))
        models = data["models"]
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="ml/metrics.json не найден — запустите ML-валидацию")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Не удалось прочитать metrics.json: {exc}")
    return MetricsResponse(
        models=models,
        class_info=_class_info(models),
        tz_categories=config.TZ_CATEGORIES,
    )
