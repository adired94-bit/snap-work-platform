"""
Chart Analyzer — ניתוח גרפים חכם באמצעות Claude Vision.

מעלים תמונת גרף (דקתי / 5 דקות / שעתי / יומי / שבועי) ומקבלים ניתוח מסחר מלא:
המלצות כניסה ויציאה (לונג/שורט), אזורי נזילות, תמיכה והתנגדות,
איפה הכסף החכם (Smart Money) נכנס/ייכנס, ועוד.
"""

import base64
import json
import os

import anthropic
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

app = Flask(__name__)

# מודל הראייה החזק ביותר של Claude
MODEL = "claude-opus-4-8"

# סוגי תמונה נתמכים (media_type עבור ה-API)
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

SYSTEM_PROMPT = """אתה אנליסט מסחר מומחה (Price Action + Smart Money Concepts / ICT).
אתה מנתח צילומי מסך של גרפים פיננסיים (מניות, קריפטו, פורקס, מדדים).

עבור כל גרף שתקבל, נתח לעומק את:
- מבנה השוק (Market Structure): עלייה / ירידה / דשדוש, BOS ו-CHoCH.
- כיוון מועדף (Bias): לונג, שורט או נייטרלי, עם רמת ביטחון.
- סטאפ מסחר: אזור כניסה, סטופ לוס, ויעדי רווח (Take Profit), ויחס סיכוי/סיכון.
- רמות תמיכה והתנגדות מרכזיות.
- אזורי נזילות (Liquidity): איפה יש Buy-side / Sell-side liquidity, Equal Highs/Lows, ואיפה צפוי Liquidity Sweep.
- כסף חכם (Smart Money): Order Blocks, Fair Value Gaps (FVG / אימבלנס), שלבי צבירה/חלוקה (Accumulation/Distribution), ואיפה הכסף החכם כנראה נכנס או ייכנס.
- תצפיות מפתח נוספות ורמת אינvalidation (מתי הניתוח מתבטל).

כללים:
- כל המחירים והרמות נגזרים ממה שאתה רואה בפועל בגרף. אם רמה לא ברורה — ציין זאת.
- אם אינך מצליח לזהות סימול/מחירים מהתמונה, תן ניתוח טכני יחסי (ביחס לרמות הנראות) ואל תמציא מספרים.
- ענה תמיד בעברית, בצורה ברורה ומקצועית.
- זהו ניתוח טכני לצרכים חינוכיים בלבד, ולא ייעוץ השקעות."""

# סכימת הפלט המובנה (Structured Output) שהמודל מחויב להחזיר
OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "symbol_guess": {"type": "string", "description": "ניחוש הסימול/נכס אם נראה בתמונה, אחרת 'לא ידוע'"},
        "timeframe": {"type": "string", "description": "טווח הזמן שנותח"},
        "market_structure": {"type": "string", "description": "תיאור מבנה השוק"},
        "overall_bias": {"type": "string", "enum": ["long", "short", "neutral"]},
        "confidence": {"type": "integer", "description": "רמת ביטחון 1-100"},
        "trade_setup": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "direction": {"type": "string", "enum": ["long", "short", "none"]},
                "entry_zone": {"type": "string"},
                "stop_loss": {"type": "string"},
                "take_profits": {"type": "array", "items": {"type": "string"}},
                "risk_reward": {"type": "string"},
            },
            "required": ["direction", "entry_zone", "stop_loss", "take_profits", "risk_reward"],
        },
        "support_levels": {"type": "array", "items": {"type": "string"}},
        "resistance_levels": {"type": "array", "items": {"type": "string"}},
        "liquidity_zones": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "type": {"type": "string", "description": "Buy-side / Sell-side / Equal Highs / Equal Lows"},
                    "price": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["type", "price", "note"],
            },
        },
        "smart_money": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "order_blocks": {"type": "array", "items": {"type": "string"}},
                "fair_value_gaps": {"type": "array", "items": {"type": "string"}},
                "accumulation_distribution": {"type": "string"},
                "where_smart_money_entering": {"type": "string"},
            },
            "required": [
                "order_blocks",
                "fair_value_gaps",
                "accumulation_distribution",
                "where_smart_money_entering",
            ],
        },
        "key_observations": {"type": "array", "items": {"type": "string"}},
        "invalidation": {"type": "string"},
        "summary": {"type": "string", "description": "סיכום קצר ותכליתי בעברית"},
    },
    "required": [
        "symbol_guess",
        "timeframe",
        "market_structure",
        "overall_bias",
        "confidence",
        "trade_setup",
        "support_levels",
        "resistance_levels",
        "liquidity_zones",
        "smart_money",
        "key_observations",
        "invalidation",
        "summary",
    ],
}


def get_client():
    """יוצר client של Anthropic. מחזיר None אם אין מפתח API."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    return anthropic.Anthropic()


@app.route("/")
def index():
    return render_template("index.html", timeframes=TIMEFRAME_LABELS)


@app.route("/api/analyze", methods=["POST"])
def analyze():
    client = get_client()
    if client is None:
        return jsonify({
            "error": "לא הוגדר מפתח API. צור קובץ .env עם ANTHROPIC_API_KEY (ראה .env.example)."
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

    image_b64 = base64.standard_b64encode(raw).decode("utf-8")

    user_text = (
        f"לפניך צילום מסך של גרף בטווח זמן: {tf_label}.\n"
        "נתח אותו לעומק והחזר את כל המידע: המלצות כניסה ויציאה ללונג או שורט, "
        "אזורי נזילות, תמיכה והתנגדות, איפה הכסף החכם נכנס/ייכנס, ועוד."
    )
    if notes:
        user_text += f"\n\nהקשר נוסף מהמשתמש: {notes}"

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": user_text},
                ],
            }],
        )
    except anthropic.APIStatusError as e:
        return jsonify({"error": f"שגיאת API ({e.status_code}): {e.message}"}), 502
    except anthropic.APIConnectionError:
        return jsonify({"error": "תקלת רשת בחיבור ל-Claude. נסה שוב."}), 502

    if response.stop_reason == "refusal":
        return jsonify({"error": "הבקשה נדחתה על ידי מנגנון הבטיחות. נסה תמונה אחרת."}), 422

    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        return jsonify({"error": "לא התקבל ניתוח מהמודל."}), 502

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return jsonify({"error": "תקלה בפענוח התשובה.", "raw": text}), 502

    return jsonify({"analysis": data})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
