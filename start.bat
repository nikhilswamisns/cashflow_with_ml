@echo off
echo ==================================================
echo  Starting Cash Flow Forecasting Engine...
echo ==================================================

python --version >nul 2>&1
if errorlevel 1 (
    echo Python is required but not found. Please install Python 3.9+ from python.org.
    pause
    exit /b 1
)

echo Installing / Verifying dependencies...
pip install -r requirements.txt --quiet

echo Launching application server on http://localhost:8000/ui
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
