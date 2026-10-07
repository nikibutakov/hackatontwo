# ============================================================
# РОЛЬ: Backend-разработчик
#
# ЧТО ЗДЕСЬ: POST /api/frame — облегчённый анализ кадра живого
# потока камеры. Отличия от /api/analyze:
#   - ответ минимальный (только детекции), никаких отчётов;
#   - детекции проходят через FrameSmoother (анти-мерцание);
#   - фронтенд шлёт следующий кадр ТОЛЬКО после ответа —
#     темп потока регулируется сам собой.
#
# ЧТО СДЕЛАТЬ (TODO):
# 1. Замерить реальный time_ms на целевом ноутбуке/GPU и решить,
#    хватит ли скорости (цель: хотя бы 4-6 FPS на потоке).
#    Если медленно — см. план в docs/ARCHITECTURE.md (s-модель / ONNX).
# 2. Никакой лишней работы внутри этого endpoint — каждый лишний
#    миллисекунд здесь это FPS демо.
# ============================================================

import io
import time

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from PIL import Image

from ..model_manager import manager
from ..schemas import Detection, FrameResponse
from ..smoothing import frame_smoother

router = APIRouter(prefix="/api", tags=["live"])


@router.post("/frame", response_model=FrameResponse)
async def frame(image: UploadFile = File(..., description="Кадр с камеры (JPEG)")):
    """Анализ одного кадра потока: сглаженные детекции, минимум лишнего."""
    raw = await image.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Пустой файл")
    try:
        pil_image = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Кадр не распознан как изображение")

    # Инференс в пуле потоков — подробности в routers/analyze.py
    model = manager.get_active()
    t0 = time.perf_counter()
    try:
        raw_detections = await run_in_threadpool(model.predict, pil_image)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Ошибка инференса (модель '{model.model_id}'): {exc}",
        )
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    # Пока кадр считался, модель могли переключить (и сглаживатель уже
    # сброшен). Детекции старой модели в новое состояние не пускаем.
    if model.model_id != manager.active_id:
        smoothed = []
    else:
        # smoother вызывается в event loop (не в потоке) — он быстрый,
        # и так к его состоянию никогда не обращаются два потока сразу.
        smoothed = frame_smoother.process(raw_detections)
    return FrameResponse(
        model=model.model_id,
        time_ms=elapsed_ms,
        detections=[Detection(**det) for det in smoothed],
    )
