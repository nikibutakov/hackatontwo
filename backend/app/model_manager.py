# ============================================================
# РОЛЬ: ML-участник (главный файл для него), Backend — поддержка
#
# ЧТО ЗДЕСЬ: Model Manager — единая точка доступа к моделям.
#   - MockModel   — заглушка: фейковые детекции без ML (для фронтенда)
#   - YoloModel   — обёртка над ultralytics YOLO (детекция + сегментация)
#   - ModelManager — реестр моделей, переключение, выбор активной
#
# Благодаря менеджеру модели взаимозаменяемы: если обучение
# не успеем — демо работает на бейзлайне с HF, и наоборот.
#
# ЧТО СДЕЛАТЬ (TODO):
# 1. [ML] Скачать бейзлайн:  python ml/download_hf_model.py
#    (веса лягут в ml/weights/hf_yolov8m_seg.pt)
# 2. [ML] Запустить сервер с USE_MOCK=false и проверить, что
#    predict() на фото платы возвращает разумные детекции.
#    Если у весов от keremberke проблемы совместимости с новым
#    ultralytics — грузите через локальный путь (здесь уже так).
# 3. [ML] После обучения своей модели добавить её в MODEL_REGISTRY
#    (config.py) — менеджер подхватит автоматически.
# 4. [ML→позже] Опционально: экспорт в ONNX для ускорения на CPU.
# ============================================================

import logging
import random
import threading
import time
from typing import Optional

from . import config

log = logging.getLogger("pcb.model_manager")

# Формат детекции, который возвращают все модели (словари, не схемы):
# {
#   "class_name": str,
#   "confidence": float,              # 0..1
#   "bbox": [x1, y1, x2, y2],         # координаты исходного изображения
#   "polygon": [[x, y], ...] | None   # маска, если модель сегментационная
# }


class BasePcbModel:
    """Интерфейс модели: принимает PIL.Image, отдаёт список детекций."""

    model_id: str = "base"

    def predict(self, image) -> list[dict]:
        raise NotImplementedError

    def is_loaded(self) -> bool:
        """Загружены ли веса в память. НЕ должен ничего грузить сам."""
        return True

    def load(self) -> None:
        """Загрузить веса (если ещё не загружены). Бросает исключение при ошибке."""

    @property
    def load_error(self) -> Optional[str]:
        """Текст последней ошибки загрузки (None — ошибок не было)."""
        return None

    def class_names(self) -> Optional[list[str]]:
        """Какие классы модель УМЕЕТ находить (None — неизвестно).
        Нужно чек-листу ТЗ: "не найдено" и "модель это не проверяет" — разные вещи."""
        return None


class MockModel(BasePcbModel):
    """Заглушка: возвращает 2-3 правдоподобные детекции без ML.
    Нужна, чтобы фронтенд и вердикты разрабатывались до готовности модели."""

    model_id = "mock"

    # "типовые" дефекты в долях ширины/высоты кадра
    FAKE_DEFECTS = [
        {"class_name": "dry_joint", "cx": 0.35, "cy": 0.42, "w": 0.08, "h": 0.06},
        {"class_name": "short_circuit", "cx": 0.62, "cy": 0.58, "w": 0.10, "h": 0.05},
        {"class_name": "pcb_damage", "cx": 0.48, "cy": 0.70, "w": 0.06, "h": 0.06},
    ]

    def class_names(self) -> Optional[list[str]]:
        return [d["class_name"] for d in self.FAKE_DEFECTS]

    def predict(self, image) -> list[dict]:
        width, height = image.size
        detections = []
        for defect in self.FAKE_DEFECTS:
            # лёгкий джиттер, чтобы выглядело живым на потоке
            jitter = lambda: random.uniform(-0.01, 0.01)
            x1 = (defect["cx"] - defect["w"] / 2 + jitter()) * width
            y1 = (defect["cy"] - defect["h"] / 2 + jitter()) * height
            x2 = (defect["cx"] + defect["w"] / 2 + jitter()) * width
            y2 = (defect["cy"] + defect["h"] / 2 + jitter()) * height
            detections.append({
                "class_name": defect["class_name"],
                "confidence": round(random.uniform(0.55, 0.9), 3),
                "bbox": [round(v, 1) for v in (x1, y1, x2, y2)],
                # полигон = углы рамки: фронтенд отрабатывает отрисовку масок
                "polygon": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
            })
        return detections


