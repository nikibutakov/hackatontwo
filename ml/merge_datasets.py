# ============================================================
# Слияние PKU-Market-PCB-corrected + DsPCBSD+ в один датасет
# для обучения единой модели на 10 канонических классах.
#
# Запуск: python ml/merge_datasets.py
# Результат: ml/data/merged/{images,labels}/{train,val} + отчёт по классам
#
# Решения (почему так):
#  - ВАЛИДАЦИЯ = только PKU board-disjoint (те же 152 фото, что у текущей
#    модели) — метрики лягут рядом с 0.943 и сравнение будет честным.
#    Данные DsPCBSD+ в валидацию НЕ попадают.
#  - PKU-трейн дублируется PKU_REPEAT раз: 541 против ~10 260 картинок
#    DsPCBSD+ — без балансировки модель «забудет» домен целых плат.
#  - id классов DsPCBSD+ (порядок подтверждён COCO-категориями SH..BMFO
#    и inspector.py автора): short, spur, spurious_copper, open, mouse_bite,
#    hole_breakout, conductor_scratch, conductor_foreign_object,
#    base_material_foreign_object -> канонические id ниже.
# ============================================================

import shutil
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKU = ROOT / "ml" / "data" / "pku"
DSP = ROOT / "ml" / "data" / "dspcbsd_raw" / "Data_YOLO"
DST = ROOT / "ml" / "data" / "merged"
PKU_REPEAT = 8

# Канонические классы объединённого датасета (0-5 = PKU как есть)
CANONICAL = [
    "missing_hole",                # 0
    "mouse_bite",                  # 1
    "open_circuit",                # 2
    "short",                       # 3
    "spur",                        # 4
    "spurious_copper",             # 5
    "hole_breakout",               # 6  (DsPCBSD+)
    "conductor_scratch",           # 7  (DsPCBSD+)
    "conductor_foreign_object",    # 8  (DsPCBSD+)
    "base_material_foreign_object",# 9  (DsPCBSD+)
]

# id класса в DsPCBSD+ -> канонический id
DSP_TO_CANONICAL = {
    0: 3,  # short
    1: 4,  # spur
    2: 5,  # spurious_copper
    3: 2,  # open
    4: 1,  # mouse_bite
    5: 6,  # hole_breakout
    6: 7,  # conductor_scratch
    7: 8,  # conductor_foreign_object
    8: 9,  # base_material_foreign_object
}


def rewrite_label(src: Path, dst: Path, class_map: dict[int, int] | None):
    """Копирует label-файл, при class_map заменяет id класса."""
    if class_map is None:
        shutil.copy(src, dst)
        return
    lines = []
    for line in src.read_text().splitlines():
        parts = line.split()
        if not parts:
            continue
        parts[0] = str(class_map[int(parts[0])])
        lines.append(" ".join(parts))
    dst.write_text("\n".join(lines) + ("\n" if lines else ""))


def copy_pair(img: Path, lbl: Path, dst_img: Path, dst_lbl: Path,
              class_map: dict[int, int] | None, stats: Counter):
    shutil.copy(img, dst_img)
    rewrite_label(lbl, dst_lbl, class_map)
    for line in dst_lbl.read_text().splitlines():
        if line.strip():
            stats[CANONICAL[int(line.split()[0])]] += 1


def main():
    for split in ("train", "val"):
        (DST / "images" / split).mkdir(parents=True, exist_ok=True)
        (DST / "labels" / split).mkdir(parents=True, exist_ok=True)

    stats = Counter()

    # ---- val: только PKU board-disjoint, без дублирования ----
    n_val = 0
    for img in sorted((PKU / "images" / "val").glob("*.jpg")):
        lbl = PKU / "labels" / "val" / (img.stem + ".txt")
        copy_pair(img, lbl, DST / "images" / "val" / img.name,
                  DST / "labels" / "val" / lbl.name, None, stats)
        n_val += 1

    # ---- train: PKU x PKU_REPEAT + весь DsPCBSD+ (их train и val) ----
    n_pku = 0
    for img in sorted((PKU / "images" / "train").glob("*.jpg")):
        lbl = PKU / "labels" / "train" / (img.stem + ".txt")
        for r in range(1, PKU_REPEAT + 1):
            suffix = "" if r == 1 else f"_r{r}"
            copy_pair(img, lbl, DST / "images" / "train" / f"{img.stem}{suffix}.jpg",
                      DST / "labels" / "train" / f"{img.stem}{suffix}.txt", None, stats)
            n_pku += 1

    n_dsp = 0
    skipped = 0
    for sub in ("train", "val"):
        for img in sorted((DSP / "images" / sub).glob("*.jpg")):
            lbl = DSP / "labels" / sub / (img.stem + ".txt")
            if not lbl.exists():  # единичные картинки без разметки
                skipped += 1
                continue
            copy_pair(img, lbl, DST / "images" / "train" / f"dsp_{img.stem}.jpg",
                      DST / "labels" / "train" / f"dsp_{img.stem}.txt",
                      DSP_TO_CANONICAL, stats)
            n_dsp += 1

    print(f"val:   {n_val} пар (PKU board-disjoint)")
    print(f"train: {n_pku} пар (PKU x{PKU_REPEAT}) + {n_dsp} пар (DsPCBSD+) = {n_pku + n_dsp}")
    if skipped:
        print(f"пропущено без разметки: {skipped}")
    print("\nобъекты по классам (train+val):")
    for i, name in enumerate(CANONICAL):
        print(f"  {i}: {name:30s} {stats[name]}")
    print(f"\nВсего: {sum(stats.values())} объектов")
    print("Готово:", DST)


if __name__ == "__main__":
    main()
