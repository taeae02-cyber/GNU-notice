@echo off
cd /d "%~dp0"
echo [GNU notice crawler] installing libraries (first time only)...
python -m pip install -q -r requirements.txt
echo [GNU notice crawler] running...
python crawl.py %*
echo.
echo Done. Press any key to close.
pause >nul
