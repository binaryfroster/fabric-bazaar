@echo off
echo ========================================
echo   FabricBazaar Marketplace Setup
echo ========================================
python -m venv venv
call venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
echo.
echo NOTE: Open .env and add a SECRET_KEY
echo Then run: python seed.py
echo Then run: python app.py
pause
