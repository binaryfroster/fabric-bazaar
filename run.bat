@echo off
echo FabricBazaar Launcher
echo =====================
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)
call venv\Scripts\activate.bat
echo Installing requirements...
pip install -r requirements.txt -q
if not exist fabricbazaar_dev.db (
    echo Seeding database...
    python seed.py
)
echo.
echo Starting server at http://localhost:5000
python app.py
