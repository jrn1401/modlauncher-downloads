@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem Bevorzugt eine bewaehrte Python-Version (3.13, 3.12, 3.11, 3.14), sonst die neueste vorhandene.
set "PY="
for %%V in (3.13 3.12 3.11 3.14) do (
  if not defined PY (
    py -%%V --version >nul 2>&1 && set "PY=py -%%V"
  )
)
if not defined PY py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY (
  python --version >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo Python wurde nicht gefunden.
  echo Bitte von https://www.python.org/downloads/ installieren und dabei "Add Python to PATH" anhaken.
  pause
  exit /b 1
)
echo Verwende: %PY%
%PY% --version

if not exist ".venv-build\Scripts\python.exe" (
  %PY% -m venv .venv-build
  if errorlevel 1 (
    echo Konnte die Python-Umgebung nicht anlegen.
    pause
    exit /b 1
  )
)
.venv-build\Scripts\python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 (
  echo Installation fehlgeschlagen. Meldung oben lesen.
  pause
  exit /b 1
)
.venv-build\Scripts\python tools\make_icon.py
.venv-build\Scripts\pyinstaller --noconfirm --clean --noconsole --onefile --name JaronsOPMakro --icon build\icon.ico --collect-all customtkinter --collect-submodules modules --collect-submodules core --collect-submodules pynput main.py
if errorlevel 1 (
  echo Build fehlgeschlagen. Meldung oben lesen.
  pause
  exit /b 1
)
echo.
echo Fertig! Die Datei liegt hier: %~dp0dist\JaronsOPMakro.exe
pause
