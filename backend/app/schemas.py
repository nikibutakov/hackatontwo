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


class DefectGroup(BaseModel):
    """Дефекты одного класса и решение по ним (разбор вердикта)."""
    class_name: str
    label: str = Field(description="Русское название класса для UI")
    category: str = Field(description="Пункт ТЗ (id из config.TZ_CATEGORIES)")
    count: int
    area_pct: Optional[float] = Field(description="Суммарная площадь в % от кадра (None — размер кадра неизвестен)")
    status: Literal["ok", "warning", "reject"]
    note: Optional[str] = Field(
        default=None,
        description="Почему warning повышен до reject (сработал порог количества/площади)",
    )


class Verdict(BaseModel):
    """Итоговое решение по детали."""
    status: Literal["ok", "warning", "reject"]
    reason: str = Field(description="Человекочитаемое объяснение решения")
    defects: list[DefectGroup] = Field(
        default_factory=list,
        description="Разбор по классам, самые серьёзные первыми",
    )


class Summary(BaseModel):
    """Сводка по кадру для таблицы результатов."""
    total: int
    by_class: dict[str, int] = Field(description="Количество дефектов по классам")


class TzCheckItem(BaseModel):
    """Один пункт чек-листа "Проверка по ТЗ"."""
    id: str = Field(description="id пункта: open_circuit | unsoldered | component_damage | other")
    title: str = Field(description="Формулировка пункта, как в тексте задания")
    state: Literal["reject", "warning", "clear", "not_checked"] = Field(
        description="reject/warning — найдены дефекты; clear — проверено, чисто; "
                    "not_checked — активная модель не распознаёт дефекты этого типа")
    found: list[str] = Field(default_factory=list, description="Найденные дефекты этого пункта, текстом")
    approximate: bool = Field(default=False, description="Пункт закрыт классом-приближением")
    note: Optional[str] = Field(default=None, description="Пояснение (приближение / не проверяется)")


class AnalyzeResponse(BaseModel):
    """Ответ POST /api/analyze (полный отчёт по фотографии)."""
    model: str = Field(description="id модели, которая выполняла инференс")
    time_ms: int = Field(description="Время инференса, мс")
    image_size: dict[str, int] = Field(description="Размер исходного изображения {width, height}")
    detections: list[Detection]
    summary: Summary
    verdict: Verdict
    tz_checklist: list[TzCheckItem] = Field(
        default_factory=list,
        description="Проверка по пунктам ТЗ (задание 4), в порядке текста задания",
    )


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
