@echo off
color 0B
echo ============================================================
echo   ONE-CLICK LOCAL SETUP
echo   Enterprise Asset Management -- Backend
echo ============================================================
echo.

cd /d "%~dp0"

echo [1/6] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed. Get it from https://www.python.org/downloads/
    echo IMPORTANT: check "Add Python to PATH" during install.
    pause
    exit /b 1
)
python --version

echo.
echo [2/6] Setting up a virtual environment...
if not exist venv (
    python -m venv venv
)
call venv\Scripts\activate.bat

echo.
echo [3/6] Installing dependencies (this can take a minute)...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Dependency install failed -- scroll up for details.
    pause
    exit /b 1
)

echo.
echo [4/6] Preparing configuration (.env)...
python setup_helper.py generate_env

echo.
echo [5/6] Setting up the database...
python manage.py makemigrations core
python manage.py migrate
if errorlevel 1 (
    echo [ERROR] Database setup failed -- scroll up for details.
    pause
    exit /b 1
)

echo.
echo [6/6] Admin account...
python setup_helper.py ensure_superuser

python setup_helper.py show_summary

echo.
echo Starting the server now -- KEEP THIS WINDOW OPEN while using the app.
echo Press Ctrl+C here to stop it later.
echo.
python manage.py runserver
