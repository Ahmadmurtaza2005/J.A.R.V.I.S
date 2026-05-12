@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv311\Scripts\python.exe" (
    echo Creating virtual environment...
    py -3.11 -m venv .venv311 2>nul
    if errorlevel 1 python -m venv .venv311
)

call ".venv311\Scripts\activate.bat"
python -m pip install --upgrade pip -q
pip install -q -r requirements.txt
pip install -q PyAudio 2>nul

echo Starting Jarvis...
python jarvis.py
pause
