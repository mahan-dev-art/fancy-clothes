#!/usr/bin/env python3
"""Serve the saved snugwrld.netlify.app copy locally + admin panel.

The storefront is Persian (site/fa.html, RTL, Vazirmatn) and is served at
"/" -- it shows each product's price from products.json (in تومان) when one
is set. The original rack page was also translated to Persian in place
(site/index.html + translated UI strings in the JS) and is served at "/rack".
The saved copy stores Next.js optimized images under hashed filenames, so
/_next/image?url=... requests are mapped back to those files here.

Products live in products.json (NOT hard-coded any more). Edit them from the
admin panel at http://localhost:8080/admin -- no code changes needed.

How it works (short version):
  * products.json is the list of clothes. serve.py reads it on every request,
    so changes made in the admin panel show up on the shop page right away.
  * The shop page itself is a saved static copy: its product list lives inside
    a JavaScript file (site/_next/static/chunks/*.js). When the browser asks
    for that file, serve.py swaps the built-in product list with the one from
    products.json, and adds image measurements for newly uploaded pictures.
    The files on disk are never changed -- the swap happens in memory only.
  * Uploaded pictures are saved under site/uploads/ and served like the rest.

Usage: python3 serve.py [port]   (default 8080)
"""
import base64
import html
import json
import mimetypes
import os
import re
import struct
import sys
import threading
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(BASE, "site")               # the shop files
PRODUCTS_FILE = os.path.join(BASE, "products.json")
UPLOADS_DIR = os.path.join(ROOT, "uploads")     # uploaded product pictures
ADMIN_FILE = os.path.join(BASE, "admin.html")
CHECKOUT_BASE = "https://checkout.snugwrld.com/products/"

# ---------------------------------------------------------------------------
# Persian storefront: colours + UI strings are translated when the shop page
# is served (products.json itself keeps the English names -- see below).
# ---------------------------------------------------------------------------
# Colour names in products.json are English ("White", "Black", ...). The shop
# shows them in Persian; anything not in this list is shown as-is, so a
# Persian colour typed in the admin panel also works.
COLOR_FA = {
    "White": "سفید", "Black": "مشکی", "Blue": "آبی",
    "Yellow": "زرد", "Sand": "شنی", "Pink": "صورتی",
}


def fa_color(color):
    """English colour name -> Persian, or the original text if unknown."""
    return COLOR_FA.get((color or "").strip(), color or "")


# User-visible English strings inside the shop's JavaScript file, translated
# to Persian. Each pair is (English, Persian) as plain text.
# Brand names ("Snug Wrld", product names) are deliberately NOT in this list.
# Most appear as double-quoted literals; two are `backtick` template literals
# (listed separately) -- note the file uses plain apostrophes inside its
# double-quoted strings (e.g. "IT'S US..."), so do NOT escape them.
UI_STRINGS_FA = [
    ("See Availability", "مشاهده موجودی"),
    ("SEE AVAILABILITY ↗", "مشاهده موجودی ↗"),
    ("Close detail view", "بستن نمای جزئیات"),
    ("Close ", "بستن "),
    ("About", "درباره ما"),
    ("Contact", "تماس"),
    ("Next piece", "آیتم بعدی"),
    ("Previous piece", "آیتم قبلی"),
    ("Show front or back", "نمایش جلو یا پشت"),
    ("IT'S US, NEVER THEM  •  NEW DROPS  •  LAGOS  •  ",
     "ما هستیم، نه اونا  •  کالکشن جدید  •  لاگوس  •  "),
    ("It's us, never them. New drops. Lagos.",
     "ما هستیم، نه اونا. کالکشن‌های جدید. لاگوس."),
]
UI_TEMPLATE_STRINGS_FA = [
    ("See availability of ${t} (opens in a new tab)",
     "مشاهده موجودی ${t} (در تب جدید باز می‌شود)"),
    ("Colour: ${t.label}", "رنگ: ${t.label}"),
]


def _js_double_quoted(text):
    """Wrap text the way it appears as a double-quoted JS string literal."""
    return '"' + text.replace('"', '\\"') + '"'


