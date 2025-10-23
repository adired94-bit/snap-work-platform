# 🚀 הגדרת Cloudflare Named Tunnel - כתובת קבועה ויציבה

## מה תקבל?
- ✅ כתובת קבועה משלך (למשל: snapcore.your-name.com)
- ✅ זמינות 24/7 (כל עוד המחשב שלך דולק)
- ✅ HTTPS אוטומטי וחינמי
- ✅ ללא הגבלת תעבורה

---

## שלב 1: הרשמה ל-Cloudflare (אם עדיין לא)
1. כנס ל-https://dash.cloudflare.com/sign-up
2. הירשם עם אימייל וסיסמה (חינמי)
3. אשר את האימייל

---

## שלב 2: יצירת Named Tunnel

### 2.1: התחבר ל-Cloudflare
פתח טרמינל והרץ:
```bash
cd /Users/admin/Desktop/snap/אפליקציה\ /SnapCore
./cloudflared tunnel login
```
זה יפתח דפדפן - אשר את ההרשאה.

### 2.2: צור Tunnel קבוע
```bash
./cloudflared tunnel create snapcore
```
זה ייצור Tunnel בשם "snapcore" ויתן לך UUID.

### 2.3: צור קובץ הגדרות
```bash
mkdir -p ~/.cloudflared
cat > ~/.cloudflared/config.yml << 'EOF'
tunnel: <TUNNEL-UUID-שקיבלת>
credentials-file: /Users/admin/.cloudflared/<TUNNEL-UUID>.json

ingress:
  - hostname: snapcore.your-subdomain.com
    service: http://localhost:5000
  - service: http_status:404
EOF
```
(החלף את `<TUNNEL-UUID-שקיבלת>` ב-UUID שקיבלת בשלב הקודם)

### 2.4: חבר את ה-Tunnel לדומיין
```bash
./cloudflared tunnel route dns snapcore snapcore.your-subdomain.com
```

### 2.5: הפעל את ה-Tunnel
```bash
./cloudflared tunnel run snapcore
```

---

## שלב 3: הרצה אוטומטית (אופציונלי)

אם תרצה שה-Tunnel יתחיל אוטומטית עם המחשב:
```bash
./cloudflared service install
```

---

## בעיות? פתרונות מהירים

### לא נפתח דפדפן?
העתק את הקישור מהטרמינל והדבק בדפדפן.

### שכחת את ה-UUID?
```bash
./cloudflared tunnel list
```

### רוצה למחוק ולהתחיל מחדש?
```bash
./cloudflared tunnel delete snapcore
```

---

## אלטרנטיבה: דומיין משלך (אם יש לך)

אם יש לך דומיין (למשל snapcore.co.il):
1. הוסף את הדומיין ל-Cloudflare (הכוון NS)
2. בשלב 2.4 השתמש בדומיין שלך:
   ```bash
   ./cloudflared tunnel route dns snapcore snapcore.co.il
   ```

---

**צריך עזרה? פשוט תגיד לי באיזה שלב אתה תקוע!**
