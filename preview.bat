@echo off
cd /d "%~dp0docs"
echo Preview server: http://localhost:8000  (close this window to stop)
start "" http://localhost:8000
python -m http.server 8000
