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

router = APIRouter(prefix="/api", tags=["metrics"])


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics():
    """Метрики валидации всех моделей (из ml/metrics.json)."""
    try:
        data = json.loads(config.METRICS_FILE.read_text(encoding="utf-8"))
        return MetricsResponse(models=data["models"])
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="ml/metrics.json не найден — запустите ML-валидацию")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Не удалось прочитать metrics.json: {exc}")
