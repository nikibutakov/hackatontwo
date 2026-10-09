# Быстрый бенчмарк моделей на нашей PKU-валидации (board-disjoint, 152 фото).
# Запуск: python ml/bench_val.py
# workers=0: на Windows multiprocessing из stdin-скрипта не работает,
# а для 152 картинок один процесс не медленнее.
from ultralytics import YOLO

MODELS = [
    ("НАША v1 yolov8s", "ml/weights/pcb_yolov8s.pt", 960),
    ("НАША v2 merged", "ml/weights/pcb_merged_yolov8s.pt", 640),
    ("YOLO26 steven0226", "ml/weights/hf_yolo26_pku.pt", 640),
]

for name, path, sz in MODELS:
    m = YOLO(path)
    r = m.val(data="ml/pku.yaml", imgsz=sz, verbose=False, plots=False,
              device=0, workers=0)
    print(f"{name:20s}: mAP50={r.box.map50:.3f}  mAP50-95={r.box.map:.3f}", flush=True)
