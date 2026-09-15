@echo off
rem Paths are always quoted; delayed expansion stays disabled for paths with !.
setlocal
cd /d "%~dp0.."
set "TRACKER_ROOT=%CD%"
if exist "%TRACKER_ROOT%\.venv\Scripts\python.exe" (
  "%TRACKER_ROOT%\.venv\Scripts\python.exe" -c "import sys; assert sys.version_info >= (3,11)" >nul 2>&1
  if not errorlevel 1 goto environment_ready
  echo The copied virtual environment is not usable on this computer.
  echo Preserving it as .venv-old. Your database will not be changed.
  if exist "%TRACKER_ROOT%\.venv-old" (
    echo Please rename .venv or .venv-old manually and retry.
    exit /b 1
  )
  ren "%TRACKER_ROOT%\.venv" ".venv-old"
  if errorlevel 1 exit /b 1
)
if defined FINANCIAL_TRACKER_PYTHON (
  "%FINANCIAL_TRACKER_PYTHON%" -c "import sys; assert sys.version_info >= (3,11)" >nul 2>&1
  if not errorlevel 1 (
    "%FINANCIAL_TRACKER_PYTHON%" -m venv "%TRACKER_ROOT%\.venv"
    goto check_environment
  )
)
py -3 -c "import sys; assert sys.version_info >= (3,11)" >nul 2>&1
if not errorlevel 1 (
  py -3 -m venv "%TRACKER_ROOT%\.venv"
  goto check_environment
)
python -c "import sys; assert sys.version_info >= (3,11)" >nul 2>&1
if not errorlevel 1 (
  python -m venv "%TRACKER_ROOT%\.venv"
  goto check_environment
)
echo Python is not installed, or Python 3.11+ was not found.
echo Install Python from https://www.python.org/downloads/windows/
echo Enable "Add python.exe to PATH", then double-click setup.bat again.
echo Or use the standalone FinancialTracker.exe build; it does not need Python.
exit /b 1
:check_environment
if not exist "%TRACKER_ROOT%\.venv\Scripts\python.exe" exit /b 1
:environment_ready
"%TRACKER_ROOT%\.venv\Scripts\python.exe" "%TRACKER_ROOT%\scripts\ensure_dependencies.py"
if errorlevel 1 exit /b 1
rem launcher.py applies migrations while holding the single-instance lock.
rem setup also supports initialization without starting the browser.
exit /b 0
