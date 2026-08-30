@echo off
setlocal
set "LOGDIR=%LOCALAPPDATA%\GrokUsagePet"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
echo %DATE% %TIME% start_pet.bat >> "%LOGDIR%\launch.log"
schtasks /Run /TN GrokUsagePetLaunch >> "%LOGDIR%\launch.log" 2>&1
if errorlevel 1 (
  echo fallback exe >> "%LOGDIR%\launch.log"
  start "" "%~dp0GrokUsagePet.exe"
)
exit /b 0
