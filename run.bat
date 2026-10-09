@echo off
REM F1: check Ollama and the port, activate the virtual environment, start uvicorn on 127.0.0.1, open the browser.
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
  echo Virtual environment not found. Follow the first-time setup in README.md.
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
python -m app.main --preflight
if errorlevel 1 (
  pause
  exit /b 1
)
python -m app.main
