# ============================================================
# РОЛЬ: Backend-разработчик
#
# ЧТО ЗДЕСЬ: Pydantic-схемы — форма JSON-ответов API.
# Фронтенд и бэкенд договариваются через эти структуры.
# Полная документация endpoints с примерами: docs/API.md
#
# ЧТО СДЕЛАТЬ (TODO):
# 1. Если появятся новые поля (например, время кадра, id трека) —
#    добавьте их сюда И в docs/API.md одновременно.
# 2. Автодокументация Swagger доступна на /docs — держите её рабочей.
# ============================================================

from typing import Literal, Optional
from pydantic import BaseModel, Field


class Detection(BaseModel):
    """Одна найденная детекция дефекта."""
    class_name: str = Field(description="Класс дефекта, например 'open_circuit'")
    confidence: float = Field(description="Уверенность модели 0..1")
    bbox: list[float] = Field(description="[x1, y1, x2, y2] рамка")
    polygon: Optional[list[list[float]]] = Field(
        default=None,
        description="Полигон маски точками [x, y] (для сегментации); None у моделей детекции",
    )


class Verdict(BaseModel):
    """Итоговое решение по детали."""
    status: Literal["ok", "warning", "reject"]
    reason: str = Field(description="Человекочитаемое объяснение решения")


class Summary(BaseModel):
    """Сводка по кадру для таблицы результатов."""
    total: int
    by_class: dict[str, int] = Field(description="Количество дефектов по классам")


class AnalyzeResponse(BaseModel):
    """Ответ POST /api/analyze (полный отчёт по фотографии)."""
    model: str = Field(description="id модели, которая выполняла инференс")
    time_ms: int = Field(description="Время инференса, мс")
    image_size: dict[str, int] = Field(description="Размер исходного изображения {width, height}")
    detections: list[Detection]
    summary: Summary
    verdict: Verdict


class FrameResponse(BaseModel):
    """Ответ POST /api/frame — облегчённый, для живого потока.
    Отчётов и сводок нет: потоку нужна минимальная задержка."""
    model: str
    time_ms: int
    detections: list[Detection] = Field(description="Сглаженные (стабилизированные) детекции")


class ModelInfo(BaseModel):
    id: str
    type: str = Field(description="'segmentation' | 'detection'")
    description: str = ""
    loaded: bool = Field(description="Веса реально загружены в память")
    active: bool = Field(description="Модель выбрана активной")
    error: Optional[str] = Field(
        default=None,
        description="Текст ошибки последней попытки загрузки весов (None — ошибок не было)",
    )


class MetricsResponse(BaseModel):
    """Ответ GET /api/metrics — содержимое ml/metrics.json как есть."""
    models: dict[str, dict]
