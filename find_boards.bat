@echo off
cd /d "%~dp0"
python -m pip install -q -r requirements.txt
echo Finding notice boards of every college/department site (3-5 min)...
python tools\find_boards.py %*
echo.
echo Press any key to close.
pause >nul
