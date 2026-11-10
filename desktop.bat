@echo off
rem The map UI as a desktop app: a window of its own (no browser); choosing water opens it in a second window.
rem Close every window of the app to stop it. (sewer_ui.bat: the same pages in the browser.)
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" app.py
