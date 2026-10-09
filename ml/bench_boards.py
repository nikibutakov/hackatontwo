# По-платная проверка на утечку: если YOLO26 обучалась на наших валидационных
# платах, её метрика на "своих" платах будет ~0.99, на "чужой" - заметно ниже.
from pathlib import Path
from ultralytics import YOLO

ROOT = Path("ml/data/pku").resolve()
m26 = YOLO("ml/weights/hf_yolo26_pku.pt")
v1 = YOLO("ml/weights/pcb_yolov8s.pt")

for board in ("10", "11", "12"):
    names = sorted(p.name for p in (ROOT / "images/val").glob(f"{board}_*.jpg"))
    lst = ROOT / f"board_{board}.txt"
    lst.write_text("\n".join(str(ROOT / "images/val" / n) for n in names))
    yaml = ROOT / f"board_{board}.yaml"
    yaml.write_text(
        f"path: {ROOT}\ntrain: board_{board}.txt\nval: board_{board}.txt\n"
        "nc: 6\nnames:\n  0: missing_hole\n  1: mouse_bite\n  2: open_circuit\n"
        "  3: short\n  4: spur\n  5: spurious_copper\n")
    r26 = m26.val(data=str(yaml), imgsz=640, verbose=False, plots=False, device=0, workers=0)
    r8 = v1.val(data=str(yaml), imgsz=960, verbose=False, plots=False, device=0, workers=0)
    print(f"плата {board} ({len(names)} фото): YOLO26 mAP50={r26.box.map50:.3f} | наша v1 mAP50={r8.box.map50:.3f}", flush=True)
