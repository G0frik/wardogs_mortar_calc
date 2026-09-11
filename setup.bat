@echo off
title War Dogs Mortar Calculator - Setup
echo ====================================================
echo  War Dogs Mortar Calculator - Setup
echo ====================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not detected on your system.
    echo.
    echo 1. Download Python 3.10+ from https://www.python.org/downloads/
    echo 2. During installation, CHECK the box: "Add python.exe to PATH"
    echo 3. Run this setup.bat again after installing.
    echo.
    pause
    exit /b 1
)

echo [*] Python detected:
python --version
echo.
echo [*] Installing required libraries...
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Installation failed. Please check your internet connection.
    pause
    exit /b 1
)

echo.
echo ====================================================
echo  [SUCCESS] Setup finished successfully!
echo  Double-click "launch.bat" to start the calculator.
echo ====================================================
echo.
pause
