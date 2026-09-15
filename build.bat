@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0"
call "%~dp0scripts\bootstrap.bat"
if errorlevel 1 goto failed
"%~dp0.venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r "%~dp0requirements-build.txt"
if errorlevel 1 goto failed
"%~dp0.venv\Scripts\python.exe" "%~dp0scripts\build_notices.py"
if errorlevel 1 goto failed
"%~dp0.venv\Scripts\python.exe" "%~dp0scripts\build_metadata.py"
if errorlevel 1 goto failed
"%~dp0.venv\Scripts\python.exe" -m PyInstaller --noconfirm "%~dp0FinancialTracker.spec"
if errorlevel 1 goto failed
"%~dp0.venv\Scripts\python.exe" "%~dp0scripts\package_release.py"
if errorlevel 1 goto failed
echo Build ready: dist\FinancialTracker\FinancialTracker.exe
echo Copy the ENTIRE dist\FinancialTracker folder to another Windows computer.
if not "%FT_NONINTERACTIVE%"=="1" pause
exit /b 0
:failed
echo Build failed. Please read the error above.
if not "%FT_NONINTERACTIVE%"=="1" pause
exit /b 1
