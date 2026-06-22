@echo off
chcp 65001 >nul
cd /d "%~dp0"
title מנתח הגרפים החכם

echo ============================================
echo      מנתח הגרפים החכם - הפעלה
echo ============================================
echo.

REM בדיקה ש-Python מותקן
where python >nul 2>nul
if errorlevel 1 (
  echo [שגיאה] Python לא מותקן.
  echo התקן מ: https://www.python.org/downloads
  echo חשוב: סמן "Add python.exe to PATH" בהתקנה.
  echo.
  pause
  exit /b
)

REM יצירת סביבה והתקנת ספריות בפעם הראשונה
if not exist .venv (
  echo מתקין ספריות... ^(פעם ראשונה בלבד, ייקח דקה^)
  python -m venv .venv
  call .venv\Scripts\activate.bat
  python -m pip install -q -r requirements.txt
) else (
  call .venv\Scripts\activate.bat
)

REM בקשת מפתח API אם אין קובץ .env
if not exist .env (
  echo.
  echo קבל מפתח חינמי ב: https://aistudio.google.com/apikey
  set /p APIKEY="הדבק כאן את מפתח ה-Gemini שלך: "
  >.env echo GEMINI_API_KEY=%APIKEY%
)

echo.
echo מפעיל את האפליקציה...
echo פתח בדפדפן: http://localhost:5000
echo לעצירה: סגור חלון זה או לחץ Ctrl+C
echo.
start "" http://localhost:5000
python app.py
pause
