@echo off
setlocal
chcp 65001 >nul
title German Compound Clinic - NLP service (port 8000)
cd /d "%~dp0"

:run
echo Starting NLP service at http://127.0.0.1:8000  (auto-reloads when Python files change)
".venv\Scripts\python.exe" -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload
echo.
echo [WARN] The NLP service stopped. Restarting in 3 seconds... (close this window to quit)
timeout /t 3 /nobreak >nul
goto run
