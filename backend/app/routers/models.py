# ============================================================
# РОЛЬ: Backend-разработчик (почти готово), ML — наполнение
#
# ЧТО ЗДЕСЬ: управление моделями.
#   GET  /api/models                  — какие есть, какая активна
#   POST /api/models/{id}/activate    — переключить активную
# На демо переключение моделей в UI — эффектный момент
# ("бейзлайн с HF" vs "наша дообученная") на одной и той же плате.
#
# ЧТО СДЕЛАТЬ (TODO):
# 1. [ML] как только в реестре две модели — проверить переключение
#    прямо на живом потоке (веса второй грузятся при первом обращении,
#    возможна пауза пару секунд — прогрейте её до демо отдельным запросом).
# ============================================================

from fastapi import APIRouter, HTTPException

from ..model_manager import manager
from ..schemas import ModelInfo

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("", response_model=list[ModelInfo])
async def list_models():
    """Список доступных моделей: id, тип, загружена ли, активна ли."""
    return manager.list_models()


@router.post("/{model_id}/activate", response_model=list[ModelInfo])
async def activate_model(model_id: str):
    """Сделать модель активной. Возвращает обновлённый список."""
    if model_id not in manager._models:
        raise HTTPException(
            status_code=404,
            detail=f"Модель '{model_id}' не найдена. Доступны: {list(manager._models.keys())}",
        )
    manager.set_active(model_id)
    return manager.list_models()
