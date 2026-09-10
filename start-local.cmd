@echo off
cd /d "%~dp0"
if not exist "frontend\dist\index.html" (
  echo Run setup-windows.cmd or build-frontend.cmd first.
  pause
  exit /b 1
)
cd backend
echo Open http://127.0.0.1:8000 in your browser. Press Ctrl+C to stop.
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
