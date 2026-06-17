// ─────────────────────────────────────────────────────────
// PRODUCT DETAIL PAGE
// ─────────────────────────────────────────────────────────

let currentAsin = null;
let userRating = 0;

// ─── User menu (giống index) ───
function renderUserMenuProduct() {
  const menu = document.getElementById('user-menu');
  const welcome = document.getElementById('welcome-text');
  const logoutLink = document.getElementById('logout-link');
  const user = getUser();

  if (user) {
    const initial = (user.username || 'U').charAt(0).toUpperCase();
    menu.innerHTML = `
      <div class="avatar">${initial}</div>
      <div>
        <div style="font-size:12px;opacity:0.85;">Xin chào</div>
        <div style="font-weight:600;">${user.username}</div>
      </div>
      <a href="/history" class="menu-history-link">📋 Lịch sử</a>
      <button class="btn-logout" onclick="logout()">Đăng xuất</button>
    `;
    welcome.textContent = `👋 ${user.full_name || user.username}`;
    logoutLink.classList.remove('hidden');
  } else {
    menu.innerHTML = `
      <a href="/register" style="opacity:0.9;">Đăng ký</a>
      <span style="opacity:0.5;">|</span>
      <a href="/login" class="btn-login">Đăng nhập</a>
    `;
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
}

const loading = {
  show() { document.getElementById('loading').classList.remove('hidden'); },
  hide() { document.getElementById('loading').classList.add('hidden'); },
};

// ─── Product card ───
function productCard(item) {
  productMap[item.asin] = { asin: item.asin, title: item.title, price: item.price ?? null, image: item.image || '' };

  const img = item.image
    ? `<img src="${item.image}" loading="lazy" onerror="this.outerHTML='<div class=&quot;placeholder&quot;>📦</div>'">`
    : `<div class="placeholder">📦</div>`;
  const price = item.price !== null && item.price !== undefined
    ? `<span class="currency">$</span>${item.price.toFixed(2)}`
    : 'Liên hệ';
  const rating = item.rating ? `⭐ ${item.rating.toFixed(1)}` : '';
  const sold = item.sold ? `Đã bán ${item.sold > 1000 ? (item.sold/1000).toFixed(1)+'k' : item.sold}` : '';
  const asin  = item.asin.replace(/'/g, "\\'");
  return `
    <div class="product-card" onclick="window.location.href='/product/${asin}'">
      <div class="product-image-wrap">${img}</div>
      <div class="product-info">
        <div class="product-title">${escapeHtml(item.title)}</div>
        <div class="product-price">${price}</div>
        <div class="product-meta">
          <span class="product-rating">${rating}</span>
          <span class="product-sold">${sold}</span>
        </div>
      </div>
      <button class="btn-add-cart" onclick="event.stopPropagation(); cartAddFromMap('${asin}')">
        + Thêm vào giỏ
      </button>
    </div>
  `;
}

// ─── Render product detail ───
function renderProduct(p) {
  productMap[p.asin] = { asin: p.asin, title: p.title, price: p.price ?? null, image: p.image || '' };
  const img = p.image
    ? `<img src="${p.image}" onerror="this.outerHTML='<div style=&quot;font-size:120px;color:#ddd&quot;>📦</div>'">`
    : `<div style="font-size:120px;color:#ddd">📦</div>`;
  const price = p.price !== null && p.price !== undefined
    ? `<span class="currency">$</span>${p.price.toFixed(2)}`
    : 'Liên hệ';
  const sold = p.sold > 1000 ? `${(p.sold/1000).toFixed(1)}k` : p.sold;

  const isLoggedInUser = isLoggedIn();

  document.getElementById('product-detail').innerHTML = `
    <div class="product-detail-image">${img}</div>
    <div class="product-detail-info">
      <h1>${escapeHtml(p.title)}</h1>
      <div class="detail-rating-row">
        <span class="stars">⭐ ${p.rating.toFixed(1)}</span>
        <span>${p.n_rating.toLocaleString()} đánh giá</span>
        <span>•</span>
        <span>Đã bán ${sold}</span>
      </div>
      <div class="detail-price-box">
        <div class="detail-price">${price}</div>
      </div>
      <div class="detail-info-row">
        <span class="label">Thương hiệu:</span>
        <span class="value">${escapeHtml(p.brand) || '—'}</span>
      </div>
      <div class="detail-info-row">
        <span class="label">Danh mục:</span>
        <span class="value">${escapeHtml(p.category) || '—'}</span>
      </div>
      <div class="detail-info-row">
        <span class="label">Mã SP:</span>
        <span class="value" style="font-family:monospace;">${p.asin}</span>
      </div>

      <div class="detail-actions">
        <button class="btn-add-cart-detail" onclick="cartAddFromMap('${p.asin}')">
          🛒 Thêm vào giỏ hàng
        </button>
        <button class="btn-buy-now" onclick="cartAddFromMap('${p.asin}'); toggleCart()">
          Mua ngay
        </button>
      </div>

      ${isLoggedInUser ? `
        <div class="detail-info-row" style="margin-top:20px;border-top:1px solid #f0f0f0;padding-top:16px;">
          <span class="label">Đánh giá:</span>
          <div style="flex:1;">
            <div class="rating-input" id="rating-input">
              <span data-val="1">★</span>
              <span data-val="2">★</span>
              <span data-val="3">★</span>
              <span data-val="4">★</span>
              <span data-val="5">★</span>
            </div>
            <button class="btn-rate" id="btn-rate" disabled>Gửi đánh giá</button>
            <div class="rate-success hidden" id="rate-success">✓ Đã gửi đánh giá của bạn!</div>
          </div>
        </div>
      ` : `
        <div style="margin-top:16px;color:#888;font-size:13px;">
          <a href="/login" style="color:#ee4d2d;">Đăng nhập</a> để đánh giá sản phẩm
        </div>
      `}
    </div>
  `;

  if (isLoggedInUser) {
    initRatingInput();
  }
}

function initRatingInput() {
  const stars = document.querySelectorAll('#rating-input span');
  const btnRate = document.getElementById('btn-rate');

  stars.forEach(star => {
    star.addEventListener('mouseenter', () => {
      const val = parseInt(star.dataset.val);
      stars.forEach(s => {
        s.classList.toggle('active', parseInt(s.dataset.val) <= val);
      });
    });
    star.addEventListener('click', () => {
      userRating = parseInt(star.dataset.val);
      btnRate.disabled = false;
    });
  });

  document.getElementById('rating-input').addEventListener('mouseleave', () => {
    stars.forEach(s => {
      s.classList.toggle('active', parseInt(s.dataset.val) <= userRating);
    });
  });

  btnRate.addEventListener('click', async () => {
    if (!userRating) return;
    btnRate.disabled = true;
    btnRate.textContent = 'Đang gửi...';
    try {
      const res = await authFetch(`${API}/track/rate`, {
        method: 'POST',
        body: JSON.stringify({ asin: currentAsin, rating: userRating }),
      });
      if (res.ok) {
        document.getElementById('rate-success').classList.remove('hidden');
        btnRate.textContent = 'Đã gửi ✓';
      }
    } catch (err) {
      alert('Lỗi: ' + err.message);
      btnRate.disabled = false;
      btnRate.textContent = 'Gửi đánh giá';
    }
  });
}

// ─── Track view ───
async function trackView(asin) {
  if (!isLoggedIn()) return;
  try {
    await authFetch(`${API}/track/view`, {
      method: 'POST',
      body: JSON.stringify({ asin }),
    });
  } catch (err) { /* ignore */ }
}

// ─── Bought Together ───
let boughtTogetherAsins = [];

async function fetchBoughtTogether(asin) {
  try {
    const res = await fetch(`${API}/products/${asin}/bought-together?k=6`);
    if (!res.ok) { hideBoughtTogether(); return; }
    const data = await res.json();
    if (!data.items || !data.items.length) { hideBoughtTogether(); return; }
    boughtTogetherAsins = data.items.map(it => it.asin);
    document.getElementById('bt-list').innerHTML = data.items.map(btCard).join('');
    renderBtTotal(data.items);
  } catch(e) { hideBoughtTogether(); }
}

function hideBoughtTogether() {
  document.getElementById('bought-together-section').classList.add('hidden');
}

function btCard(item) {
  productMap[item.asin] = { asin: item.asin, title: item.title, price: item.price ?? null, image: item.image || '' };
  const img = item.image
    ? `<img src="${item.image}" loading="lazy" onerror="this.outerHTML='<div style=&quot;font-size:40px;color:#ddd&quot;>📦</div>'">`
    : `<div style="font-size:40px;color:#ddd">📦</div>`;
  const price = item.price !== null && item.price !== undefined
    ? `$${item.price.toFixed(2)}` : 'Liên hệ';
  const asin = item.asin.replace(/'/g, "\\'");
  return `
    <div class="bt-card" onclick="window.location.href='/product/${asin}'">
      <div class="bt-img">${img}</div>
      <div class="bt-info">
        <div class="bt-title">${escapeHtml(item.title)}</div>
        <div class="bt-price">${price}</div>
      </div>
      <button class="bt-add" onclick="event.stopPropagation(); cartAddFromMap('${asin}')">+ Thêm</button>
    </div>`;
}

function renderBtTotal(btItems) {
  const totalEl = document.getElementById('bt-total');
  const cur = productMap[currentAsin];
  const allItems = cur ? [cur, ...btItems] : btItems;
  const prices = allItems.map(it => it.price).filter(p => p !== null && p !== undefined);
  if (!prices.length) return;
  const total = prices.reduce((a, b) => a + b, 0);
  totalEl.innerHTML = `
    <span class="bt-total-label">Tổng ${allItems.length} sản phẩm:</span>
    <span class="bt-total-price">$${total.toFixed(2)}</span>
    <button class="btn-add-all" onclick="addAllBoughtTogether()">Thêm tất cả vào giỏ</button>
  `;
  totalEl.classList.remove('hidden');
}

function addAllBoughtTogether() {
  if (productMap[currentAsin]) cartAddFromMap(currentAsin);
  boughtTogetherAsins.forEach(asin => { if (productMap[asin]) cartAddFromMap(asin); });
  toggleCart();
}

// ─── Personal Recommendations (chỉ hiện với user có đủ lịch sử ≥ 3) ───
async function fetchPersonalRec() {
  if (!isLoggedIn()) return;
  try {
    const res = await authFetch(`${API}/recommend?k=8`);
    if (!res.ok) return;
    const data = await res.json();
    if (data.n_interactions < 3) return;
    const items = data.items.filter(it => it.asin !== currentAsin);
    if (!items.length) return;
    document.getElementById('personal-rec-grid').innerHTML = items.map(productCard).join('');
    document.getElementById('personal-algo-badge').textContent = data.algorithm;
    document.getElementById('personal-rec-section').classList.remove('hidden');
  } catch(e) {}
}

// ─── Similar ───
async function fetchSimilar(asin) {
  try {
    const res = await fetch(`${API}/products/${asin}/similar?k=12`);
    if (res.ok) {
      const data = await res.json();
      document.getElementById('similar-grid').innerHTML = data.items.map(productCard).join('');
    }
  } catch(e) {}
}

// ─── Store Items ───
async function fetchStoreItems(asin) {
  try {
    const res = await fetch(`${API}/products/${asin}/store-items?k=8`);
    if (!res.ok) return;
    const data = await res.json();
    if (!data.items || !data.items.length) return;
    document.getElementById('store-grid').innerHTML = data.items.map(productCard).join('');
    document.getElementById('store-algo-badge').textContent = data.algorithm;
    if (data.algorithm === 'Same Category') {
      document.querySelector('#store-section h2').textContent = '🏪 Sản phẩm cùng danh mục';
    }
    document.getElementById('store-section').classList.remove('hidden');
  } catch(e) {}
}

// ─── Init ───
function getAsinFromUrl() {
  const parts = window.location.pathname.split('/');
  return parts[parts.length - 1];
}

function goToSearch() {
  const q = document.getElementById('search-input').value.trim();
  if (q) window.location.href = `/?q=${encodeURIComponent(q)}`;
}

async function initProductPage() {
  renderUserMenuProduct();
  currentAsin = getAsinFromUrl();

  document.getElementById('search-input').addEventListener('keypress', e => {
    if (e.key === 'Enter') goToSearch();
  });

  loading.show();
  try {
    const res = await fetch(`${API}/products/${currentAsin}`);
    if (!res.ok) {
      document.getElementById('product-detail').innerHTML = '<p>Sản phẩm không tồn tại</p>';
      return;
    }
    const product = await res.json();
    renderProduct(product);
    trackView(currentAsin);  // fire-and-forget

    await Promise.all([
      fetchBoughtTogether(currentAsin),
      fetchStoreItems(currentAsin),
      fetchSimilar(currentAsin),
      fetchPersonalRec(),
    ]);
  } finally {
    loading.hide();
  }
}
