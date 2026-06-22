"""
Chart Analyzer — ניתוח גרפים חכם באמצעות Google Gemini (Vision).

מעלים תמונת גרף (דקתי / 5 דקות / שעתי / יומי / שבועי) ומקבלים ניתוח מסחר מלא:
המלצות כניסה ויציאה (לונג/שורט), אזורי נזילות, תמיכה והתנגדות,
איפה הכסף החכם (Smart Money) נכנס/ייכנס, ועוד.

משתמש ב-Gemini עם שכבה חינמית. מפתח חינמי: https://aistudio.google.com/apikey
"""

import json
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from google import genai
from google.genai import types

load_dotenv()

app = Flask(__name__)

# מודל Gemini עם תמיכה בתמונות ושכבה חינמית
MODEL = "gemini-2.0-flash"

# סוגי תמונה נתמכים (mime type)
SUPPORTED_MEDIA = {
    "image/jpeg": "image/jpeg",
    "image/jpg": "image/jpeg",
    "image/png": "image/png",
    "image/gif": "image/gif",
    "image/webp": "image/webp",
}

# תוויות טווחי זמן לתצוגה אנושית בתוך הפרומפט
TIMEFRAME_LABELS = {
    "1m": "דקה (1m)",
    "5m": "5 דקות (5m)",
    "15m": "15 דקות (15m)",
    "1h": "שעה (1h)",
    "4h": "4 שעות (4h)",
    "1d": "יומי (1D)",
    "1w": "שבועי (1W)",
}

# מבנה ה-JSON שהמודל חייב להחזיר (המפתחות חייבים להתאים ל-index.html)
JSON_SHAPE = """{
  "symbol_guess": "ניחוש הסימול/נכס אם נראה בתמונה, אחרת 'לא ידוע'",
  "timeframe": "טווח הזמן שנותח",
  "market_structure": "תיאור מבנה השוק (עלייה/ירידה/דשדוש, BOS, CHoCH)",
  "overall_bias": "long | short | neutral",
  "confidence": 0,
  "trade_setup": {
    "direction": "long | short | none",
    "entry_zone": "אזור כניסה",
    "stop_loss": "סטופ לוס",
    "take_profits": ["יעד 1", "יעד 2"],
    "risk_reward": "יחס סיכוי/סיכון"
  },
  "support_levels": ["רמת תמיכה 1", "רמת תמיכה 2"],
  "resistance_levels": ["רמת התנגדות 1", "רמת התנגדות 2"],
  "liquidity_zones": [
    {"type": "Buy-side / Sell-side / Equal Highs / Equal Lows", "price": "מחיר", "note": "הסבר קצר"}
  ],
  "smart_money": {
    "order_blocks": ["Order Block 1"],
    "fair_value_gaps": ["FVG 1"],
    "accumulation_distribution": "שלב צבירה/חלוקה",
    "where_smart_money_entering": "איפה הכסף החכם נכנס או צפוי להיכנס"
  },
  "key_observations": ["תצפית 1", "תצפית 2"],
  "invalidation": "מתי הניתוח מתבטל",
  "summary": "סיכום קצר ותכליתי בעברית"
}"""

SYSTEM_PROMPT = f"""אתה אנליסט מסחר מומחה (Price Action + Smart Money Concepts / ICT).
אתה מנתח צילומי מסך של גרפים פיננסיים (מניות, קריפטו, פורקס, מדדים).

עבור כל גרף נתח לעומק: מבנה השוק, כיוון מועדף (לונג/שורט/נייטרלי) עם רמת ביטחון,
סטאפ מסחר (כניסה, סטופ, יעדי רווח, יחס סיכוי/סיכון), תמיכות והתנגדויות,
אזורי נזילות (Buy/Sell-side, Equal Highs/Lows, צפי ל-Liquidity Sweep),
וכסף חכם (Order Blocks, Fair Value Gaps, צבירה/חלוקה, ואיפה הכסף החכם נכנס/ייכנס).

כללים:
- כל המחירים והרמות נגזרים ממה שאתה רואה בפועל בגרף. אם רמה לא ברורה — ציין זאת.
- אם אינך מזהה סימול/מחירים, תן ניתוח טכני יחסי ואל תמציא מספרים.
- ענה תמיד בעברית, מקצועי וברור. זהו ניתוח חינוכי בלבד, לא ייעוץ השקעות.

החזר אך ורק אובייקט JSON תקין במבנה המדויק הבא (ללא טקסט נוסף, ללא ```):
{JSON_SHAPE}"""


def get_client():
    """יוצר client של Gemini. מחזיר None אם אין מפתח API."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


@app.route("/")
def index():
    return render_template("index.html", timeframes=TIMEFRAME_LABELS)


@app.route("/api/analyze", methods=["POST"])
def analyze():
    client = get_client()
    if client is None:
        return jsonify({
            "error": "לא הוגדר מפתח API. הגדר GEMINI_API_KEY (מפתח חינמי: https://aistudio.google.com/apikey)."
        }), 500

    if "image" not in request.files:
        return jsonify({"error": "לא נשלחה תמונה."}), 400

    file = request.files["image"]
    raw = file.read()
    if not raw:
        return jsonify({"error": "הקובץ ריק."}), 400

    media_type = SUPPORTED_MEDIA.get((file.mimetype or "").lower())
    if media_type is None:
        return jsonify({
            "error": "סוג קובץ לא נתמך. השתמש ב-PNG, JPG, GIF או WEBP."
        }), 400

    timeframe = request.form.get("timeframe", "1h")
    tf_label = TIMEFRAME_LABELS.get(timeframe, timeframe)
    notes = (request.form.get("notes") or "").strip()

    user_text = (
        f"לפניך צילום מסך של גרף בטווח זמן: {tf_label}.\n"
        "נתח אותו לעומק והחזר את כל המידע במבנה ה-JSON שהוגדר."
    )
    if notes:
        user_text += f"\n\nהקשר נוסף מהמשתמש: {notes}"

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=[
                types.Part.from_bytes(data=raw, mime_type=media_type),
                user_text,
            ],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.4,
            ),
        )
    except Exception as e:  # noqa: BLE001 — מציג למשתמש הודעה ידידותית
        msg = str(e)
        if "API key" in msg or "API_KEY" in msg or "PERMISSION" in msg:
            return jsonify({"error": "מפתח ה-API לא תקין. בדוק את GEMINI_API_KEY."}), 502
        if "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
            return jsonify({"error": "חרגת ממכסת השימוש החינמית הרגעית. המתן דקה ונסה שוב."}), 429
        return jsonify({"error": f"שגיאה בקריאה ל-Gemini: {msg[:160]}"}), 502

    text = (response.text or "").strip()
    if not text:
        return jsonify({"error": "לא התקבל ניתוח מהמודל."}), 502

    # ניקוי גידור קוד אם המודל הוסיף בטעות ```json
    if text.startswith("```"):
        text = text.strip("`")
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return jsonify({"error": "תקלה בפענוח התשובה.", "raw": text[:500]}), 502

    return jsonify({"analysis": data})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
