@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0"
call "%~dp0scripts\bootstrap.bat"
if errorlevel 1 goto failed
"%~dp0.venv\Scripts\python.exe" "%~dp0launcher.py" %*
if errorlevel 1 goto failed
exit /b 0
:failed
echo Financial Tracker could not start. See the message above or instance\logs.
if not "%FT_NONINTERACTIVE%"=="1" pause
exit /b 1
