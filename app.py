"""
Chart Analyzer — ניתוח גרפים חכם באמצעות Google Gemini (Vision).

מעלים תמונת גרף (דקתי / 5 דקות / שעתי / יומי / שבועי) ומקבלים ניתוח מסחר מלא:
המלצות כניסה ויציאה (לונג/שורט), אזורי נזילות, תמיכה והתנגדות,
איפה הכסף החכם (Smart Money) נכנס/ייכנס, ועוד.

משתמש ב-Gemini עם שכבה חינמית. מפתח חינמי: https://aistudio.google.com/apikey
"""

import json
import os
import time

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


def _strip_json_fence(text):
    """מנקה גידור קוד ```json אם המודל הוסיף אותו."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    return text.strip()


def fetch_market_news(client, symbol):
    """מחפש באינטרנט חדשות ודעת אנליסטים על הנכס, באמצעות Google Search grounding."""
    prompt = (
        f'חפש באינטרנט מידע עדכני (מהחודשים האחרונים) על הנכס/מניה: "{symbol}".\n'
        "החזר אך ורק אובייקט JSON תקין (ללא טקסט נוסף, ללא גידור קוד), במבנה הבא:\n"
        "{\n"
        '  "company_name": "שם החברה/הנכס",\n'
        '  "analyst_rating": "strong_buy | buy | hold | sell | strong_sell | unknown",\n'
        '  "rating_label": "תווית בעברית: קנייה חזקה / קנייה / החזק / מכירה / מכירה חזקה / לא ידוע",\n'
        '  "consensus": "משפט-שניים על קונצנזוס האנליסטים בעברית",\n'
        '  "price_target": "מחיר יעד ממוצע אם קיים, אחרת \'לא ידוע\'",\n'
        '  "news": [\n'
        '    {"title": "כותרת בעברית", "summary": "תקציר קצר בעברית", "sentiment": "positive | negative | neutral"}\n'
        "  ]\n"
        "}\n"
        "כלול עד 5 כותרות חדשות רלוונטיות ועדכניות. אם אין מספיק מידע, החזר "
        "rating_label='לא ידוע' ורשימת news ריקה. אל תמציא נתונים."
    )
    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt],
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.3,
        ),
    )
    return json.loads(_strip_json_fence(resp.text))


@app.route("/")
def index():
    return render_template("index.html", timeframes=TIMEFRAME_LABELS)


@app.route("/health")
def health():
    """נקודת בדיקה קלה — משמשת שירות keep-alive כדי שהשרת לא יירדם."""
    return "ok", 200


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

    # רשימת מודלים לנסות לפי הסדר (אם הראשון חוסם במכסה — ננסה את הבא)
    models_to_try = [MODEL, "gemini-2.5-flash", "gemini-flash-latest"]
    response = None
    last_msg = ""

    for model_name in models_to_try:
        for attempt in range(2):  # ניסיון + ניסיון חוזר אחד עם המתנה
            try:
                response = client.models.generate_content(
                    model=model_name,
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
                break
            except Exception as e:  # noqa: BLE001
                last_msg = str(e)
                is_rate = "RESOURCE_EXHAUSTED" in last_msg or "429" in last_msg or "quota" in last_msg.lower()
                if is_rate and attempt == 0:
                    time.sleep(4)
                    continue
                break  # שגיאה שאינה ניתנת לניסיון חוזר, או שכבר ניסינו — עבור למודל הבא
        if response is not None:
            break

    if response is None:
        msg = last_msg
        low = msg.lower()
        if "api key" in low or "api_key" in low or "permission" in low or "invalid" in low and "key" in low:
            return jsonify({"error": f"בעיית מפתח API. פרטים: {msg[:200]}"}), 502
        if "RESOURCE_EXHAUSTED" in msg or "429" in msg or "quota" in low:
            return jsonify({"error": f"חרגת ממכסת השימוש החינמית. פרטים: {msg[:220]}"}), 429
        return jsonify({"error": f"שגיאה בקריאה ל-Gemini: {msg[:220]}"}), 502

    text = _strip_json_fence(response.text)
    if not text:
        return jsonify({"error": "לא התקבל ניתוח מהמודל."}), 502

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return jsonify({"error": "תקלה בפענוח התשובה.", "raw": text[:500]}), 502

    # שלב שני: חדשות ודעת אנליסטים (חיפוש באינטרנט) על הסימול שזוהה
    symbol = (data.get("symbol_guess") or "").strip()
    known = bool(symbol) and symbol.lower() not in ("לא ידוע", "unknown", "n/a", "none")
    if not known and notes:
        symbol = notes
        known = True
    if known:
        try:
            data["news_report"] = fetch_market_news(client, symbol)
        except Exception as e:  # noqa: BLE001 — החדשות הן תוספת; לא מפילות את הניתוח
            data["news_report"] = {"error": str(e)[:160]}
    else:
        data["news_report"] = {"unavailable": True}

    return jsonify({"analysis": data})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
