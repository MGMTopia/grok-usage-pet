@echo off
setlocal
set "LOGDIR=%LOCALAPPDATA%\GrokUsagePetKawaii"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
echo %DATE% %TIME% start_pet.bat kawaii >> "%LOGDIR%\launch.log"
schtasks /Run /TN GrokUsagePetKawaiiLaunch >> "%LOGDIR%\launch.log" 2>&1
if errorlevel 1 (
  echo fallback exe >> "%LOGDIR%\launch.log"
  start "" "%~dp0GrokUsagePetKawaii.exe"
)
exit /b 0
