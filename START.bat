@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY (
  python --version >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo Python wurde nicht gefunden.
  echo Bitte von https://www.python.org/downloads/ installieren und dabei "Add Python to PATH" anhaken.
  echo Falls Python schon installiert ist: Windows-Einstellungen - Apps - Erweiterte App-Einstellungen -
  echo App-Ausfuehrungsaliase - die Eintraege "python.exe" und "python3.exe" ausschalten.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Einrichtung beim ersten Start, das dauert einen Moment ...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo Konnte die Python-Umgebung nicht anlegen.
    pause
    exit /b 1
  )
  .venv\Scripts\python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Installation fehlgeschlagen. Bitte Internetverbindung pruefen und die Meldung oben lesen.
    rmdir /s /q .venv
    pause
    exit /b 1
  )
)
start "" .venv\Scripts\pythonw.exe main.py
