# ============================================================
# РОЛЬ: Backend-разработчик (тонкая настройка), ML — тестирование
#
# ЧТО ЗДЕСЬ: анти-мерцание для живого потока камеры.
# Модель на видео-потоке "дышит": детекция то появляется, то
# пропадает. Smoother показывает дефект только после подтверждения
# в CONFIRM_FRAMES кадрах подряд и держит его на экране ещё
# HOLD_MS миллисекунд после пропадания.
#
# КАК РАБОТАЕТ: каждый дефект — отдельный "трек" (класс + место на
# кадре). Детекцию нового кадра привязываем к треку того же класса,
# чья рамка перекрывается с ней сильнее всего (IoU >= SMOOTH_IOU_MATCH).
# Не нашлось пары — заводим новый трек. Так два dry_joint в разных
# местах живут и подтверждаются независимо.
#
# ЧТО СДЕЛАТЬ (TODO):
# 1. Подобрать CONFIRM_FRAMES / HOLD_MS / SMOOTH_IOU_MATCH в config.py
#    на реальном потоке (цель: маски не мигают, но появление заметно
#    в течение ~0.5 с).
# ============================================================

import time

from . import config


def iou(a: list[float], b: list[float]) -> float:
    """Intersection over Union двух рамок [x1, y1, x2, y2]: 0 — не пересекаются,
    1 — совпадают. Мера того, что это "тот же самый" дефект."""
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter == 0:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / (area_a + area_b - inter)


class FrameSmoother:
    """Сглаживание детекций по времени. Один экземпляр на поток камеры."""

    def __init__(self, confirm_frames: int = None, hold_ms: int = None, iou_match: float = None):
        # "is None", а не "or": иначе явно переданный 0 молча заменился бы дефолтом
        self.confirm_frames = config.CONFIRM_FRAMES if confirm_frames is None else confirm_frames
        self.hold_ms = config.HOLD_MS if hold_ms is None else hold_ms
        self.iou_match = config.SMOOTH_IOU_MATCH if iou_match is None else iou_match
        # Трек: {"class_name", "det" (последний вид детекции для показа),
        #        "streak" (кадров подряд), "shown", "last_seen_ms"}
        self._tracks: list[dict] = []

    def reset(self) -> None:
        """Забыть всё (при смене модели / перезапуске камеры)."""
        self._tracks = []

    def process(self, detections: list[dict]) -> list[dict]:
        """Принимает сырые детекции кадра, возвращает стабилизированные."""
        now_ms = time.time() * 1000
        matched: set[int] = set()  # id() треков, уже получивших детекцию в этом кадре

        # 1. Сопоставление. Самые уверенные детекции выбирают трек первыми.
        for det in sorted(detections, key=lambda d: d["confidence"], reverse=True):
            best, best_iou = None, self.iou_match
            for track in self._tracks:
                if id(track) in matched or track["class_name"] != det["class_name"]:
                    continue
                score = iou(track["det"]["bbox"], det["bbox"])
                if score >= best_iou:
                    best, best_iou = track, score
            if best is None:
                best = {"class_name": det["class_name"], "streak": 0, "shown": False}
                self._tracks.append(best)
            best["det"] = det
            best["streak"] += 1          # ровно +1 за кадр на трек
            best["last_seen_ms"] = now_ms
            matched.add(id(best))

        # 2. Треки без детекции в этом кадре — серия прервана
        for track in self._tracks:
            if id(track) not in matched:
                track["streak"] = 0

        # 3. Что показывать
        result = []
        for track in self._tracks:
            if track["streak"] >= self.confirm_frames:
                track["shown"] = True
            elif now_ms - track["last_seen_ms"] >= self.hold_ms:
                track["shown"] = False
            if track["shown"]:
                result.append(track["det"])

        # 4. Чистка: пропавшие и не показываемые треки больше не нужны
        self._tracks = [t for t in self._tracks if t["shown"] or t["streak"] > 0]
        return result


# Один сглаживатель на приложение (один поток камеры).
# TODO [Backend]: если появится несколько камер — ключом добавить id камеры.
frame_smoother = FrameSmoother()
