@echo off
setlocal
chcp 65001 >nul
title German Compound Clinic - dev server

rem Always run from the folder this file lives in (works with non-ASCII paths).
cd /d "%~dp0"

where node >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Node.js was not found. Install it from https://nodejs.org and try again.
  pause
  exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python was not found. Install Python 3.10+ from https://www.python.org and try again.
  pause
  exit /b 1
)

if not exist "node_modules\" (
  echo Installing web dependencies...
  call npm install
  if errorlevel 1 (
    echo [ERROR] npm install failed.
    pause
    exit /b 1
  )
)

if not exist "nlp\.venv\Scripts\python.exe" (
  echo Creating Python environment and installing NLP libraries... (first run only, a few minutes)
  python -m venv nlp\.venv
  if errorlevel 1 (
    echo [ERROR] Could not create the Python virtual environment.
    pause
    exit /b 1
  )
  nlp\.venv\Scripts\python.exe -m pip install --upgrade pip
  nlp\.venv\Scripts\python.exe -m pip install -r nlp\requirements.txt
  if errorlevel 1 (
    echo [ERROR] pip install failed.
    pause
    exit /b 1
  )
)

rem Start the NLP service (translator + per-language libraries) in its own window.
start "German NLP service" cmd /c ""%~dp0nlp\run-nlp.bat""

rem Open the browser a few seconds after the servers start.
start "" /b cmd /c "timeout /t 8 /nobreak >nul & start "" http://localhost:3000"

echo Starting web server at http://localhost:3000
echo Code changes (web and Python) are applied instantly - no restart needed.
echo Press Ctrl+C to stop the web server. Close the "German NLP service" window to stop the analyzer.
echo.

:run
call npm run dev
echo.
echo [WARN] The dev server stopped. Restarting in 3 seconds... (close this window to quit)
timeout /t 3 /nobreak >nul
goto run
