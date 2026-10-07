# ============================================================
# РОЛЬ: Backend-разработчик (тонкая настройка), ML — тестирование
#
# ЧТО ЗДЕСЬ: анти-мерцание для живого потока камеры.
# Модель на видео-потоке "дышит": детекция то появляется, то
# пропадает. Smoother показывает дефект только после подтверждения
# в CONFIRM_FRAMES кадрах подряд и держит его на экране ещё
# HOLD_MS миллисекунд после пропадания.
#
# ЧТО СДЕЛАТЬ (TODO):
# 1. Рабочая версия уже написана (сглаживание по классу).
#    Улучшение: привязка к МЕСТУ на кадре (сопоставление рамок
#    по IoU между кадрами), чтобы два разных dry_joint в разных
#    местах не сливались в один счётчик.
# 2. Подобрать CONFIRM_FRAMES / HOLD_MS в config.py на реальном
#    потоке (цель: маски не мигают, но появление заметно в течение ~0.5 с).
# ============================================================

import time

from . import config


class FrameSmoother:
    """Сглаживание детекций по времени. Один экземпляр на поток камеры."""

    def __init__(self, confirm_frames: int = None, hold_ms: int = None):
        self.confirm_frames = confirm_frames or config.CONFIRM_FRAMES
        self.hold_ms = hold_ms or config.HOLD_MS
        # class_name -> {"streak": сколько кадров подряд видели,
        #                "shown": показан ли сейчас,
        #                "last_seen_ms": время последнего появления}
        self._state: dict[str, dict] = {}
        # последний стабильный вид детекции для показа (с реальными координатами)
        self._last_detection: dict[str, dict] = {}

    def process(self, detections: list[dict]) -> list[dict]:
        """Принимает сырые детекции кадра, возвращает стабилизированные."""
        now_ms = time.time() * 1000
        seen_classes = {det["class_name"] for det in detections}

        # обновляем счётчики
        for det in detections:
            name = det["class_name"]
            state = self._state.setdefault(name, {"streak": 0, "shown": False, "last_seen_ms": 0})
            state["streak"] += 1
            state["last_seen_ms"] = now_ms
            self._last_detection[name] = det

        for name, state in self._state.items():
            if name not in seen_classes:
                state["streak"] = 0

        # решаем, что показывать
        result = []
        for name, state in self._state.items():
            confirmed = state["streak"] >= self.confirm_frames
            still_holding = now_ms - state["last_seen_ms"] < self.hold_ms
            if confirmed:
                state["shown"] = True
            elif not still_holding:
                state["shown"] = False
            if state["shown"] and name in self._last_detection:
                result.append(self._last_detection[name])

        # чистим забытые классы, чтобы состояние не росло бесконечно
        stale = [n for n, s in self._state.items()
                 if not s["shown"] and s["streak"] == 0 and now_ms - s["last_seen_ms"] > 5000]
        for name in stale:
            self._state.pop(name, None)
            self._last_detection.pop(name, None)

        return result


# Один сглаживатель на приложение (один поток камеры).
# TODO [Backend]: если появится несколько камер — ключом добавить id камеры.
frame_smoother = FrameSmoother()
