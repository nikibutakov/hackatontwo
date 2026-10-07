# ============================================================
# РОЛЬ: Backend-разработчик
#
# ЧТО ЗДЕСЬ: POST /api/analyze — полный анализ фотографии платы:
# загрузка файла -> инференс -> сводка -> вердикт.
# Основной endpoint вкладки "Фото".
#
# ЧТО СДЕЛАТЬ (TODO):
# 1. Обработка ошибок: сейчас минимальная. Добавьте понятные
#    сообщения (не-изображение, пустой файл, модель не загрузилась).
# 2. Опционально: сохранение истории анализов (для этого появится
#    endpoint GET /api/history) — только если останется время,
#    это НЕ критично для демо.
# ============================================================

import io
import time

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from PIL import Image

from .. import config
from ..model_manager import manager
from ..schemas import AnalyzeResponse, Detection, Summary, TzCheckItem, Verdict
from ..verdict import build_summary, build_tz_checklist, build_verdict

router = APIRouter(prefix="/api", tags=["analyze"])


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(image: UploadFile = File(..., description="Изображение платы (JPEG/PNG)")):
    """Полный анализ одного изображения: детекции + сводка + вердикт."""
    # 1. Читаем и валидируем изображение
    raw = await image.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Пустой файл")
    try:
        pil_image = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Файл не является изображением (JPEG/PNG)")

    # 2. Инференс активной моделью.
    # predict() — синхронный и тяжёлый (сотни мс). Вызванный прямо в async-
    # функции, он заморозил бы event loop: сервер не отвечал бы НИКОМУ
    # (ни /api/health, ни камере) до конца инференса. run_in_threadpool
    # уносит его в отдельный поток, а event loop продолжает обслуживать запросы.
    # Модель берём один раз: если во время инференса её переключат,
    # в ответе всё равно будет id той, что реально считала.
    model = manager.get_active()
    t0 = time.perf_counter()
    try:
        raw_detections = await run_in_threadpool(model.predict, pil_image)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Ошибка инференса (модель '{model.model_id}'): {exc}. "
                   f"Проверьте, скачаны ли веса (ml/README.md) и установлены ли ml-зависимости.",
        )
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    # 3. Сводка, вердикт и чек-лист по пунктам ТЗ.
    # Чек-листу нужны классы ИМЕННО той модели, что считала: по ним он
    # отличает "дефектов нет" от "модель такие дефекты не ищет".
    summary = build_summary(raw_detections)
    verdict = build_verdict(raw_detections, pil_image.size)
    tz_checklist = build_tz_checklist(verdict["defects"], model.class_names())

    # 4. Формируем ответ по схеме
    return AnalyzeResponse(
        model=model.model_id,
        time_ms=elapsed_ms,
        image_size={"width": pil_image.size[0], "height": pil_image.size[1]},
        detections=[Detection(**det) for det in raw_detections],
        summary=Summary(**summary),
        verdict=Verdict(**verdict),
        tz_checklist=[TzCheckItem(**item) for item in tz_checklist],
    )
