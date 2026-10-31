@echo off
rem Start Utter without a console window. First-time setup: see README.md.
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Utter is not installed yet. See README.md for setup steps.
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m utter run
