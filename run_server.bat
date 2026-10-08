@echo off
rem ============================================================
rem Запуск сервера PCB Defect Inspector с автоперезапуском.
rem Планировщик задач запускает этот файл при входе в систему
rem (задача "PCB-Server"). При падении uvicorn цикл поднимает
rem его заново через 5 секунд. Остановить: закрыть окно
rem или `taskkill /f /im python.exe` (осторожно - убьёт все python).
rem ============================================================
cd /d E:\Hackaton
set USE_MOCK=false
:loop
.venv-ml\Scripts\python.exe -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
echo [%date% %time%] сервер упал, перезапуск через 5 секунд...
timeout /t 5 /nobreak >nul
goto loop
