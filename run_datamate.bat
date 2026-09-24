@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo           Starting DataMate AI
echo ========================================

if not exist "venv\Scripts\python.exe" (
  echo Creating virtual environment...
  python -m venv venv
  if errorlevel 1 (
    echo.
    echo Could not create the virtual environment.
    echo Make sure Python is installed and available as the python command.
    pause
    exit /b 1
  )
)

call "venv\Scripts\activate.bat"

echo Installing/updating required packages...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Package installation failed. Check your internet connection and Python installation.
  pause
  exit /b 1
)

echo.
echo Opening DataMate AI...
python -m streamlit run app.py
pause
