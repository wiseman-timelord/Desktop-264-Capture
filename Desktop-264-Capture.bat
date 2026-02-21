@echo off
:: Desktop-264-Capture – Windows 8.1+ / Python 3.11
setlocal enabledelayedexpansion

REM ==== Admin Check ====
net session >nul 2>&1
if %errorLevel% NEQ 0 (
    echo Error: Admin Required!
    timeout /t 2 >nul
    echo Right Click, Run As Administrator.
    timeout /t 2 >nul
    goto :end_of_script_console
)
echo Status: Administrator
timeout /t 1 >nul

REM Fix working Dir
cd /d "%~dp0"

REM ==== Static Configuration ====
set "TITLE=Desktop-264-Record"
title %TITLE%
mode con cols=80 lines=30
powershell -noprofile -command "& { $w = $Host.UI.RawUI; $b = $w.BufferSize; $b.Height = 6000; $w.BufferSize = $b; }"

set "VENV=.venv"
set "PY=%VENV%\Scripts\python.exe"

:MAIN_MENU
cls
echo ===============================================================================
echo    Desktop-264-Capture: Batch Menu
echo ===============================================================================
echo.
echo.
echo.
echo.
echo.
echo.
echo.
echo.
echo.
echo.
echo    1) Launch Desktop-264-Capture
echo.
echo    2) Install Requirements
echo.
echo.
echo.
echo.
echo.
echo.
echo.
echo.
echo.
echo -------------------------------------------------------------------------------
set /p choice="Selection; Menu Options = 1-2, Quit = Q: "

if /i "%choice%"=="1" goto LAUNCH
if /i "%choice%"=="2" goto INSTALL
if /i "%choice%"=="Q" exit /b 0

echo Invalid selection.
pause
goto MAIN_MENU

:LAUNCH
if not exist "%PY%" (
    echo.
    echo  Virtual environment not found. Run option 2 first.
    echo.
    pause
    goto MAIN_MENU
)
call "%VENV%\Scripts\activate.bat"
"%PY%" launcher.py
goto MAIN_MENU

:INSTALL
python "%~dp0installer.py"
goto MAIN_MENU
