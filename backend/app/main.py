# ============================================================
# РОЛЬ: Backend-разработчик
#
# ЧТО ЗДЕСЬ: точка входа приложения FastAPI.
#   - собирает все роутеры (/api/analyze, /api/frame, /api/models, /api/metrics)
#   - раздаёт фронтенд из ../frontend как статику на "/"
#   - CORS для гибридного режима (фронт на localhost, API удалённо)
#   - /api/health для проверки живости
#
# ЗАПУСК из корня репозитория:
#   uvicorn backend.app.main:app --reload --port 8000
# После старта: http://localhost:8000 — сайт, http://localhost:8000/docs — Swagger.
#
# ЧТО СДЕЛАТЬ (TODO):
# 1. Настроить production-запуск (без --reload) для демо.
# 2. Проверить CORS для схемы "фронт на ноутбуке + API на домашнем ПК"
#    (см. docs/ARCHITECTURE.md, раздел про удалённый сервер).
# ============================================================

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .model_manager import manager
from .routers import analyze, live, metrics, models

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")

app = FastAPI(
    title="PCB Defect Inspector",
    description="Сервис определения дефектов печатных плат (хакатон, задание 4)",
    version="0.1.0",
)

# CORS: разрешаем всё — на хакатоне к API ходят и с localhost (гибридный режим
# "фронт локально + API на домашнем ПК через Tailscale"), и с удалённых адресов.
# TODO [Backend]: перед "продакшеном" сузить origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", tags=["health"])
async def health():
    """Проверка живости: активно ли API, какая модель, есть ли ML-библиотеки."""
    try:
        import ultralytics  # noqa: F401
        ml_available = True
    except ImportError:
        ml_available = False
    return {
        "status": "ok",
        "active_model": manager.active_id,
        "mock_mode": manager.active_id == "mock",
        "ml_dependencies": ml_available,
    }


# Роутеры API (порядок важен: они должны быть раньше монтирования статики)
app.include_router(analyze.router)
app.include_router(live.router)
app.include_router(models.router)
app.include_router(metrics.router)


# Фронтенд — статикой из ../frontend, html=True означает "отдавать index.html на /"
frontend_dir = config.PROJECT_ROOT / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
else:
    @app.get("/")
    async def no_frontend():
        return JSONResponse(
            {"warning": "Папка frontend/ не найдена — бэкенд работает, но сайта нет"},
        )