def translate_ui_strings(text):
    """Replace the shop's English UI strings with Persian ones (in memory).

    Only exact string literals are replaced, so code identifiers (e.g. the
    DOM property "Size") are never touched. A string that is not found is
    simply skipped -- the page still serves.
    """
    for english, persian in UI_STRINGS_FA:
        old = _js_double_quoted(english)
        if old in text:
            text = text.replace(old, _js_double_quoted(persian))
    for english, persian in UI_TEMPLATE_STRINGS_FA:
        old = "`" + english + "`"
        if old in text:
            text = text.replace(old, "`" + persian + "`")
    return text


# ---------------------------------------------------------------------------
# Products: load / save products.json
# ---------------------------------------------------------------------------
# Fallback: the original 11 products, used only if products.json is missing.
# (large front, small front, side) -- None falls back to the next available image
LEGACY_PRODUCTS = {
    "crimson-memory":    ("image-c6343cb74a71e8", "image-6c2a15e13730c8", "image-4e8640f03d7b6"),
    "distressed-logo-t": ("image-bb6fb99c4b2508", "image-c1471486a0b8a8", "image-05f55d455bb558"),
    "its-us-tee-black":  ("image-b4ec065a4e66f8", "image-39f2c686e071e8", "image-b542c1d352ef8"),
    "jersey-yellow":     ("image-6ae6766896f1d8", "image-a088f00edf1b58", "image-959fe759fcd068"),
    "silicone-tee":      ("image-ffce5fea8389f8", "image-9f64af5d69fbe", "image-97e6e1449d26b"),
    "tank-black":        ("image-0af2db7b4647a8", "image-9f9a2a06d674d8", "image-9efcd9db49e648"),
    "varsity":           ("image-84bdfd6756b51", "image-36c27604289f1", "image-d2f85dbbd1b6c8"),
    "jersey-blue":       ("image-2406692edfcaf", None, None),
    "tank-sand":         ("image-246e6ad4aa26a8", None, None),
    "its-us-tee-yellow": ("image-277d32b1ca5e88", None, None),
    "its-us-tee-bubblegum": ("image-ad7c33cd14d518", None, None),
}

_products_lock = threading.Lock()


def _legacy_as_list():
    """Turn the old hard-coded dict into the products.json format."""
    names = {
        "crimson-memory": ("Crimson Memory LS Shirt", "White", "#ffffff", None, "crimson-memory-shirt"),
        "distressed-logo-t": ("Distressed Logo Print T-Shirt", "Blue", "#2f5fb3", None, "distressed-logo-print-t-shirt"),
        "its-us-tee-black": ("It's Us Never Them Tee", "Black", "#1e1e1e", "its-us-tee", "its-us-never-them-tee-pink"),
        "jersey-yellow": ("Snug Football Jersey", "Yellow", "#e3ca1e", "jersey", "snug-jersey-blue"),
        "silicone-tee": ("Silicone Logo Print T-Shirt", "White", "#ffffff", None, "silicone-logo-tee"),
        "tank-black": ("Distressed Painted Logo Tank Top", "Black", "#2d2d2c", "tank", "distressed-sleeveless-vintage-light-beige"),
        "varsity": ("Snug Wrld Logo Varsity Jacket", "Black", "#1e1e1e", None, "snug-wrld-varsity-jackets"),
        "jersey-blue": ("Snug Football Jersey", "Blue", "#0842a9", "jersey", "snug-jersey-blue"),
        "tank-sand": ("Distressed Painted Logo Tank Top", "Sand", "#b29e8b", "tank", "distressed-sleeveless-vintage-light-beige"),
        "its-us-tee-yellow": ("It's Us Never Them Tee", "Yellow", "#f8dd2f", "its-us-tee", "its-us-never-them-tee-pink"),
        "its-us-tee-bubblegum": ("It's Us Never Them Tee", "Pink", "#f6b1b4", "its-us-tee", "its-us-never-them-tee-pink"),
    }
    out = []
    for slug, (large, small, side) in LEGACY_PRODUCTS.items():
        name, color, hexcode, group, url = names[slug]
        out.append({"id": slug, "name": name, "color": color, "hex": hexcode,
                    "price": "", "group": group, "url": url,
                    "image": large, "image_small": small, "image_side": side,
                    "upload": None})
    return out


