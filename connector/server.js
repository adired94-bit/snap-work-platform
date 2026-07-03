/*
 * אוצר — מחבר בנק מקומי (Local Bank Connector)
 * ------------------------------------------------------------------
 * מה זה עושה:
 *   1. מגיש את אפליקציית אוצר (הקבצים בתיקייה שמעל) בכתובת http://localhost:8788
 *   2. חושף API אחד — POST /api/scrape — שמתחבר לחשבון האמיתי שלך
 *      (בנק הפועלים, כרטיסי אשראי ועוד) דרך israeli-bank-scrapers
 *      ומחזיר את התנועות האמיתיות.
 *
 * אבטחה — קרא בבקשה:
 *   • הכל רץ על המחשב שלך בלבד. שום דבר לא נשלח לשרת חיצוני.
 *   • פרטי ההתחברות (שם משתמש/סיסמה) מגיעים בבקשה, משמשים רגע אחד
 *     כדי להתחבר, ולא נשמרים ולא נרשמים בשום קובץ/לוג.
 *   • הכלי הוא קוד פתוח (israeli-bank-scrapers) — אותה טכנולוגיה
 *     שמריצות אפליקציות פיננסיות ישראליות לחשבון האישי שלהן.
 */
const path = require('path');
const express = require('express');
const cors = require('cors');
const { createScraper, CompanyTypes } = require('israeli-bank-scrapers');

const app = express();
const PORT = process.env.PORT || 8788;

app.use(cors());                       // מאפשר גם לאפליקציה שרצה בכתובת אחרת בלוקאלי
app.use(express.json({ limit: '256kb' }));

// מגיש את אפליקציית אוצר (index.html, vendor/pdf.js וכו') מהתיקייה שמעל
app.use(express.static(path.join(__dirname, '..')));

app.get('/api/health', (_req, res) => {
  res.json({ ok: true, providers: Object.values(CompanyTypes) });
});

/*
 * POST /api/scrape
 * body: { provider: "hapoalim", credentials: { userCode, password }, months?: 3 }
 * מחזיר: { provider, accounts: [{ accountNumber, balance, kind, txns: [{date, desc, amt, memo, status}] }] }
 */
app.post('/api/scrape', async (req, res) => {
  const { provider, credentials, months } = req.body || {};
  if (!provider || !credentials) {
    return res.status(400).json({ error: 'missing_params', message: 'חסר provider או credentials' });
  }
  const companyId = CompanyTypes[provider];
  if (!companyId) {
    return res.status(400).json({ error: 'unknown_provider', message: `ספק לא מוכר: ${provider}` });
  }

  const startDate = new Date();
  startDate.setMonth(startDate.getMonth() - (Number(months) || 3));

  const CARD_PROVIDERS = ['visaCal', 'max', 'isracard', 'amex'];
  const kind = CARD_PROVIDERS.includes(provider) ? 'card' : 'bank';

  const scraper = createScraper({
    companyId,
    startDate,
    combineInstallments: false,
    showBrowser: false,
    defaultTimeout: 80000,
  });

  try {
    const result = await scraper.scrape(credentials);
    if (!result || !result.success) {
      return res.status(502).json({
        error: result ? result.errorType : 'scrape_failed',
        message: (result && result.errorMessage) || 'ההתחברות נכשלה. בדוק את הפרטים ונסה שוב.',
      });
    }
    const accounts = (result.accounts || []).map((a) => ({
      accountNumber: a.accountNumber,
      balance: typeof a.balance === 'number' ? a.balance : null,
      kind,
      txns: (a.txns || []).map((t) => ({
        date: t.date,
        desc: (t.description || '').trim() || 'תנועה',
        memo: (t.memo || '').trim(),
        amt: t.chargedAmount,          // שלילי = הוצאה, חיובי = הכנסה
        status: t.status,
      })),
    }));
    res.json({ provider, kind, accounts });
  } catch (e) {
    res.status(500).json({ error: 'exception', message: String((e && e.message) || e) });
  }
  // credentials יוצאים מהזיכרון עם סיום הבקשה — לא נשמרים בשום מקום.
});

app.listen(PORT, () => {
  console.log('\n══════════════════════════════════════════════');
  console.log('  אוצר · מחבר בנק מקומי פועל');
  console.log(`  פתח בדפדפן:  http://localhost:${PORT}`);
  console.log('  הכל רץ מקומית. הסיסמאות לא יוצאות מהמחשב הזה.');
  console.log('══════════════════════════════════════════════\n');
});
