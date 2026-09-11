@echo off
start pythonw mortar_calc.py
if %errorlevel% neq 0 (
    python mortar_calc.py
)
