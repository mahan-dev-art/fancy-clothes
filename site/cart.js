/* Delta Shop — shared cart + checkout.
   Used by both storefront views (the Persian home page "/" and the rack
   view "/rack"). The cart lives in the browser's localStorage; orders are
   sent to POST /api/orders and stored on the server. */
(function () {
  "use strict";

  var CART_KEY = "delta-shop-cart-v1";
  var SIZES = ["S", "M", "L", "XL"];
  var DEFAULT_SIZE = "M";

  var COLOR_FA = {
    "White": "سفید", "Black": "مشکی", "Pink": "صورتی", "Yellow": "زرد",
    "Blue": "آبی", "Sand": "شنی", "Red": "قرمز", "Green": "سبز",
    "Grey": "خاکستری", "Gray": "خاکستری", "Beige": "کرم",
    "Brown": "قهوه‌ای", "Orange": "نارنجی", "Purple": "بنفش"
  };

  function faNum(n) {
    return Number(n).toLocaleString("fa-IR");
  }
  function faColor(color) {
    return COLOR_FA[color] || color || "";
  }
  function priceDigits(p) {
    var d = String(p == null ? "" : p).replace(/[^\d]/g, "");
    if (!d) return null;
    var n = parseInt(d, 10);
    return isFinite(n) ? n : null;
  }
  function formatPrice(p) {
    var n = priceDigits(p);
    return n == null ? "" : faNum(n) + " تومان";
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  /* ---------------- cart state ---------------- */
  function loadCart() {
    try {
      var c = JSON.parse(localStorage.getItem(CART_KEY) || "[]");
      return Array.isArray(c) ? c : [];
    } catch (e) {
      return [];
    }
  }
  function saveCart(cart) {
    try {
      localStorage.setItem(CART_KEY, JSON.stringify(cart));
    } catch (e) { /* storage unavailable: cart still works in memory */ }
  }
  function cartCount(cart) {
    return cart.reduce(function (n, it) { return n + (it.qty || 1); }, 0);
  }
  function cartTotal(cart) {
    return cart.reduce(function (sum, it) {
      var p = priceDigits(it.price);
      return sum + (p == null ? 0 : p * (it.qty || 1));
    }, 0);
  }
  function cartHasUnpriced(cart) {
    return cart.some(function (it) { return priceDigits(it.price) == null; });
  }
  function addToCart(item) {
    var cart = loadCart();
    var found = null;
    cart.forEach(function (it) {
      if (it.id === item.id && it.color === item.color && it.size === item.size) found = it;
    });
    if (found) {
      found.qty = (found.qty || 1) + 1;
    } else {
      cart.push({
        id: item.id, name: item.name, color: item.color || "",
        size: item.size || DEFAULT_SIZE, price: item.price || "",
        qty: 1, image: item.image || ""
      });
    }
    saveCart(cart);
    renderCart();
    toast("به سبد خرید اضافه شد");
  }
  function setQty(index, qty) {
    var cart = loadCart();
    if (!cart[index]) return;
    cart[index].qty = Math.max(1, qty);
    saveCart(cart);
    renderCart();
  }
  function removeItem(index) {
    var cart = loadCart();
    cart.splice(index, 1);
    saveCart(cart);
    renderCart();
  }
  function clearCart() {
    saveCart([]);
    renderCart();
  }

  /* ---------------- UI: styles, button, drawer ---------------- */
  var CSS =
    ".delta-fab{position:fixed;left:16px;bottom:16px;z-index:1000;" +
    "background:#c9a24b;color:#1a1408;border:none;border-radius:999px;" +
    "padding:12px 20px;font-family:inherit;font-size:15px;font-weight:700;" +
    "cursor:pointer;box-shadow:0 6px 24px rgba(0,0,0,.45)}" +
    ".delta-fab .delta-count{background:#1a1408;color:#e8c97a;border-radius:999px;" +
    "min-width:22px;height:22px;display:inline-block;text-align:center;" +
    "line-height:22px;font-size:13px;margin-inline-start:8px;padding:0 5px}" +
    ".delta-overlay{position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:1001;" +
    "opacity:0;pointer-events:none;transition:opacity .25s}" +
    ".delta-overlay.open{opacity:1;pointer-events:auto}" +
    ".delta-drawer{position:fixed;top:0;bottom:0;left:0;width:min(420px,94vw);" +
    "background:#211d18;color:#f2ead9;z-index:1002;transform:translateX(-105%);" +
    "transition:transform .3s ease;display:flex;flex-direction:column;" +
    "font-family:inherit;box-shadow:0 0 40px rgba(0,0,0,.5)}" +
    ".delta-drawer.open{transform:translateX(0)}" +
    ".delta-drawer header{display:flex;justify-content:space-between;align-items:center;" +
    "padding:16px 18px;border-bottom:1px solid #3a322a}" +
    ".delta-drawer header h2{margin:0;font-size:19px}" +
    ".delta-close{background:none;border:none;color:#b8a894;font-size:22px;cursor:pointer}" +
    ".delta-body{flex:1;overflow-y:auto;padding:16px 18px}" +
    ".delta-item{display:flex;gap:12px;padding:12px 0;border-bottom:1px solid #332b23}" +
    ".delta-item img{width:64px;height:84px;object-fit:cover;border-radius:8px;background:#3a322a}" +
    ".delta-item .delta-info{flex:1;min-width:0}" +
    ".delta-item .delta-name{font-weight:700;font-size:14px;line-height:1.5}" +
    ".delta-item .delta-meta{color:#b8a894;font-size:13px;margin-top:2px}" +
    ".delta-item .delta-line{font-weight:700;font-size:14px;margin-top:6px}" +
    ".delta-qty{display:inline-flex;align-items:center;gap:10px;margin-top:8px}" +
    ".delta-qty button{width:28px;height:28px;border-radius:50%;border:1px solid #6b5a44;" +
    "background:none;color:#e8c97a;font-size:16px;cursor:pointer}" +
    ".delta-remove{background:none;border:none;color:#d98a7a;font-size:13px;" +
    "cursor:pointer;padding:0;margin-top:8px}" +
    ".delta-empty{text-align:center;color:#b8a894;padding:40px 0}" +
    ".delta-foot{border-top:1px solid #3a322a;padding:16px 18px}" +
    ".delta-total{display:flex;justify-content:space-between;font-weight:700;font-size:17px}" +
    ".delta-note{color:#b8a894;font-size:13px;margin:8px 0 0;line-height:1.7}" +
    ".delta-btn{display:block;width:100%;text-align:center;background:#c9a24b;color:#1a1408;" +
    "border:none;border-radius:999px;padding:12px 18px;font-family:inherit;" +
    "font-size:15px;font-weight:700;cursor:pointer;margin-top:14px}" +
    ".delta-btn:hover{background:#d9b45e}" +
    ".delta-btn.ghost{background:none;color:#e8c97a;border:1px solid #6b5a44}" +
    ".delta-field{margin-bottom:12px}" +
    ".delta-field label{display:block;font-size:13px;color:#b8a894;margin-bottom:4px}" +
    ".delta-field input,.delta-field textarea{width:100%;padding:10px;border:1px solid #4a4034;" +
    "border-radius:8px;background:#16130f;color:#f2ead9;font-family:inherit;font-size:14px;" +
    "box-sizing:border-box}" +
    ".delta-done{text-align:center;padding:30px 0}" +
    ".delta-done .delta-big{font-size:26px;font-weight:700;color:#e8c97a;margin:12px 0}" +
    ".delta-done p{color:#b8a894;line-height:1.9}" +
    ".delta-toast{position:fixed;bottom:80px;left:50%;transform:translateX(-50%) translateY(20px);" +
    "background:#211d18;color:#f2ead9;border:1px solid #c9a24b;border-radius:999px;" +
    "padding:10px 22px;font-size:14px;z-index:1100;opacity:0;pointer-events:none;" +
    "transition:opacity .25s,transform .25s;white-space:nowrap}" +
    ".delta-toast.show{opacity:1;transform:translateX(-50%) translateY(0)}" +
    ".delta-sizes{display:flex;gap:8px;margin:10px 0}" +
    ".delta-sizes button{min-width:44px;height:38px;border-radius:8px;border:1px solid #6b5a44;" +
    "background:none;color:#f2ead9;font-family:inherit;font-size:14px;cursor:pointer}" +
    ".delta-sizes button[aria-pressed=\"true\"]{background:#c9a24b;color:#1a1408;" +
    "border-color:#c9a24b;font-weight:700}" +
    ".delta-rack-price{font-weight:700;font-size:16px;color:#e8c97a;margin:6px 0}" +
    ".delta-rack-add{display:block;width:100%;text-align:center;background:#c9a24b;color:#1a1408;" +
    "border:none;border-radius:999px;padding:11px 16px;font-family:inherit;" +
    "font-size:15px;font-weight:700;cursor:pointer;margin-top:12px}" +
    ".delta-rack-add:hover{background:#d9b45e}";

  var fab, overlay, drawer, bodyEl, footEl, toastEl, toastTimer;
  var styleAdded = false;

  function makeStyle() {
    if (styleAdded || document.getElementById("delta-cart-style")) return;
    var st = document.createElement("style");
    st.id = "delta-cart-style";
    st.textContent = CSS;
    document.head.appendChild(st);
    styleAdded = true;
  }
  function makeFab() {
    var old = document.getElementById("delta-cart-fab");
    if (old) { fab = old; return; }
    fab = document.createElement("button");
    fab.id = "delta-cart-fab";
    fab.type = "button";
    fab.className = "delta-fab";
    fab.innerHTML = "🛒 سبد خرید <span class=\"delta-count\">۰</span>";
    fab.addEventListener("click", openDrawer);
    document.body.appendChild(fab);
  }
  function makeOverlay() {
    var old = document.getElementById("delta-cart-overlay");
    if (old) { overlay = old; return; }
    overlay = document.createElement("div");
    overlay.id = "delta-cart-overlay";
    overlay.className = "delta-overlay";
    overlay.addEventListener("click", closeDrawer);
    document.body.appendChild(overlay);
  }
  function makeDrawer() {
    var old = document.getElementById("delta-cart-drawer");
    if (old) {
      drawer = old;
      bodyEl = drawer.querySelector(".delta-body");
      footEl = drawer.querySelector(".delta-foot");
      return;
    }
    drawer = document.createElement("aside");
    drawer.id = "delta-cart-drawer";
    drawer.className = "delta-drawer";
    drawer.setAttribute("aria-label", "سبد خرید");
    drawer.innerHTML =
      "<header><h2>سبد خرید</h2>" +
      "<button type=\"button\" class=\"delta-close\" aria-label=\"بستن\">✕</button></header>" +
      "<div class=\"delta-body\"></div>" +
      "<div class=\"delta-foot\"></div>";
    drawer.querySelector(".delta-close").addEventListener("click", closeDrawer);
    document.body.appendChild(drawer);
    bodyEl = drawer.querySelector(".delta-body");
    footEl = drawer.querySelector(".delta-foot");
  }
  function makeToast() {
    var old = document.getElementById("delta-cart-toast");
    if (old) { toastEl = old; return; }
    toastEl = document.createElement("div");
    toastEl.id = "delta-cart-toast";
    toastEl.className = "delta-toast";
    document.body.appendChild(toastEl);
  }
  // The rack page is a React app: hydration removes nodes it did not
  // render, so anything appended to <body> can vanish after load.
  // Re-create any missing piece whenever the body changes.
  function ensureUI() {
    makeStyle();
    makeFab();
    makeOverlay();
    makeDrawer();
    makeToast();
  }
  function buildUI() { ensureUI(); }

  function toast(msg) {
    ensureUI();
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.classList.remove("show"); }, 2200);
  }

  function openDrawer() {
    ensureUI();
    renderCart();
    if (overlay) overlay.classList.add("open");
    if (drawer) drawer.classList.add("open");
  }
  function closeDrawer() {
    if (overlay) overlay.classList.remove("open");
    if (drawer) drawer.classList.remove("open");
  }

  function renderCart() {
    ensureUI();
    if (!bodyEl) return;
    var cart = loadCart();
    var count = cartCount(cart);
    var badge = fab.querySelector(".delta-count");
    badge.textContent = faNum(count);
    badge.style.display = count ? "" : "none";

    showCartView(cart);
  }

  function showCartView(cart) {
    if (!cart.length) {
      bodyEl.innerHTML = "<p class=\"delta-empty\">سبد خریدت خالیه.<br>یه لباس انتخاب کن و به سبد اضافه‌ش کن.</p>";
      footEl.innerHTML = "";
      return;
    }
    var html = "";
    cart.forEach(function (it, i) {
      var price = formatPrice(it.price);
      var line = priceDigits(it.price) == null
        ? "تماس بگیرید"
        : faNum(priceDigits(it.price) * (it.qty || 1)) + " تومان";
      html += "<div class=\"delta-item\">" +
        (it.image ? "<img src=\"" + esc(it.image) + "\" alt=\"\">" : "") +
        "<div class=\"delta-info\">" +
        "<div class=\"delta-name\">" + esc(it.name) + "</div>" +
        "<div class=\"delta-meta\">رنگ: " + esc(it.color || "—") + " · سایز: " + esc(it.size || "—") + "</div>" +
        "<div class=\"delta-line\">" + esc(line) + "</div>" +
        "<div class=\"delta-qty\">" +
        "<button type=\"button\" data-dec=\"" + i + "\" aria-label=\"کم کردن\">−</button>" +
        "<span>" + faNum(it.qty || 1) + "</span>" +
        "<button type=\"button\" data-inc=\"" + i + "\" aria-label=\"زیاد کردن\">+</button>" +
        "</div>" +
        "<button type=\"button\" class=\"delta-remove\" data-del=\"" + i + "\">حذف از سبد</button>" +
        "</div></div>";
    });
    bodyEl.innerHTML = html;
    bodyEl.querySelectorAll("[data-inc]").forEach(function (b) {
      b.addEventListener("click", function () { setQty(+b.dataset.inc, (loadCart()[+b.dataset.inc].qty || 1) + 1); });
    });
    bodyEl.querySelectorAll("[data-dec]").forEach(function (b) {
      b.addEventListener("click", function () {
        var idx = +b.dataset.dec;
        var q = (loadCart()[idx].qty || 1) - 1;
        if (q < 1) removeItem(idx); else setQty(idx, q);
      });
    });
    bodyEl.querySelectorAll("[data-del]").forEach(function (b) {
      b.addEventListener("click", function () { removeItem(+b.dataset.del); });
    });

    var total = cartTotal(cart);
    var foot = "<div class=\"delta-total\"><span>جمع کل</span><span>" +
      (total ? faNum(total) + " تومان" : "—") + "</span></div>";
    if (cartHasUnpriced(cart)) {
      foot += "<p class=\"delta-note\">قیمت اقلام بدون قیمت پس از ثبت سفارش اعلام می‌شود.</p>";
    }
    foot += "<button type=\"button\" class=\"delta-btn\" id=\"delta-checkout\">ثبت سفارش</button>" +
      "<button type=\"button\" class=\"delta-btn ghost\" id=\"delta-continue\">ادامه خرید</button>";
    footEl.innerHTML = foot;
    footEl.querySelector("#delta-checkout").addEventListener("click", showOrderForm);
    footEl.querySelector("#delta-continue").addEventListener("click", closeDrawer);
  }

  function showOrderForm() {
    var cart = loadCart();
    if (!cart.length) return;
    bodyEl.innerHTML =
      "<h3 style=\"margin:0 0 4px\">ثبت سفارش</h3>" +
      "<p class=\"delta-note\" style=\"margin:0 0 16px\">مشخصاتت رو بنویس؛ بعد از ثبت، برای تایید سفارش باهات تماس می‌گیریم.</p>" +
      "<div class=\"delta-field\"><label for=\"delta-f-name\">نام و نام خانوادگی *</label>" +
      "<input id=\"delta-f-name\" type=\"text\" autocomplete=\"name\"></div>" +
      "<div class=\"delta-field\"><label for=\"delta-f-phone\">شماره تماس *</label>" +
      "<input id=\"delta-f-phone\" type=\"tel\" inputmode=\"tel\" autocomplete=\"tel\" dir=\"ltr\" style=\"text-align:right\"></div>" +
      "<div class=\"delta-field\"><label for=\"delta-f-address\">آدرس *</label>" +
      "<textarea id=\"delta-f-address\" rows=\"3\"></textarea></div>" +
      "<div class=\"delta-field\"><label for=\"delta-f-notes\">توضیحات (اختیاری)</label>" +
      "<textarea id=\"delta-f-notes\" rows=\"2\"></textarea></div>" +
      "<p class=\"delta-note\" id=\"delta-form-err\" style=\"color:#e8a08f;display:none\"></p>";
    footEl.innerHTML =
      "<button type=\"button\" class=\"delta-btn\" id=\"delta-submit-order\">ثبت نهایی سفارش</button>" +
      "<button type=\"button\" class=\"delta-btn ghost\" id=\"delta-back-cart\">برگشت به سبد</button>";
    footEl.querySelector("#delta-back-cart").addEventListener("click", function () { renderCart(); });
    footEl.querySelector("#delta-submit-order").addEventListener("click", submitOrder);
  }

  function submitOrder() {
    var err = document.getElementById("delta-form-err");
    var name = document.getElementById("delta-f-name").value.trim();
    var phone = document.getElementById("delta-f-phone").value.trim();
    var address = document.getElementById("delta-f-address").value.trim();
    var notes = document.getElementById("delta-f-notes").value.trim();
    if (!name || !phone || !address) {
      err.textContent = "نام، شماره تماس و آدرس رو کامل بنویس.";
      err.style.display = "";
      return;
    }
    err.style.display = "none";
    var cart = loadCart();
    var btn = document.getElementById("delta-submit-order");
    btn.disabled = true;
    btn.textContent = "در حال ثبت…";
    fetch("/api/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        customer: { name: name, phone: phone, address: address, notes: notes },
        items: cart.map(function (it) {
          return { id: it.id, color: it.color, size: it.size, qty: it.qty };
        })
      })
    }).then(function (res) {
      return res.json().then(function (data) {
        if (!res.ok) throw new Error(data.error || ("خطا " + res.status));
        return data;
      });
    }).then(function (order) {
      clearCart();
      bodyEl.innerHTML =
        "<div class=\"delta-done\">" +
        "<div style=\"font-size:44px\">✅</div>" +
        "<h3 style=\"margin:8px 0 0\">سفارشت ثبت شد!</h3>" +
        "<div class=\"delta-big\">شماره سفارش: " + esc(order.number) + "</div>" +
        "<p>برای تایید سفارش و اعلام هزینه ارسال با تو تماس می‌گیریم.<br>شماره سفارشت رو نگه دار.</p>" +
        "</div>";
      footEl.innerHTML =
        "<button type=\"button\" class=\"delta-btn\" id=\"delta-done-close\">باشه، فهمیدم</button>";
      footEl.querySelector("#delta-done-close").addEventListener("click", closeDrawer);
    }).catch(function (e) {
      err.textContent = "خطا در ثبت سفارش: " + e.message;
      err.style.display = "";
      btn.disabled = false;
      btn.textContent = "ثبت نهایی سفارش";
    });
  }

  /* ---------------- rack view integration ---------------- */
  var productsByKey = null;   // "name|faColor" -> product; "name:<name>" -> [products]
  var rackSize = DEFAULT_SIZE;

  function rackProducts() {
    if (productsByKey) return Promise.resolve(productsByKey);
    return fetch("/api/products").then(function (r) { return r.json(); })
      .then(function (products) {
        productsByKey = {};
        products.forEach(function (p) {
          productsByKey[p.name + "|" + faColor(p.color)] = p;
          var k = "name:" + p.name;
          (productsByKey[k] = productsByKey[k] || []).push(p);
        });
        return productsByKey;
      }).catch(function () {
        productsByKey = {};
        return productsByKey;
      });
  }

  // Find the product shown in the rack detail panel. Colour tags only
  // render for multi-colourway products, so for single-colour products
  // the colour is unknown from the DOM -- fall back to the unique
  // product with that name.
  function findRackProduct(map, name, color) {
    if (!map) return null;
    if (color && map[name + "|" + color]) return map[name + "|" + color];
    var byName = map["name:" + name] || [];
    if (byName.length === 1) return byName[0];
    if (color) {
      for (var i = 0; i < byName.length; i++) {
        if (faColor(byName[i].color) === color) return byName[i];
      }
    }
    return byName.length ? byName[0] : null;
  }

  function rackCurrent() {
    var info = document.querySelector(".info");
    if (!info) return null;
    var nameEl = info.querySelector(".info-name");
    if (!nameEl) return null;
    var name = nameEl.textContent.trim();
    var color = "";
    var active = document.querySelector(".tag-hit[aria-pressed=\"true\"] .tag-face")
      || document.querySelector(".tag-hit .tag-face");
    if (active) color = active.textContent.trim();
    return { name: name, color: color, info: info };
  }

  function enhanceRackDetail() {
    var cur = rackCurrent();
    if (!cur || cur.info.querySelector("[data-delta-enhanced]")) return;
    var wrap = document.createElement("div");
    wrap.setAttribute("data-delta-enhanced", "1");
    wrap.innerHTML =
      "<div class=\"delta-rack-price\">در حال بارگذاری قیمت…</div>" +
      "<div style=\"color:#b8a894;font-size:13px;margin-top:8px\">سایز:</div>" +
      "<div class=\"delta-sizes\">" +
      SIZES.map(function (s) {
        return "<button type=\"button\" data-size=\"" + s + "\" aria-pressed=\"" +
          (s === rackSize ? "true" : "false") + "\">" + s + "</button>";
      }).join("") +
      "</div>" +
      "<button type=\"button\" class=\"delta-rack-add\">🛒 افزودن به سبد</button>";
    cur.info.appendChild(wrap);
    wrap.querySelectorAll("[data-size]").forEach(function (b) {
      b.addEventListener("click", function () {
        rackSize = b.dataset.size;
        wrap.querySelectorAll("[data-size]").forEach(function (x) {
          x.setAttribute("aria-pressed", x.dataset.size === rackSize ? "true" : "false");
        });
      });
    });
    wrap.querySelector(".delta-rack-add").addEventListener("click", function () {
      addCurrentRackItem();
    });
    // price for the currently shown product (by name + colour)
    var priceEl = wrap.querySelector(".delta-rack-price");
    rackProducts().then(function (map) {
      var p = findRackProduct(map, cur.name, cur.color);
      if (p) {
        var price = formatPrice(p.price);
        priceEl.textContent = price ? ("قیمت: " + price) : "قیمت: تماس بگیرید";
        wrap.dataset.pid = p.id;
      } else {
        priceEl.textContent = "قیمت: تماس بگیرید";
      }
    });
  }

  function addCurrentRackItem() {
    var cur = rackCurrent();
    if (!cur) return;
    rackProducts().then(function (map) {
      var p = findRackProduct(map, cur.name, cur.color);
      var img = "";
      var imgEl = document.querySelector(".focus-anchor img") || document.querySelector(".rack-item img");
      if (imgEl && imgEl.currentSrc) img = imgEl.currentSrc;
      addToCart({
        id: p ? p.id : cur.name,
        name: cur.name,
        color: p ? faColor(p.color) : cur.color,
        size: rackSize,
        price: p ? p.price : "",
        image: img
      });
    });
  }

  function initRack() {
    if (!document.querySelector(".rack")) return;
    // the old external checkout links now point to "#" -- make them add to cart
    document.addEventListener("click", function (e) {
      var a = e.target.closest ? e.target.closest("a.info-cta, a[href=\"#\"]") : null;
      if (!a) return;
      if (!document.querySelector(".info")) return;
      e.preventDefault();
      addCurrentRackItem();
    });
    // the detail panel is re-rendered by the shop app; re-inject our controls
    var observer = new MutationObserver(function () { enhanceRackDetail(); });
    observer.observe(document.body, { childList: true, subtree: true });
    enhanceRackDetail();
  }

  /* ---------------- boot ---------------- */
  function init() {
    buildUI();
    renderCart();
    if (document.body) {
      // Re-create the cart UI if React hydration (rack view) removes it.
      var uiObs = new MutationObserver(function () {
        if (!document.getElementById("delta-cart-fab") ||
            !document.getElementById("delta-cart-drawer")) {
          ensureUI();
          renderCart();
        }
      });
      uiObs.observe(document.body, { childList: true });
      setTimeout(function () { ensureUI(); renderCart(); }, 1500);
    }
    initRack();
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  window.DeltaCart = {
    add: addToCart,
    open: openDrawer,
    close: closeDrawer,
    count: function () { return cartCount(loadCart()); }
  };
})();
