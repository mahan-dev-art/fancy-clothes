# Fancy Clothes 👕

<div dir="rtl">

یه سایت فروشگاه لباس با یه رگال لباس متحرک. روی هر لباس که کلیک کنی، بزرگ می‌شه و جزئیاتش رو نشون می‌ده.

صفحهٔ فروشگاه به **فارسی و راست‌چین** است (فونت وزیرمتن)؛ اسم لباس‌ها چون اسم برنده، انگلیسی مونده.

صفحهٔ اصلی فروشگاه (`/`) محصول‌ها را به‌صورت جدولی نشان می‌دهد و قیمت هر لباس را — وقتی در پنل ادمین وارد شده باشد — به تومان نمایش می‌دهد. نمای کلاسیک رگال هم به فارسی ترجمه شده و روی `/rack` در دسترس است.

[English guide below ⬇️](#english)

## چطوری اجراش کنم؟ (۳ قدم)

### قدم ۱: دانلود

بالای همین صفحه روی دکمهٔ سبز **`<> Code`** بزن و بعد **`Download ZIP`** رو انتخاب کن.
فایل دانلودشده رو باز کن (Unzip) تا یه پوشه بشه.

### قدم ۲: نصب پایتون (فقط یه بار)

- **مک:** معمولاً از قبل نصبه. برو قدم ۳.
- **ویندوز:** از [python.org/downloads](https://www.python.org/downloads/) دانلود و نصبش کن.
  ⚠️ موقع نصب حتماً تیک **`Add Python to PATH`** رو بزن.

### قدم ۳: اجرا

توی پوشه‌ای که باز کردی:

- **مک:** روی فایل **`start-mac.command`** دوبار کلیک کن.
- **ویندوز:** روی فایل **`start-windows.bat`** دوبار کلیک کن.

سایت خودش توی مرورگر باز می‌شه. 🎉
اگه باز نشد، این آدرس رو توی مرورگر بزن: **http://localhost:8080**

برای بستن سایت، پنجرهٔ سیاه (ترمینال) رو ببند.

## پنل مدیریت (اضافه / عوض کردن لباس)

برای اضافه کردن یه لباس جدید یا عوض کردن لباس‌ها، لازم نیست کد رو دست بزنی:

1. سایت رو مثل همیشه اجرا کن (دوبار کلیک روی `start-windows.bat`).
2. توی مرورگر برو به: **http://localhost:8080/admin**
3. از اونجا می‌تونی:
   - **لباس جدید اضافه کنی:** نام، رنگ، قیمت و عکس رو بده و «اضافه کن» رو بزن.
   - **ویرایش کنی:** روی «ویرایش» بزن، چیزی که می‌خوای رو عوض کن و «ذخیره تغییرات» رو بزن. اگه عکس جدید انتخاب نکنی، عکس قبلی می‌مونه.
   - **حذف کنی:** روی «حذف» بزن.

همه لباس‌ها توی فایل **`products.json`** ذخیره می‌شن و تغییرات بلافاصله توی فروشگاه دیده می‌شه (صفحه فروشگاه رو رفرش کن). عکس‌هایی که آپلود می‌کنی توی پوشه `site/uploads/` ذخیره می‌شن.

| نکته | توضیح |
|---|---|
| قیمت | قیمت‌ها فعلاً فقط توی پنل مدیریت نگه داشته می‌شن و روی صفحه فروشگاه نمایش داده نمی‌شن. |
| گروه | اگه چند رنگ از یه مدل لباس داری، برای همه‌شون یه «گروه» یکسان بنویس تا توی فروشگاه با هم نمایش داده بشن و مشتری رنگ رو انتخاب کنه. |
| عکس | عکس بهتره روی پس‌زمینه ساده و به صورت عمودی باشه (PNG یا JPG). |

## دیپلوی روی Deplexo

یه `Dockerfile` توی ریشهٔ ریپو هست؛ Deplexo خودش اون رو تشخیص می‌ده و نیازی به `deplexo.yaml` نیست:

1. توی داشبورد Deplexo ریپوی گیت‌هاب رو وصل کن و دیپلوی رو بزن.
2. پورت رو Deplexo با متغیر محیطی `PORT` می‌ده و سرور (`serve.py`) روی همون پورت و روی `0.0.0.0` گوش می‌ده.

⚠️ تغییرات پنل ادمین (قیمت‌ها، محصولات، عکس‌های آپلودی) داخل فایل‌سیستم کانتینر ذخیره می‌شن و بدون volume روی Deplexo ماندگار نیستن؛ بعد از هر ری‌دیپلوی ممکنه به حالت ریپو برگردن.

## مشکل داری؟

| مشکل | راه‌حل |
|---|---|
| مک می‌گه «نمی‌شه بازش کرد چون از یه توسعه‌دهندهٔ ناشناسه» | روی فایل **راست‌کلیک** کن، **Open** رو بزن، بعد دوباره **Open**. |
| ویندوز می‌گه `python` پیدا نشد | پایتون رو دوباره نصب کن و این بار تیک `Add Python to PATH` رو بزن. |
| می‌گه پورت 8080 درگیره | یه بار دیگه سایت بازه. اون پنجره رو ببند و دوباره امتحان کن. |

## روش دستی (برای کسایی که با ترمینال کار می‌کنن)

</div>

```bash
python3 serve.py
```

<div dir="rtl">

روی ویندوز به جای `python3` بنویس `python`.
اگه می‌خوای روی یه پورت دیگه اجرا بشه: `python3 serve.py 3000`

</div>

---

<a id="english"></a>

## English

A clothing store website with an animated clothes rack. Click any item to see it up close.

### How to run it (3 steps)

1. **Download:** click the green **`<> Code`** button at the top of this page → **`Download ZIP`**, then unzip it.
2. **Install Python (one time only):**
   - **Mac:** usually already installed, so skip this step.
   - **Windows:** install it from [python.org/downloads](https://www.python.org/downloads/). ⚠️ Tick **`Add Python to PATH`** during setup.
3. **Run:** in the unzipped folder, double-click
   - **Mac:** `start-mac.command`
   - **Windows:** `start-windows.bat`

The site opens in your browser by itself. If it doesn't, go to **http://localhost:8080**.
To stop the site, close the black terminal window.

**Mac says the file is from an unidentified developer?** Right-click the file → **Open** → **Open**.

**Prefer the terminal?**

```bash
python3 serve.py
```

### What's inside

| File / folder | What it is |
|---|---|
| `site/` | The website itself |
| `products.json` | The list of products (name, colour, price, pictures). Edit it from the admin panel — no code changes needed. |
| `admin.html` | The admin panel page, served at `/admin` |
| `serve.py` | A tiny local server that runs the site. Nothing to install: it only needs Python. It also serves the admin panel and its API. |
| `start-mac.command` | Double-click to run on Mac |
| `start-windows.bat` | Double-click to run on Windows |

### Admin panel

To add a product or change one, no code needed:

1. Run the site as usual (double-click `start-windows.bat`).
2. Open **http://localhost:8080/admin** in the browser.
3. Add a product (name, colour, price, picture), edit one, or delete one.

Products are stored in `products.json` and changes show up on the shop page immediately (refresh it). Uploaded pictures are saved under `site/uploads/` (local only, not committed to git).
