# Раскладка PKU-Market-PCB-corrected в стандартную структуру ultralytics.
# Читает ImageSets/{train,val}_board.txt и копирует пары картинка+разметка
# в ml/data/pku/images|labels/{train,val}. Запуск: python ml/prepare_pku.py
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "ml" / "data" / "pku_raw"
DST = ROOT / "ml" / "data" / "pku"

for split in ("train", "val"):
    names = (SRC / "ImageSets" / f"{split}_board.txt").read_text().split()
    for sub in ("images", "labels"):
        (DST / sub / split).mkdir(parents=True, exist_ok=True)
    for name in names:
        stem = name.rsplit(".", 1)[0]
        img = SRC / "images" / name
        lbl = SRC / "labels" / (stem + ".txt")
        assert img.exists(), f"нет картинки: {img.name}"
        assert lbl.exists(), f"нет разметки: {lbl.name}"
        shutil.copy(img, DST / "images" / split / name)
        shutil.copy(lbl, DST / "labels" / split / (stem + ".txt"))
    print(f"{split}: {len(names)} пар")

print("Готово:", DST)