def load_products():
    """Read products.json (fresh from disk every time, so admin edits apply instantly)."""
    with _products_lock:
        try:
            with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
                products = json.load(f)
            if isinstance(products, list):
                return products
        except (OSError, ValueError):
            pass
        return _legacy_as_list()


def save_products(products):
    """Write the product list back to products.json."""
    with _products_lock:
        tmp = PRODUCTS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, PRODUCTS_FILE)


def slugify(text):
    """Turn a name into a short URL-safe id, e.g. 'My Shirt' -> 'my-shirt'."""
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    if not text:  # Persian-only name etc: fall back to a timestamp id
        text = "item-%d" % (int(time.time()) % 1000000)
    return text[:40]


# ---------------------------------------------------------------------------
# Images: find the file for a /products/<slug>-<view>.webp request
# ---------------------------------------------------------------------------
def resolve_image(url, width):
    """Return (filesystem path, content type) for an image URL, or (None, None).

    Two kinds of products:
      * original products: image files saved as site/_next/image-*.html
      * products with an uploaded picture: the file under site/uploads/
    """
    if url == "/snug-wrld-logo.png":
        return os.path.join(ROOT, "_next", "image.html"), "image/webp"
    name = os.path.basename(url).rsplit(".", 1)[0]
    products = load_products()
    for p in products:
        if name.startswith(p["id"] + "-"):
            view = name[len(p["id"]) + 1:]
            if p.get("upload"):  # uploaded picture: same image for every view
                path = os.path.join(ROOT, p["upload"].replace("/", os.sep))
                ctype = mimetypes.guess_type(path)[0] or "image/jpeg"
                return (path, ctype) if os.path.exists(path) else (None, None)
            # original saved images: pick large/small/side like before
            large, small, side = p.get("image"), p.get("image_small"), p.get("image_side")
            front = small if (small and width <= 512) else large
            fname = (side or front) if view == "side" else front
            if not fname:
                return None, None
            return os.path.join(ROOT, "_next", fname + ".html"), "image/webp"
    # unknown slug: try the old hard-coded mapping (safety net)
    for slug, (large, small, side) in LEGACY_PRODUCTS.items():
        if name.startswith(slug + "-"):
            view = name[len(slug) + 1:]
            front = small if (small and width <= 512) else large
            fname = (side or front) if view == "side" else front
            if not fname:
                return None, None
            return os.path.join(ROOT, "_next", fname + ".html"), "image/webp"
    return None, None


# ---------------------------------------------------------------------------
# Image size (pure Python, no extra installs): needed for the clothes rack
# ---------------------------------------------------------------------------
def image_size(path):
    """Return (width, height) of a PNG/JPEG/WebP file, or (800, 1000) if unknown."""
    try:
        with open(path, "rb") as f:
            head = f.read(64)
        if head[:8] == b"\x89PNG\r\n\x1a\n":  # PNG: width/height in IHDR
            return struct.unpack(">II", head[16:24])
        if head[:2] == b"\xff\xd8":  # JPEG: find a SOF marker
            i = 2
            while i < len(head) - 9:
                if head[i] != 0xFF:
                    i += 1
                    continue
                marker = head[i + 1]
                if marker in (0xC0, 0xC1, 0xC2):
                    h, w = struct.unpack(">HH", head[i + 5:i + 9])
                    return w, h
                size = struct.unpack(">H", head[i + 2:i + 4])[0]
                i += 2 + size
            # need more bytes for big JPEGs: read the whole header
            with open(path, "rb") as f:
                data = f.read(65536)
            i = 2
            while i < len(data) - 9:
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                if marker in (0xC0, 0xC1, 0xC2):
                    h, w = struct.unpack(">HH", data[i + 5:i + 9])
                    return w, h
                size = struct.unpack(">H", data[i + 2:i + 4])[0]
                i += 2 + size
        if head[:4] == b"RIFF" and head[8:12] == b"WEBP":  # WebP
            kind = head[12:16]
            if kind == b"VP8X":
                w = int.from_bytes(head[24:27], "little") + 1
                h = int.from_bytes(head[27:30], "little") + 1
                return w, h
            if kind == b"VP8L":
                bits = int.from_bytes(head[21:25], "little")
                return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
            if kind == b"VP8 ":
                w = int.from_bytes(head[26:28], "little") & 0x3FFF
                h = int.from_bytes(head[28:30], "little") & 0x3FFF
                return w, h
    except (OSError, struct.error, IndexError):
        pass
    return 800, 1000


