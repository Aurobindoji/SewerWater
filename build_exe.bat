@echo off
rem Builds the desktop app without Python: dist\SewerWater\SewerWater.exe (copy the whole folder to another PC).
cd /d "%~dp0"
".venv\Scripts\python.exe" -m PyInstaller SewerWater.spec --noconfirm
pause
