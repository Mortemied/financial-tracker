@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0"
call "%~dp0scripts\bootstrap.bat" %*
if errorlevel 1 goto failed
"%~dp0.venv\Scripts\python.exe" "%~dp0launcher.py" --setup --no-browser
if errorlevel 1 goto failed
echo Setup complete. Double-click start.bat to open Financial Tracker.
if not "%FT_NONINTERACTIVE%"=="1" pause
exit /b 0
:failed
echo Setup failed. Check the message above and your internet connection.
if not "%FT_NONINTERACTIVE%"=="1" pause
exit /b 1
