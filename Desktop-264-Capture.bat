@echo off
:: Desktop-264-Capture – Windows 8.1+ / Python 3.11
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "VENV=.venv"
set "PY=%VENV%\Scripts\python.exe"

:MAIN_MENU
cls
echo ===============================================================================
echo    Desktop-264-Capture: Batch Menu
echo ===============================================================================
echo.
echo    1) Launch Desktop-264-Capture
echo.
echo    2) Install Requirements (fresh every time)
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
if exist "%VENV%" (
    echo  Removing old virtual environment...
    rmdir /s /q "%VENV%" >nul 2>&1
)
echo Running installer...
python "%~dp0installer.py"
echo.
echo Installer finished.
pause
goto MAIN_MENU