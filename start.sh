#!/bin/bash
echo "=================================================="
echo " Starting Cash Flow Forecasting Engine..."
echo "=================================================="

if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required but not found. Please install Python 3.9+."
    exit 1
fi

echo "Installing / Verifying dependencies..."
pip3 install -r requirements.txt --quiet

if lsof -i :8000 &> /dev/null; then
    echo "Port 8000 is already running. Stopping previous instance..."
    lsof -ti :8000 | xargs kill -9 2>/dev/null || true
    sleep 1
fi

echo "Launching application server on http://localhost:8000/ui"
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
