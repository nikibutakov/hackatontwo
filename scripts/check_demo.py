# ============================================================
# РОЛЬ: Backend-разработчик (запускают все перед демо)
#
# ЧТО ЗДЕСЬ: предполётная проверка демо-стенда. Ловит до выступления
# то, что иначе всплывёт на сцене: нет весов, не те зависимости,
# занят порт, метрики-заглушки, медленный инференс.
#
# ЗАПУСК из корня репозитория (run_demo.bat вызывает его сам):
#   python scripts/check_demo.py            # проверки без загрузки модели
#   python scripts/check_demo.py --bench    # + загрузить активную модель
#                                           #   и замерить скорость инференса
# Режим берётся из переменной USE_MOCK, как у сервера.
#
# Код возврата: 0 — можно запускать (возможны ⚠), 1 — есть ✗.
# ============================================================

import argparse
import importlib.util
import json
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Консоль Windows по умолчанию не в UTF-8 — без этого значки и кириллица "ломаются"
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from backend.app import config  # noqa: E402  (после правки sys.path)

OK, WARN, FAIL = "✓", "⚠", "✗"
results: list[tuple[str, str, str]] = []


def report(status: str, title: str, details: str = "") -> None:
    results.append((status, title, details))
    print(f"  {status} {title}" + (f" — {details}" if details else ""))


def has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def check_python() -> None:
    v = sys.version_info
    status = OK if v >= (3, 10) else FAIL
    report(status, f"Python {v.major}.{v.minor}.{v.micro}", "" if status == OK else "нужен 3.10+")


def check_core_deps() -> None:
    missing = [m for m in ("fastapi", "uvicorn", "PIL", "multipart", "pydantic") if not has_module(m)]
    if missing:
        report(FAIL, "Зависимости бэкенда", "нет: " + ", ".join(missing) + " -> pip install -r requirements.txt")
    else:
        report(OK, "Зависимости бэкенда")


def check_mode_and_models() -> None:
    if config.USE_MOCK:
        report(WARN, "Режим ЗАГЛУШКИ (USE_MOCK=true)", "детекции фейковые — для демо запускайте run_demo.bat без mock")
        return
    report(OK, "Режим реальных моделей (USE_MOCK=false)")

    if not has_module("ultralytics"):
        report(FAIL, "ultralytics не установлен", "pip install -r ml/requirements-ml.txt")
    else:
        report(OK, "ultralytics установлен")

    if has_module("torch"):
        import torch
        if torch.cuda.is_available():
            report(OK, "GPU (CUDA)", torch.cuda.get_device_name(0))
        else:
            report(WARN, "GPU не найден — инференс на CPU", "проверьте FPS: python scripts/check_demo.py --bench")

    ids = [m["id"] for m in config.MODEL_REGISTRY]
    if config.ACTIVE_MODEL not in ids:
        report(FAIL, f"ACTIVE_MODEL '{config.ACTIVE_MODEL}' нет в MODEL_REGISTRY", f"есть: {ids}")
    for entry in config.MODEL_REGISTRY:
        path = ROOT / entry["path"]
        active = " (активная)" if entry["id"] == config.ACTIVE_MODEL else ""
        if path.is_file():
            report(OK, f"Веса {entry['id']}{active}", f"{path.stat().st_size / 1e6:.0f} МБ")
        else:
            # без весов активной модели демо не работает, без весов запасной — только переключение
            report(FAIL if active else WARN, f"Нет весов {entry['id']}{active}", f"ожидаются в {entry['path']}")


def check_metrics() -> None:
    try:
        models = json.loads(config.METRICS_FILE.read_text(encoding="utf-8"))["models"]
    except FileNotFoundError:
        report(WARN, "ml/metrics.json не найден", "вкладка «Метрики» будет пустой")
        return
    except Exception as exc:
        report(FAIL, "ml/metrics.json не читается", str(exc))
        return
    placeholders = [mid for mid, m in models.items() if m.get("placeholder")]
    if placeholders:
        report(WARN, "Метрики-заглушки", "placeholder: true у " + ", ".join(placeholders))
    else:
        report(OK, "Метрики", f"моделей: {len(models)}")
    registry = {m["id"] for m in config.MODEL_REGISTRY}
    unknown = [mid for mid in models if mid not in registry]
    if unknown and not config.USE_MOCK:
        report(WARN, "В metrics.json есть модели не из реестра", ", ".join(unknown) + " — «активна» не будет помечена")


def check_examples() -> None:
    count = 0
    if config.EXAMPLES_DIR.is_dir():
        count = sum(1 for p in config.EXAMPLES_DIR.iterdir()
                    if p.is_file() and p.suffix.lower() in config.EXAMPLE_EXTENSIONS)
    if count:
        report(OK, "Примеры фото", f"{count} шт. в examples/")
    else:
        report(WARN, "Нет примеров фото", "положите 3–5 снимков в examples/ (см. examples/README.md)")


def check_frontend() -> None:
    index = ROOT / "frontend" / "index.html"
    report(OK if index.is_file() else FAIL, "Фронтенд", "" if index.is_file() else "нет frontend/index.html")


def check_port(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        busy = s.connect_ex(("127.0.0.1", port)) == 0
    if busy:
        report(FAIL, f"Порт {port} занят", "сервер уже запущен? Закройте его или выберите другой порт")
    else:
        report(OK, f"Порт {port} свободен")


def bench(runs: int = 10) -> None:
    """Загрузка активной модели и замер инференса на кадре 640×480 — оценка FPS камеры."""
    from PIL import Image
    from backend.app.model_manager import manager

    model = manager.get_active()
    t0 = time.perf_counter()
    try:
        model.load()
    except Exception as exc:
        report(FAIL, f"Модель {model.model_id} не загрузилась", str(exc))
        return
    report(OK, f"Модель {model.model_id} загружена", f"{time.perf_counter() - t0:.1f} с")

    frame = Image.new("RGB", (640, 480), (30, 90, 45))
    model.predict(frame)  # первый прогон — прогрев, в замер не входит
    times = []
    for _ in range(runs):
        t = time.perf_counter()
        model.predict(frame)
        times.append((time.perf_counter() - t) * 1000)
    avg = sum(times) / len(times)
    fps = 1000 / avg
    # цель из docs/PLAN.md — хотя бы 4 FPS на потоке (сеть и JPEG съедят ещё часть)
    status = OK if fps >= 6 else WARN if fps >= 4 else FAIL
    report(status, "Скорость инференса", f"{avg:.0f} мс/кадр ≈ {fps:.1f} FPS (цель ≥ 4–6)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Предполётная проверка демо-стенда")
    parser.add_argument("--bench", action="store_true", help="загрузить модель и замерить скорость")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    print("\nПроверка демо-стенда PCB Defect Inspector\n")
    check_python()
    check_core_deps()
    check_mode_and_models()
    check_metrics()
    check_examples()
    check_frontend()
    check_port(args.port)
    if args.bench:
        bench()

    fails = sum(1 for s, _, _ in results if s == FAIL)
    warns = sum(1 for s, _, _ in results if s == WARN)
    print()
    if fails:
        print(f"{FAIL} Есть проблемы: {fails}. Исправьте их до запуска демо.")
        return 1
    print(f"{OK} Можно запускать" + (f" (предупреждений: {warns})" if warns else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
