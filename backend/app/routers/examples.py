# ============================================================
# РОЛЬ: Backend-разработчик
#
# ЧТО ЗДЕСЬ: примеры фото плат для вкладки «Фото».
#   GET /api/examples         — список картинок из папки examples/
#   GET /api/examples/{name}  — сама картинка
# На демо и репетициях не нужно искать файлы по диску: миниатюры
# под зоной загрузки, анализ — в один клик.
#
# БЕЗОПАСНОСТЬ: отдаём только файлы, которые сами нашли в EXAMPLES_DIR
# (имя сверяется со списком) — путь вида "../backend/app/config.py"
# через {name} не пройдёт.
# ============================================================

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import config
from ..schemas import ExampleInfo

router = APIRouter(prefix="/api/examples", tags=["examples"])


def _example_files() -> dict:
    """Имя файла -> путь, только картинки прямо в EXAMPLES_DIR (без подпапок)."""
    if not config.EXAMPLES_DIR.is_dir():
        return {}
    return {
        path.name: path
        for path in sorted(config.EXAMPLES_DIR.iterdir())
        if path.is_file() and path.suffix.lower() in config.EXAMPLE_EXTENSIONS
    }


@router.get("", response_model=list[ExampleInfo])
async def list_examples():
    """Список примеров (пустой, если папки examples/ нет или в ней нет картинок)."""
    return [
        ExampleInfo(name=name, size_kb=round(path.stat().st_size / 1024))
        for name, path in _example_files().items()
    ]


@router.get("/{name}")
async def get_example(name: str):
    """Картинка-пример по имени из списка."""
    path = _example_files().get(name)
    if path is None:
        raise HTTPException(status_code=404, detail=f"Пример '{name}' не найден в папке examples/")
    return FileResponse(path)
