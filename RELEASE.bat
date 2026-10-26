@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  .venv\Scripts\python tools\make_exe_release.py
) else (
  py -3 tools\make_exe_release.py
)
echo.
pause
