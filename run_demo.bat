@echo off
chcp 65001 >nul
rem ============================================================
rem  Запуск демо-стенда (Windows). Двойной клик или из консоли:
rem    run_demo.bat         - реальные модели (USE_MOCK=false)
rem    run_demo.bat mock    - заглушка, без ML (проверка фронтенда)
rem
rem  1. предполётная проверка (scripts\check_demo.py), при ошибках - стоп;
rem  2. сервер БЕЗ --reload, на всех интерфейсах (0.0.0.0) - чтобы
rem     работал доступ через Tailscale / Cloudflare Tunnel;
rem  3. ровно ОДИН воркер: модель, активная модель и сглаживание потока
rem     живут в памяти процесса - с несколькими воркерами переключение
rem     моделей и сглаживание работали бы "через раз";
rem  4. без access-лога: камера шлёт 5-15 запросов в секунду, лог
rem     забивал бы консоль и отнимал время.
rem
rem  Сайт: http://localhost:8000   Swagger: http://localhost:8000/docs
rem ============================================================
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [!] Нет виртуального окружения .venv. Создайте его:
  echo     python -m venv .venv
  echo     .venv\Scripts\pip install -r requirements.txt -r ml\requirements-ml.txt
  pause
  exit /b 1
)

if /i "%~1"=="mock" (set "USE_MOCK=true") else (set "USE_MOCK=false")

".venv\Scripts\python.exe" scripts\check_demo.py
if errorlevel 1 (
  echo.
  echo Запуск остановлен: исправьте пункты с крестиком выше.
  pause
  exit /b 1
)

echo.
echo Запускаю сервер: http://localhost:8000  (остановка - Ctrl+C)
".venv\Scripts\python.exe" -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log
pause
