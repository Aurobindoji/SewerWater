@echo off
rem Water module alone: double-click to start; the browser opens http://127.0.0.1:8766/water
rem Keep this window open while working; close it (or Ctrl+C) to stop.
cd /d "%~dp0"
".venv\Scripts\python.exe" -m water_app ui
pause
