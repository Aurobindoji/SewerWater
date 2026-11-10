@echo off
rem The app in the browser: double-click to start; http://127.0.0.1:8764 opens (choose language and module there).
rem Only the module chosen starts (sewer 8765, water 8766); the other from its button on the page (start_ui.py).
rem Keep this window open while working; close it (or Ctrl+C) to stop.
cd /d "%~dp0"
".venv\Scripts\python.exe" start_ui.py
pause
