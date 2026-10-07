# ============================================================
# РОЛЬ: ML-участник
# ЧТО ЗДЕСЬ: скачивание бейзлайн-модели с Hugging Face:
#   keremberke/yolov8m-pcb-defect-segmentation
# (сегментация; классы: dry_joint, incorrect_installation,
#  pcb_damage, short_circuit; датасет 189 фото, mAP@0.5 ~0.57)
#
# ЗАПУСК:
#   pip install -r ml/requirements-ml.txt
#   python ml/download_hf_model.py
# Результат: ml/weights/hf_yolov8m_seg.pt
#
# ПОСЛЕ СКАЧИВАНИЯ — ПРОВЕРКА (главный риск совместимости):
#   python ml/download_hf_model.py --check
# Если чек падает на новой версии ultralytics — варианты:
#   a) pip install "ultralytics==8.0.23" ultralyticsplus==0.0.24
#      (пин из карточки модели; держите отдельным venv, чтобы не сломать обучение)
#   b) дообучить свою сегментационную модель на том же датасете
#      (keremberke/pcb-defect-segmentation, COCO-формат, см. ml/README.md)
# ============================================================

import argparse
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def download(repo_id: str, out_path: Path):
    from huggingface_hub import hf_hub_download
    out_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Скачиваю {repo_id}/best.pt ...")
    local_path = hf_hub_download(repo_id=repo_id, filename="best.pt")
    shutil.copy(local_path, out_path)
    print(f"Готово: {out_path}")


def check(out_path: Path):
    """Проверка: открываются ли веса текущей версией ultralytics + один инференс."""
    from ultralytics import YOLO
    from PIL import Image
    import numpy as np

    print(f"Загружаю {out_path} ...")
    model = YOLO(str(out_path))
    print(f"Задача: {model.task}")
    dummy = Image.fromarray(np.zeros((480, 640, 3), dtype=np.uint8))
    result = model.predict(dummy, verbose=False)[0]
    print(f"Инференс прошёл, детекций: {len(result.boxes)} (на чёрном кадре — 0 это нормально)")
    print("Классы модели:", model.names)
    print("OK — модель совместима. Переключайте сервер: USE_MOCK=false")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Скачивание и проверка моделей с HF")
    parser.add_argument("--repo", help="id репозитория HF")
    parser.add_argument("--out", required=True, help="куда сохранять веса (от корня проекта)")
    parser.add_argument("--check", action="store_true", help="проверить веса инференсом")
    
    args = parser.parse_args()

    out_path = Path(args.out)
    if not args.repo and not args.check:
        parser.error("нечего делать: укажите --repo (скачать) и/или --check (проверить)")

    if args.repo:
        download(args.repo, out_path)   # скачать
        check(out_path)                 # и сразу проверить свежескачанное
    else:
        check(out_path)                 # только проверить уже лежащий файл
