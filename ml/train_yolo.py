# ============================================================
# РОЛЬ: ML-участник
# ЧТО ЗДЕСЬ: обучение СВОЕЙ модели YOLO на датасете DeepPCB
# (закрывает «разрыв дорожки» — open_circuit — и ещё 5 классов).
#
# ЗАПУСК (после подготовки датасета, см. ml/README.md):
#   python ml/train_yolo.py --epochs 80 --model-size s
# Результат: ml/weights/pcb_yolov8s.pt + метрики в ml/runs/
#
# ЧТО СДЕЛАТЬ (TODO):
# 1. Подготовить датасет по ml/README.md (папка ml/data/deeppcb).
# 2. Запустить обучение. На Colab T4 / локальной GPU — ~30-60 мин.
#    Без GPU: добавьте --device cpu (дольше, но для 693-картиночного
#    датасета реально).
# 3. После обучения: переписать лучшие метрики в ml/metrics.json
#    (структура — в ml/README.md), иначе вкладка «Метрики» покажет заглушку.
# 4. Добавить модель в MODEL_REGISTRY в backend/app/config.py.
# ============================================================

import argparse
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_YAML = PROJECT_ROOT / "ml" / "pcb.yaml"
WEIGHTS_DIR = PROJECT_ROOT / "ml" / "weights"


def parse_args():
    parser = argparse.ArgumentParser(description="Обучение YOLO на дефектах плат")
    parser.add_argument("--model-size", default="s", choices=["n", "s", "m"],
                        help="размер модели: n (быстрее) / s (баланс) / m (точнее)")
    parser.add_argument("--epochs", type=int, default=80, help="число эпох (60-100)")
    parser.add_argument("--imgsz", type=int, default=640, help="размер входа")
    parser.add_argument("--device", default="", help="0 = GPU, cpu = процессор (пусто = авто)")
    parser.add_argument("--resume", action="store_true", help="продолжить прерванное обучение")
    return parser.parse_args()


def main():
    from ultralytics import YOLO  # pip install -r ml/requirements-ml.txt

    args = parse_args()

    if not DATASET_YAML.exists():
        raise SystemExit(f"Не найден {DATASET_YAML} — сначала настройте его по ml/README.md")

    base_weights = f"yolov8{args.model_size}.pt"  # предобученные веса COCO
    model = YOLO(base_weights)

    train_kwargs = dict(
        data=str(DATASET_YAML),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=16,
        # аугментации: датасет «микроскопный», а камера даёт другие условия света
        hsv_v=0.4,        # сильнее варьируем яркость
        degrees=10,       # лёгкие повороты
        fliplr=0.5,
        mosaic=1.0,
        project=str(PROJECT_ROOT / "ml" / "runs"),
        name="pcb_train",
        exist_ok=True,
    )
    if args.device:
        train_kwargs["device"] = args.device
    if args.resume:
        model = YOLO(str(PROJECT_ROOT / "ml" / "runs" / "pcb_train" / "weights" / "last.pt"))

    results = model.train(**train_kwargs)

    # забираем лучшие веса в стандартное место
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    best = PROJECT_ROOT / "ml" / "runs" / "pcb_train" / "weights" / "best.pt"
    target = WEIGHTS_DIR / f"pcb_yolov8{args.model_size}.pt"
    shutil.copy(best, target)
    print(f"\nГотово. Лучшие веса: {target}")
    print("ДАЛЬШЕ (вручную):")
    print("  1) метрики из ml/runs/pcb_train/ -> ml/metrics.json (структура в ml/README.md)")
    print("  2) добавить модель в MODEL_REGISTRY (backend/app/config.py)")


if __name__ == "__main__":
    main()
