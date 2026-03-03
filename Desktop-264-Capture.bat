@echo off
:: Desktop-264-Capture – Windows 8.1+ / Python 3.11
setlocal enabledelayedexpansion
REM ==== Admin Check ====
net session >nul 2>&1
if %errorlevel% NEQ 0 (
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
set "TITLE=Desktop-264-Capture"
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
echo    2) Launch Desktop-264-Capture (debug)
echo.
echo    3) Install Requirements
echo.
echo.
echo.
echo.
echo.
echo.
echo.
echo -------------------------------------------------------------------------------
set /p choice="Selection; Menu Options = 1-3, Quit = Q: "
if /i "%choice%"=="1" goto LAUNCH_NORMAL
if /i "%choice%"=="2" goto LAUNCH_DEBUG
if /i "%choice%"=="3" goto INSTALL
if /i "%choice%"=="Q" exit /b 0
echo Invalid selection.
pause
goto MAIN_MENU

:LAUNCH_NORMAL
cls
echo ===============================================================================
echo    Desktop-264-Capture: Launching (Normal Mode)...
echo ===============================================================================
echo.
echo    The console will close in 3 seconds.
echo    The application will continue running in the background.
echo.
timeout /t 1 >nul
if not exist "%PY%" (
    echo.
    echo  Virtual environment not found. Run option 3 first.
    echo.
    pause
    goto MAIN_MENU
)
REM Start detached so this batch file can exit while Python keeps running
start "" "%PY%" launcher.py
timeout /t 3 >nul
exit /b 0

:LAUNCH_DEBUG
cls
echo ===============================================================================
echo    Desktop-264-Capture: Launching (Debug Mode)...
echo ===============================================================================
echo.
echo    Console will remain open to show logs.
echo    Close the App Window to return to this menu.
echo.
timeout /t 1 >nul
if not exist "%PY%" (
    echo.
    echo  Virtual environment not found. Run option 3 first.
    echo.
    pause
    goto MAIN_MENU
)
call "%VENV%\Scripts\activate.bat"
REM Pass --debug flag to enable verbose logging in launcher.py
"%PY%" launcher.py --debug
goto MAIN_MENU

:INSTALL
cls
echo ===============================================================================
echo    Desktop-264-Capture: Installing...
echo ===============================================================================
echo.
timeout /t 1 >nul
REM Use system python for installer in case venv doesn't exist yet
python "%~dp0installer.py"
goto MAIN_MENU

:end_of_script_console