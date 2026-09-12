@echo off
cd /d "%~dp0"
start "" pythonw mortar_calc.py
if %errorlevel% neq 0 (
    start "" python mortar_calc.py
)
