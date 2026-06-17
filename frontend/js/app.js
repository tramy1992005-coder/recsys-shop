// ─────────────────────────────────────────────────────────
// HOME PAGE LOGIC
// ─────────────────────────────────────────────────────────

// ─── User menu render ───
function renderUserMenu() {
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
    welcome.textContent = 'Đăng ký/Đăng nhập để có gợi ý cá nhân hóa';
  }
}

// ─── Product card render ───
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
  const isHot = item.sold > 500;
  const asin  = item.asin.replace(/'/g, "\\'");

  return `
    <div class="product-card" onclick="goToProduct('${asin}')">
      <div class="product-image-wrap">
        ${img}
        ${isHot ? '<div class="product-badge">HOT</div>' : ''}
      </div>
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

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
}

function renderGrid(containerId, items) {
  const el = document.getElementById(containerId);
  if (!items || !items.length) {
    el.innerHTML = '<div class="empty-msg" style="grid-column:1/-1;">Không có sản phẩm</div>';
    return;
  }
  el.innerHTML = items.map(productCard).join('');
}

function goToProduct(asin) {
  window.location.href = `/product/${asin}`;
}

function goToSearch() {
  const q = document.getElementById('search-input').value.trim();
  if (!q) return;
  doSearch(q);
}

// ─── Loading helper ───
const loading = {
  show() { document.getElementById('loading').classList.remove('hidden'); },
  hide() { document.getElementById('loading').classList.add('hidden'); },
};

// ─── Fetch helpers ───
async function fetchPopular() {
  const res = await fetch(`${API}/products/popular?k=20`);
  const data = await res.json();
  renderGrid('popular-grid', data.items);
}

async function fetchRecommend() {
  if (!isLoggedIn()) return;
  try {
    const res = await authFetch(`${API}/recommend?k=12`);
    if (!res.ok) return;
    const data = await res.json();
    const bannerTitle    = document.getElementById('banner-title');
    const bannerSubtitle = document.getElementById('banner-subtitle');
    const user = getUser();

    if (data.n_interactions < 3) {
      // User mới — chưa đủ dữ liệu để cá nhân hóa, kết quả giống Popularity → không hiện section
      bannerTitle.textContent    = `Xin chào ${user.username}! 👋`;
      bannerSubtitle.textContent = `Hãy tương tác với sản phẩm để nhận gợi ý cá nhân hóa (hiện có ${data.n_interactions} tương tác)`;
      return;
    }

    bannerTitle.textContent    = `Chào mừng trở lại, ${user.username}! 🎉`;
    bannerSubtitle.textContent = `Đã có ${data.n_interactions} tương tác — gợi ý đã được cá nhân hóa cho bạn`;
    document.getElementById('recommend-algo').textContent = data.algorithm;
    renderGrid('recommend-grid', data.items);
    document.getElementById('recommend-section').classList.remove('hidden');
  } catch (err) {
    console.error(err);
  }
}

async function doSearch(query) {
  loading.show();
  try {
    const res = await fetch(`${API}/search?q=${encodeURIComponent(query)}&k=30`);
    const data = await res.json();
    document.getElementById('search-title').textContent = `🔍 Kết quả tìm kiếm: "${query}"`;
    renderGrid('search-grid', data.items);
    document.getElementById('search-section').classList.remove('hidden');
    document.getElementById('search-section').scrollIntoView({behavior:'smooth'});
  } finally {
    loading.hide();
  }
}

async function fetchByCategory(category) {
  loading.show();
  try {
    const url = category
      ? `${API}/category/${encodeURIComponent(category)}?k=30`
      : `${API}/products/popular?k=30`;
    const res = await fetch(url);
    const data = await res.json();
    renderGrid('popular-grid', data.items);
  } finally {
    loading.hide();
  }
}

// ─── Categories (load động từ API) ───
const CAT_ICONS = {
  'Ốp lưng & Bao da':          '📱',
  'Kính cường lực':             '🛡️',
  'Sạc & Adapter':              '🔌',
  'Cáp kết nối':                '🔗',
  'Đồng hồ & Vòng đeo':        '⌚',
  'Giá đỡ & Kẹp điện thoại':   '🗜️',
  'Pin & Sạc dự phòng':         '🔋',
  'Bảo vệ Camera':              '📷',
  'Tai nghe & Loa':             '🎧',
  'Nhẫn & Grip điện thoại':     '💍',
  'Bút cảm ứng & Bàn phím':    '✏️',
  'Selfie & Chụp ảnh':          '🤳',
};

async function fetchCategories() {
  try {
    const res = await fetch(`${API}/categories`);
    if (!res.ok) return;
    const data = await res.json();
    const bar  = document.getElementById('categories-bar');
    data.categories.forEach(cat => {
      const icon = CAT_ICONS[cat.toLowerCase()] || '📦';
      const chip = document.createElement('span');
      chip.className    = 'category-chip';
      chip.dataset.cat  = cat;
      chip.textContent  = `${icon} ${cat}`;
      bar.appendChild(chip);
    });
  } catch (e) { /* ignore — static fallback already in HTML */ }
}

// ─── Init home page ───
async function initHomePage() {
  renderUserMenu();

  // Event delegation cho categories (bao gồm chips tải động)
  document.getElementById('categories-bar').addEventListener('click', e => {
    const chip = e.target.closest('.category-chip');
    if (!chip) return;
    document.querySelectorAll('.category-chip').forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
    fetchByCategory(chip.dataset.cat);
  });

  // Search
  document.getElementById('search-btn').addEventListener('click', goToSearch);
  document.getElementById('search-input').addEventListener('keypress', e => {
    if (e.key === 'Enter') goToSearch();
  });

  loading.show();
  try {
    // Popular + categories trước — nhanh, tắt spinner sớm để user thấy trang ngay
    await Promise.all([fetchPopular(), fetchCategories()]);
  } finally {
    loading.hide();
  }
  // Recommendations load ngầm sau — nặng hơn vì chạy matrix ops, không chặn render
  fetchRecommend();
}
