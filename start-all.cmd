@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo   LungTic + CodexBridge WeChat
echo ==========================================
echo.

echo [1/2] Starting Python backend...
start "LungTic Backend" cmd /c "cd /d backend && python main.py"
echo   Backend launched in new window.

echo [2/2] Starting WeChat bridge...
start "CodexBridge WeChat" cmd /c "cd /d backend\wx && serve-weixin.cmd"
echo   WeChat bridge launched in new window.

echo.
echo ==========================================
echo All services are starting...
echo - Backend:  http://127.0.0.1:8000
echo - WeChat:   CodexBridge iLink bridge
echo ==========================================
echo.
echo Close the windows or press Ctrl+C in each to stop.
pause
