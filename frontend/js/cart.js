// ─────────────────────────────────────────────────────────
// CART MODULE — dùng chung cho index + product page
// ─────────────────────────────────────────────────────────
// productMap[asin] = {asin, title, price, image} — đăng ký bởi productCard()
const productMap = {};

// Cart key riêng cho từng user — guest dùng key riêng, không share giữa các tài khoản
function getCartKey() {
  const u = getUser();
  return u ? `recsys_cart_${u.id}` : 'recsys_cart_guest';
}

// ─── CRUD ───
function getCart() {
  try { return JSON.parse(localStorage.getItem(getCartKey())) || []; } catch { return []; }
}

function saveCart(cart) {
  localStorage.setItem(getCartKey(), JSON.stringify(cart));
  updateCartBadge();
}

function addToCart(item) {
  const cart = getCart();
  const existing = cart.find(c => c.asin === item.asin);
  if (existing) {
    existing.qty += 1;
  } else {
    cart.push({ asin: item.asin, title: item.title, price: item.price ?? null, image: item.image || '', qty: 1 });
  }
  saveCart(cart);

  if (isLoggedIn()) {
    authFetch(`${API}/track/cart`, {
      method: 'POST',
      body: JSON.stringify({ asin: item.asin }),
    }).catch(() => {});
  }

  showCartToast(item.title);
}

function cartAddFromMap(asin) {
  const item = productMap[asin];
  if (item) addToCart(item);
}

function removeFromCart(asin) {
  saveCart(getCart().filter(c => c.asin !== asin));
  renderCartPanel();
}

function changeQty(asin, delta) {
  const cart = getCart();
  const item = cart.find(c => c.asin === asin);
  if (!item) return;
  item.qty += delta;
  if (item.qty <= 0) cart.splice(cart.indexOf(item), 1);
  saveCart(cart);
  renderCartPanel();
}

function getCartCount() {
  return getCart().reduce((s, c) => s + c.qty, 0);
}

function getCartTotal() {
  return getCart().reduce((s, c) => s + (c.price || 0) * c.qty, 0);
}

// ─── Badge ───
function updateCartBadge() {
  const badge = document.getElementById('cart-badge');
  if (!badge) return;
  const n = getCartCount();
  badge.textContent = n > 99 ? '99+' : n;
  badge.classList.toggle('hidden', n === 0);
}

// ─── Panel ───
function toggleCart() {
  const overlay = document.getElementById('cart-overlay');
  const panel   = document.getElementById('cart-panel');
  const isOpen  = panel.classList.toggle('open');
  overlay.classList.toggle('open', isOpen);
  if (isOpen) renderCartPanel();
}

function renderCartPanel() {
  const items   = getCart();
  const listEl  = document.getElementById('cart-items-list');
  const totalEl = document.getElementById('cart-total-price');
  const recSec  = document.getElementById('cart-rec-section');
  if (!listEl) return;

  if (!items.length) {
    listEl.innerHTML = `<div class="cart-empty"><div class="cart-empty-icon">🛒</div><p>Giỏ hàng đang trống</p></div>`;
    if (totalEl) totalEl.textContent = '$0.00';
    if (recSec)  recSec.classList.add('hidden');
    return;
  }

  listEl.innerHTML = items.map(item => {
    const img = item.image
      ? `<img src="${item.image}" onerror="this.outerHTML='<span style=font-size:28px>📦</span>'">`
      : '<span style="font-size:28px">📦</span>';
    const price = item.price != null ? `$${item.price.toFixed(2)}` : 'Liên hệ';
    const asin  = escapeCartAttr(item.asin);
    return `
      <div class="cart-item">
        <div class="cart-item-img">${img}</div>
        <div class="cart-item-info">
          <div class="cart-item-title">${escapeCartHtml(item.title)}</div>
          <div class="cart-item-price">${price}</div>
          <div class="cart-item-qty">
            <button class="qty-btn" onclick="changeQty('${asin}',-1)">−</button>
            <span class="qty-val">${item.qty}</span>
            <button class="qty-btn" onclick="changeQty('${asin}',1)">+</button>
          </div>
        </div>
        <button class="cart-item-remove" onclick="removeFromCart('${asin}')" title="Xóa">×</button>
      </div>`;
  }).join('');

  const total = getCartTotal();
  if (totalEl) totalEl.textContent = total > 0 ? `$${total.toFixed(2)}` : '—';

  loadCartRecommendations();
}

// ─── Cart-based recommendations ───
async function loadCartRecommendations() {
  const recSec  = document.getElementById('cart-rec-section');
  const recList = document.getElementById('cart-rec-list');
  if (!recSec || !recList) return;

  const asins = getCart().map(c => c.asin);
  if (!asins.length) { recSec.classList.add('hidden'); return; }

  try {
    const res = await fetch(`${API}/cart/recommend?k=8`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ asins }),
    });
    if (!res.ok) { recSec.classList.add('hidden'); return; }
    const data = await res.json();
    if (!data.items.length) { recSec.classList.add('hidden'); return; }

    recList.innerHTML = data.items.map(item => {
      const img   = item.image
        ? `<img src="${item.image}" onerror="this.outerHTML='<span style=font-size:24px>📦</span>'">`
        : '<span style="font-size:24px">📦</span>';
      const price = item.price != null ? `$${item.price.toFixed(2)}` : 'Liên hệ';
      const asin  = escapeCartAttr(item.asin);
      productMap[item.asin] = { asin: item.asin, title: item.title, price: item.price ?? null, image: item.image || '' };
      return `
        <div class="cart-rec-card" onclick="window.location.href='/product/${asin}'">
          <div class="cart-rec-img">${img}</div>
          <div class="cart-rec-info">
            <div class="cart-rec-name">${escapeCartHtml(item.title)}</div>
            <div class="cart-rec-price">${price}</div>
            <button class="cart-rec-add" onclick="event.stopPropagation(); cartAddFromMap('${asin}')">+ Thêm</button>
          </div>
        </div>`;
    }).join('');
    recSec.classList.remove('hidden');
  } catch(e) {
    recSec.classList.add('hidden');
  }
}

// ─── Toast ───
function showCartToast(title) {
  let toast = document.getElementById('cart-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'cart-toast';
    toast.className = 'cart-toast';
    document.body.appendChild(toast);
  }
  const short = title.length > 45 ? title.slice(0, 45) + '…' : title;
  toast.innerHTML = `<span style="color:#2ecc71;margin-right:6px;">✓</span> Đã thêm: ${escapeCartHtml(short)}`;
  toast.classList.add('show');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => toast.classList.remove('show'), 2500);
}

// ─── Utils ───
function escapeCartHtml(s) {
  return String(s).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
}
function escapeCartAttr(s) {
  return String(s).replace(/'/g, "\\'");
}

// ─── Init ───
function initCart() {
  updateCartBadge();
  document.getElementById('cart-overlay')?.addEventListener('click', () => {
    document.getElementById('cart-overlay').classList.remove('open');
    document.getElementById('cart-panel').classList.remove('open');
  });
}