def default_geometry(width, height):
    """Rack measurements for a newly uploaded picture.

    The shop page hangs every garment on a hook, so it needs to know where
    the hook, shoulders and bottom of the garment are. These are the same
    proportions as the original products, scaled to the new picture size.
    """
    return {
        "width": width, "height": height,
        "hookApexX": round(width * 0.50), "hookApexY": 18,
        "loopTopY": 18, "loopCenterX": round(width * 0.50),
        "loopInnerTopY": 24, "loopInnerBottomY": 53,
        "neckY": round(height * 0.08),
        "garmentTopY": 18, "garmentBottomY": round(height * 0.94),
        "shoulderY": round(height * 0.38),
        "shoulderX0": round(width * 0.15), "shoulderX1": round(width * 0.84),
        "garmentX0": round(width * 0.04), "garmentX1": round(width * 0.96),
    }


# ---------------------------------------------------------------------------
# Shop-page patching: swap the built-in product list with products.json
# ---------------------------------------------------------------------------
def build_product_list_js(products):
    """Build the shop's product list (JavaScript) from products.json.

    Products sharing a "group" (e.g. the same shirt in 3 colours) become one
    rack item with colour choices, exactly like the original site.
    """
    groups = []  # list of (group key, [products]) in file order
    seen = {}
    for p in products:
        key = p.get("group") or p["id"]
        if key in seen:
            groups[seen[key]][1].append(p)
        else:
            seen[key] = len(groups)
            groups.append((key, [p]))
    parts = []
    for key, items in groups:
        first = items[0]
        name = json.dumps(first["name"], ensure_ascii=False)
        url = json.dumps(CHECKOUT_BASE + (first.get("url") or first["id"]), ensure_ascii=False)
        if len(items) == 1:
            colour = json.dumps(fa_color(first.get("color")), ensure_ascii=False)
            parts.append('ou(%s, %s, %s, %s)' % (
                json.dumps(first["id"], ensure_ascii=False), name, colour, url))
        else:
            variants = ", ".join(
                '[%s, %s, %s]' % (
                    json.dumps(fa_color(it.get("color")), ensure_ascii=False),
                    json.dumps(it.get("hex") or "#888888", ensure_ascii=False),
                    json.dumps(it["id"], ensure_ascii=False))
                for it in items)
            parts.append('oh(%s, %s, %s, [%s])' % (
                json.dumps(key, ensure_ascii=False), name, url, variants))
    return ", ".join(parts)


