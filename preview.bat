@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Install Python and add it to PATH.
    pause >nul
    exit /b 1
)
echo Browser: http://127.0.0.1:8000/index.html
echo To stop the server, press Ctrl+C.
start "" http://127.0.0.1:8000/index.html
python -m http.server 8000 --bind 127.0.0.1
pause >nul
