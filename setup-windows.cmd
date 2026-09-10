@echo off
setlocal
cd /d "%~dp0"
py -3.12 --version >nul 2>&1
if errorlevel 1 goto python_missing
where npm >nul 2>&1
if errorlevel 1 goto node_missing
if not exist "backend\.venv\Scripts\python.exe" py -3.12 -m venv backend\.venv
if errorlevel 1 goto failed
backend\.venv\Scripts\python.exe -m pip install --no-cache-dir -r backend\requirements.txt
if errorlevel 1 goto failed
backend\.venv\Scripts\python.exe scripts\setup.py
if errorlevel 1 goto failed
cd frontend
call npm ci
if errorlevel 1 goto failed
call npm run build
if errorlevel 1 goto failed
echo Setup complete. Run start-local.cmd and open http://127.0.0.1:8000
echo For development use start-backend.cmd and start-frontend.cmd instead.
pause
exit /b 0
:python_missing
echo Install Python 3.12 with the Python launcher, then open a new terminal.
goto failed
:node_missing
echo Install Node.js 22.12 or newer in the 22.x series, then open a new terminal.
goto failed
:failed
echo Setup failed. Read the error above, fix it, and run this script again.
pause
exit /b 1
