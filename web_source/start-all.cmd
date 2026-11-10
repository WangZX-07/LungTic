@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo   LungTic local development services
echo ==========================================
echo.

echo [1/3] Starting API backend...
start "LungTic API" cmd /k "cd /d backend && python -m uvicorn main:app --host 127.0.0.1 --port 8000"
echo   API launched in a new window.

echo [2/3] Starting clinical client dev server...
start "LungTic Clinical Client" cmd /k "cd /d frontend && npm run dev"
echo   Clinical client launched in a new window.

echo [3/3] Starting administrator dev server...
start "LungTic Admin" cmd /k "cd /d frontend && npm run dev:admin"
echo   Administrator portal launched in a new window.

echo.
echo ==========================================
echo All services are starting...
echo - API:              http://127.0.0.1:8000
echo - Clinical client:  http://127.0.0.1:5173
echo - Admin portal:     check the Vite window (normally 5174)
echo ==========================================
echo.
echo Required backend environment variables must be set before running this script.
echo Close the windows or press Ctrl+C in each to stop.
pause
