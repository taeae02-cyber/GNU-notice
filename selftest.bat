@echo off
cd /d "%~dp0"
python -m pip install -q -r requirements.txt
python tools\selftest.py
echo.
echo Press any key to close.
pause >nul
