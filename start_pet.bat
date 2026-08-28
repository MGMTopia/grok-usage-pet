@echo off
setlocal
set "LOGDIR=%LOCALAPPDATA%\GrokUsagePet"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
echo %DATE% %TIME% start_pet.bat >> "%LOGDIR%\launch.log"
schtasks /Run /TN GrokUsagePetLaunch >> "%LOGDIR%\launch.log" 2>&1
if errorlevel 1 (
  echo fallback start >> "%LOGDIR%\launch.log"
  start "" "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" "D:\ai\pet.py"
)
exit /b 0
