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
from fastapi.concurrency import run_in_threadpool

from ..model_manager import manager
from ..schemas import ModelInfo
from ..smoothing import frame_smoother

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("", response_model=list[ModelInfo])
async def list_models():
    """Список доступных моделей: id, тип, загружена ли, активна ли.
    Ничего не загружает — отвечает мгновенно."""
    return manager.list_models()


@router.post("/{model_id}/activate", response_model=list[ModelInfo])
async def activate_model(model_id: str):
    """Сделать модель активной. Возвращает обновлённый список.

    Сначала грузим веса, и только при успехе переключаемся: если веса
    битые, остаётся работать прежняя модель, а не "сломанная" новая."""
    if not manager.has(model_id):
        raise HTTPException(
            status_code=404,
            detail=f"Модель '{model_id}' не найдена. Доступны: {manager.ids()}",
        )
    try:
        await run_in_threadpool(manager.get(model_id).load)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Не удалось загрузить модель '{model_id}': {exc}. "
                   f"Активной осталась '{manager.active_id}'.",
        )
    manager.set_active(model_id)
    # Детекции старой модели (другие классы!) не должны "доживать" на экране
    frame_smoother.reset()
    return manager.list_models()
