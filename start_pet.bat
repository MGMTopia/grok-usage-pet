@echo off
setlocal
set "LOGDIR=%LOCALAPPDATA%\GrokUsagePet"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
echo %DATE% %TIME% start_pet.bat >> "%LOGDIR%\launch.log"
set "PYTHONW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if exist "%PYTHONW%" (
  "%PYTHONW%" "%~dp0pet.py" --hook >> "%LOGDIR%\launch.log" 2>&1
  if not errorlevel 1 exit /b 0
)
schtasks /Run /TN GrokUsagePetLaunch >> "%LOGDIR%\launch.log" 2>&1
if errorlevel 1 (
  echo fallback start >> "%LOGDIR%\launch.log"
  start "" "%PYTHONW%" "%~dp0pet.py"
)
exit /b 0
