# 📊 מנתח הגרפים החכם (Chart Analyzer)

אפליקציית web שבה מעלים צילום מסך של גרף פיננסי (דקתי / 5 דקות / שעתי / יומי / שבועי)
ומקבלים ניתוח מסחר מלא באמצעות יכולת הראייה (Vision) של Claude.

## מה מקבלים בניתוח

- **כיוון מועדף (Bias)** — לונג / שורט / נייטרלי + רמת ביטחון
- **סטאפ מסחר** — אזור כניסה, סטופ לוס, יעדי רווח, יחס סיכוי/סיכון
- **תמיכות והתנגדויות** מרכזיות
- **אזורי נזילות (Liquidity)** — Buy-side / Sell-side, Equal Highs/Lows, צפי ל-Sweep
- **כסף חכם (Smart Money)** — Order Blocks, Fair Value Gaps, צבירה/חלוקה, ואיפה הכסף החכם נכנס/ייכנס
- **מבנה השוק**, תצפיות מפתח, ורמת ביטול הניתוח (Invalidation)

## הרצה מקומית

דרישות: Python 3.10+

```bash
# 1. התקנת ספריות
pip install -r requirements.txt

# 2. הגדרת מפתח API (חינמי)
cp .env.example .env
# ערוך את .env והכנס את ה-GEMINI_API_KEY שלך
# (מקבלים מפתח חינמי ב: https://aistudio.google.com/apikey)

# 3. הרצה
python app.py
```

האפליקציה תרוץ בכתובת http://localhost:5000

## איך זה עובד

הקצה הקדמי (`templates/index.html`) שולח את התמונה ל-`/api/analyze`.
השרת (`app.py`) שולח את התמונה למודל `gemini-2.0-flash` (Google Gemini, שכבה חינמית)
יחד עם פרומפט מערכת של אנליסט מסחר (Price Action + Smart Money Concepts),
ומקבל JSON מובנה שמוצג בממשק בעברית.

## מבנה הפרויקט

```
app.py                  # שרת Flask + קריאה ל-Gemini Vision
templates/index.html    # ממשק המשתמש (עברית, RTL)
requirements.txt        # ספריות Python
.env.example            # תבנית להגדרת מפתח ה-API
```

## ⚠️ הבהרה

הניתוח נועד למטרות חינוכיות בלבד ואינו מהווה ייעוץ השקעות.
מסחר בשווקים פיננסיים כרוך בסיכון.
