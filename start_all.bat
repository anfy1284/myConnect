@echo off
cd /d "%~dp0"
echo Stopping old processes...
taskkill /F /IM python.exe
echo Starting Server...
cd server
start /B python main.py
cd ..
timeout /t 2
echo Starting Client...
cd client
start /B python main.py
echo Done.
pause