def patch_shop_js(data):
    """Swap the product list + add image measurements for uploaded pictures.

    data: the original JavaScript file (bytes). Returns patched bytes.
    If the file is not the shop's main script, it is returned unchanged.
    """
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    if "op = [" not in text or "let or = {" not in text:
        return data
    products = load_products()

    # 1. Replace the product list:  op = [ ... ]  (bracket matching)
    start = text.find("op = [")
    open_br = text.find("[", start)
    depth = 0
    k = open_br
    while k < len(text):
        ch = text[k]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                break
        k += 1
    else:
        return data
    text = text[:start] + "op = [" + build_product_list_js(products) + "]" + text[k + 1:]

    # 1b. Translate the shop's English UI strings to Persian (in memory only).
    text = translate_ui_strings(text)

    # 2. Add image measurements for uploaded pictures (front/side/back views).
    #    Remove any old entry for the same image first, then add the new one.
    extra = {}
    for p in products:
        if not p.get("upload"):
            continue
        path = os.path.join(ROOT, p["upload"].replace("/", os.sep))
        if not os.path.exists(path):
            continue
        w, h = image_size(path)
        geo = default_geometry(w, h)
        for view in ("front", "side", "back"):
            extra["/products/%s-%s.webp" % (p["id"], view)] = geo
    if extra:
        for key in extra:
            # delete an old measurement for this image, if one exists
            text = re.sub(r'%s:\s*\{[^}]*\},\s*' % re.escape(json.dumps(key)),
                          "", text, count=1)
        anchor = "let or = {"
        idx = text.find(anchor) + len(anchor)
        inject = "".join("\n%s: %s," % (json.dumps(key), json.dumps(geo))
                         for key, geo in extra.items())
        text = text[:idx] + inject + text[idx:]
    return text.encode("utf-8")


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    # -- helpers ------------------------------------------------------------
    def _send_bytes(self, data, content_type, status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _send_json(self, obj, status=200):
        self._send_bytes(json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                         "application/json; charset=utf-8", status)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            return json.loads(raw.decode("utf-8")) if raw else {}
        except ValueError:
            return None

    # -- admin API ----------------------------------------------------------
    def _api_products(self, product_id):
        """GET list / POST create / PUT update / DELETE one product."""
        if self.command == "GET" and product_id is None:
            return self._send_json(load_products())
        if self.command == "POST" and product_id is None:
            body = self._read_json_body()
            if body is None or not str(body.get("name") or "").strip():
                return self._send_json({"error": "name is required"}, 400)
            products = load_products()
            new_id = slugify(body.get("name"))
            n = 2
            while any(p["id"] == new_id for p in products):
                new_id = "%s-%d" % (slugify(body.get("name")), n)
                n += 1
            product = {
                "id": new_id,
                "name": str(body["name"]).strip(),
                "color": str(body.get("color") or "").strip(),
                "hex": body.get("hex") if re.fullmatch(r"#[0-9a-fA-F]{6}", str(body.get("hex") or "")) else "#888888",
                "price": str(body.get("price") or "").strip(),
                "group": str(body.get("group") or "").strip() or None,
                "url": slugify(body.get("name")),
                "image": None, "image_small": None, "image_side": None,
                "upload": body.get("upload") or None,
            }
            if not product["upload"]:
                return self._send_json({"error": "an image is required for a new product"}, 400)
            products.append(product)
            save_products(products)
            return self._send_json(product, 201)
        if self.command in ("PUT", "DELETE") and product_id:
            products = load_products()
            target = next((p for p in products if p["id"] == product_id), None)
            if target is None:
                return self._send_json({"error": "product not found"}, 404)
            if self.command == "DELETE":
                products = [p for p in products if p["id"] != product_id]
                save_products(products)
                _delete_upload(target)
                return self._send_json({"ok": True})
            body = self._read_json_body()
            if body is None:
                return self._send_json({"error": "invalid JSON"}, 400)
            old_upload = target.get("upload")
            for field in ("name", "color", "price", "group", "url"):
                if field in body:
                    target[field] = str(body[field] or "").strip() or (None if field == "group" else target[field])
            if "hex" in body and re.fullmatch(r"#[0-9a-fA-F]{6}", str(body.get("hex") or "")):
                target["hex"] = body["hex"]
            if body.get("upload"):
                target["upload"] = body["upload"]
                if old_upload and old_upload != target["upload"]:
                    _delete_upload({"upload": old_upload})
            save_products(products)
            return self._send_json(target)
        return self._send_json({"error": "method not allowed"}, 405)

    def _api_upload(self):
        """POST /api/upload -- multipart form with one file field named 'image'.

        Saves the picture under site/uploads/ and returns its path + size.
        Only image files are accepted.
        """
        ctype = self.headers.get("Content-Type") or ""
        match = re.search(r"multipart/form-data;\s*boundary=(.+)", ctype)
        if not match:
            return self._send_json({"error": "expected a multipart file upload"}, 400)
        boundary = match.group(1).strip().strip('"').encode()
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        file_bytes, filename = _parse_multipart_file(raw, boundary)
        if file_bytes is None:
            return self._send_json({"error": "no image file received"}, 400)
        ext = os.path.splitext(filename or "")[1].lower()
        if ext not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
            return self._send_json({"error": "only PNG, JPG, WEBP or GIF pictures"}, 400)
        if ext == ".jpeg":
            ext = ".jpg"
        os.makedirs(UPLOADS_DIR, exist_ok=True)
        save_name = "up-%s%s" % (os.urandom(8).hex(), ext)
        path = os.path.join(UPLOADS_DIR, save_name)
        with open(path, "wb") as f:
            f.write(file_bytes)
        w, h = image_size(path)
        return self._send_json({"upload": "uploads/" + save_name,
                                "width": w, "height": h}, 201)

    # -- routing ------------------------------------------------------------
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/", "/index.html"):
            # Persian storefront (RTL, Vazirmatn) -- the shop's home page.
            try:
                with open(os.path.join(ROOT, "fa.html"), "rb") as f:
                    return self._send_bytes(f.read(), "text/html; charset=utf-8")
            except OSError:
                pass  # fall through to the old English export
        if path == "/rack":
            # The original rack page, translated to Persian in place.
            try:
                with open(os.path.join(ROOT, "index.html"), "rb") as f:
                    return self._send_bytes(f.read(), "text/html; charset=utf-8")
            except OSError:
                return self.send_error(404)
        if path == "/api/products":
            return self._api_products(None)
        if path.startswith("/api/products/"):
            return self._api_products(path.rsplit("/", 1)[-1])
        if path in ("/admin", "/admin.html"):
            try:
                with open(ADMIN_FILE, "rb") as f:
                    return self._send_bytes(f.read(), "text/html; charset=utf-8")
            except OSError:
                return self.send_error(404, "admin.html not found")
        if path == "/_next/image":
            qs = parse_qs(parsed.query)
            width = int(qs.get("w", ["0"])[0] or 0)
            fpath, ctype = resolve_image(qs.get("url", [""])[0], width)
            if not fpath or not os.path.exists(fpath):
                return self.send_error(404)
            with open(fpath, "rb") as f:
                return self._send_bytes(f.read(), ctype)
        if path.startswith("/_next/static/chunks/") and path.endswith(".js"):
            fpath = os.path.join(ROOT, path.lstrip("/").replace("/", os.sep))
            if os.path.exists(fpath):
                with open(fpath, "rb") as f:
                    return self._send_bytes(patch_shop_js(f.read()),
                                            "text/javascript; charset=utf-8")
            return self.send_error(404)
        self.path = path  # drop query strings like ?favicon...
        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/products":
            return self._api_products(None)
        if parsed.path == "/api/upload":
            return self._api_upload()
        return self._send_json({"error": "not found"}, 404)

    def do_PUT(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/products/"):
            return self._api_products(parsed.path.rsplit("/", 1)[-1])
        return self._send_json({"error": "not found"}, 404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/products/"):
            return self._api_products(parsed.path.rsplit("/", 1)[-1])
        return self._send_json({"error": "not found"}, 404)

    def log_message(self, *args):
        pass  # keep the terminal window quiet


def _delete_upload(product):
    """Delete an uploaded picture file when its product is removed/replaced."""
    upload = (product or {}).get("upload")
    if not upload:
        return
    path = os.path.join(ROOT, upload.replace("/", os.sep))
    if os.path.abspath(path).startswith(os.path.abspath(UPLOADS_DIR)):
        try:
            os.remove(path)
        except OSError:
            pass


def _parse_multipart_file(raw, boundary):
    """Tiny multipart parser (no extra installs). Returns (bytes, filename)."""
    parts = raw.split(b"--" + boundary)
    for part in parts:
        if b'Content-Disposition: form-data' not in part:
            continue
        header, _, body = part.partition(b"\r\n\r\n")
        if b'name="image"' not in header:
            continue
        m = re.search(rb'filename="([^"]*)"', header)
        filename = m.group(1).decode("utf-8", "replace") if m else ""
        if body.endswith(b"\r\n"):
            body = body[:-2]
        return body, filename
    return None, None


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://localhost:{port}"
    print(f"Site is running at {url}  (press Ctrl+C to stop)")
    print(f"Admin panel: {url}/admin")
    if os.environ.get("NO_BROWSER") != "1":
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