class YoloModel(BasePcbModel):
    """Настоящая модель: ultralytics YOLOv8/v11 (детекция или сегментация).
    ultralytics импортируется ЛЕНИВО — без него сервер работает в Mock-режиме."""

    def __init__(self, model_id: str, weights_path, model_type: str):
        self.model_id = model_id
        self.model_type = model_type
        self.weights_path = str(weights_path)
        self._model = None  # ленивая загрузка при первом predict
        self._load_error: Optional[str] = None
        # Инференс идёт в пуле потоков (см. routers/analyze.py), а модель
        # ultralytics не потокобезопасна: фото и кадр камеры могут прийти
        # одновременно. Лок пропускает к модели строго по одному запросу.
        self._lock = threading.Lock()

    def load(self) -> None:
        with self._lock:
            if self._model is not None:
                return
            try:
                from ultralytics import YOLO  # тяжёлый импорт — только по необходимости
                log.info("Загружаю веса %s ...", self.weights_path)
                self._model = YOLO(self.weights_path)
                self._load_error = None
            except Exception as exc:  # веса не скачаны / битые / нет torch
                self._load_error = str(exc)
                log.warning("Модель %s не загрузилась: %s", self.model_id, exc)
                raise

    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error

    def class_names(self) -> Optional[list[str]]:
        # names у ultralytics — {0: 'dry_joint', ...}; до загрузки весов неизвестны
        if self._model is None:
            return None
        return [str(name) for name in self._model.names.values()]

    def predict(self, image) -> list[dict]:
        self.load()
        t0 = time.perf_counter()
        with self._lock:
            result = self._model.predict(
                image,
                conf=config.CONF_THRESHOLD,
                iou=config.IOU_THRESHOLD,
                imgsz=config.INPUT_SIZE,
                verbose=False,
            )[0]
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        log.info("Инференс %s: %d детекций за %d мс", self.model_id, len(result.boxes), elapsed_ms)

        detections = []
        names = result.names  # {0: 'class_name', ...}
        boxes = result.boxes.xyxy.cpu().numpy()
        confs = result.boxes.conf.cpu().numpy()
        # полигоны масок есть только у сегментационных моделей
        polygons = None
        if getattr(result, "masks", None) is not None:
            polygons = result.masks.xy  # список массивов точек [(x, y), ...]

        for i in range(len(boxes)):
            x1, y1, x2, y2 = [float(v) for v in boxes[i]]
            raw_name = str(names[int(result.boxes.cls[i])])
            detections.append({
                # имя класса нормализуется в каноническое (config.CLASS_ALIASES):
                # модели называют одни и те же дефекты по-разному ("0", "open", "open_circuit")
                "class_name": config.CLASS_ALIASES.get(raw_name, raw_name),
                "confidence": round(float(confs[i]), 3),
                "bbox": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
                "polygon": [[float(x), float(y)] for x, y in polygons[i]] if polygons is not None else None,
            })
        return detections


class ModelManager:
    """Держит реестр моделей, отдаёт активную, умеет переключать."""

    def __init__(self):
        self._models: dict[str, BasePcbModel] = {}
        self._descriptions: dict[str, dict] = {}
        self.active_id: Optional[str] = None

        if config.USE_MOCK:
            self._register(MockModel(), {"type": "mock", "description": "ЗАГЛУШКА: фейковые детекции без ML"})
            self.active_id = "mock"
            log.warning("USE_MOCK=true — работаем на заглушке (для разработки фронтенда)")
        else:
            for entry in config.MODEL_REGISTRY:
                path = config.PROJECT_ROOT / entry["path"]
                model = YoloModel(entry["id"], path, entry["type"])
                self._register(model, {"type": entry["type"], "description": entry.get("description", "")})
            self.active_id = config.ACTIVE_MODEL

    def _register(self, model: BasePcbModel, meta: dict):
        self._models[model.model_id] = model
        self._descriptions[model.model_id] = meta

    def get_active(self) -> BasePcbModel:
        model = self._models.get(self.active_id)
        if model is None:
            raise RuntimeError(f"Активная модель '{self.active_id}' не найдена в реестре")
        return model

    def has(self, model_id: str) -> bool:
        return model_id in self._models

    def ids(self) -> list[str]:
        return list(self._models.keys())

    def get(self, model_id: str) -> BasePcbModel:
        return self._models[model_id]

    def set_active(self, model_id: str) -> None:
        if model_id not in self._models:
            raise KeyError(model_id)
        self.active_id = model_id
        log.info("Активная модель переключена на %s", model_id)

    def warmup_active(self) -> None:
        """Загрузить веса активной модели заранее (на старте сервера),
        чтобы первый запрос с камеры не ждал 1–3 секунды. Ошибку не бросает:
        сервер должен подняться даже без весов — она будет видна в /api/models."""
        try:
            self.get_active().load()
        except Exception:
            pass

    def list_models(self) -> list[dict]:
        # ВАЖНО: только читаем состояние, ничего не грузим — иначе
        # GET /api/models подвешивал бы страницу на загрузку всех весов.
        result = []
        for model_id, model in self._models.items():
            meta = self._descriptions[model_id]
            result.append({
                "id": model_id,
                "type": meta["type"],
                "description": meta["description"],
                "loaded": model.is_loaded(),
                "active": model_id == self.active_id,
                "error": model.load_error,
            })
        return result


# Единый экземпляр на всё приложение (импортируется роутерами)
manager = ModelManager()
