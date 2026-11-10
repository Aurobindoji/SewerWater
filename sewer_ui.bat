@echo off
rem Map UI: double-click to start; the browser opens http://127.0.0.1:8765 (choose language and module there).
rem Sewer and water run on their own servers: sewer 8765, water 8766 (start_ui.py starts both).
rem Keep this window open while working; close it (or Ctrl+C) to stop.
cd /d "%~dp0"
".venv\Scripts\python.exe" start_ui.py
pause
