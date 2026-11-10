@echo off
rem Builds the setup of the desktop app: dist\SewerWater_Setup.exe - everything in one file (the app packed by
rem PyInstaller and Microsoft's WebView2 bootstrapper). Needs Inno Setup 6 (winget install JRSoftware.InnoSetup).
cd /d "%~dp0"
".venv\Scripts\python.exe" -m PyInstaller SewerWater.spec --noconfirm || goto :fail
if not exist "installer\redist\MicrosoftEdgeWebview2Setup.exe" (
  mkdir "installer\redist" 2>nul
  powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile 'installer\redist\MicrosoftEdgeWebview2Setup.exe' -UseBasicParsing" || goto :fail
)
set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (echo Inno Setup 6 not found - winget install JRSoftware.InnoSetup & goto :fail)
rem the version: launcher\about.py APP_VERSION, the one place of it (the app's About and its update check read it)
for /f "usebackq delims=" %%v in (`".venv\Scripts\python.exe" -c "from launcher.about import APP_VERSION as v; print(v)"`) do set "APPVER=%%v"
if "%APPVER%"=="" (echo version not read from launcher\about.py & goto :fail)
"%ISCC%" /DAppVersion=%APPVER% installer\SewerWater.iss || goto :fail
echo.
echo Setup: dist\SewerWater_Setup_%APPVER%.exe
pause
exit /b 0
:fail
echo.
echo *** build failed
pause
exit /b 1
