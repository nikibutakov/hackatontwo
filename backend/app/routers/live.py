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

    t0 = time.perf_counter()
    try:
        raw_detections = manager.get_active().predict(pil_image)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Ошибка инференса (модель '{manager.active_id}'): {exc}",
        )
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    smoothed = frame_smoother.process(raw_detections)
    return FrameResponse(
        model=manager.active_id,
        time_ms=elapsed_ms,
        detections=[Detection(**det) for det in smoothed],
    )
