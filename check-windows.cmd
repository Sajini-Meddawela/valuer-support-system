@echo off
cd /d "%~dp0backend"
.venv\Scripts\python.exe -m unittest tests.domain_checks -v
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pytest -q
if errorlevel 1 goto failed
cd ..\frontend
call npm run build
if errorlevel 1 goto failed
echo Automated checks passed. Complete the manual checklist before client use.
pause
exit /b 0
:failed
echo A check failed. See the error above.
pause
exit /b 1
