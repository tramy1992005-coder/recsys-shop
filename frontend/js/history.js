// ─────────────────────────────────────────────────────────
// HISTORY PAGE
// ─────────────────────────────────────────────────────────

let allInteractions = [];

async function initHistoryPage() {
  if (!isLoggedIn()) {
    window.location.href = '/login';
    return;
  }

  renderUserMenuHistory();

  document.getElementById('search-input').addEventListener('keypress', e => {
    if (e.key === 'Enter') goToSearch();
  });

  document.querySelectorAll('.htab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.htab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      renderHistory(tab.dataset.action);
    });
  });

  const loading = document.getElementById('loading');
  loading.classList.remove('hidden');
  try {
    const res = await authFetch(`${API}/user/history?limit=500&_t=${Date.now()}`);
    if (!res.ok) throw new Error();
    const data = await res.json();
    allInteractions = data.items;
  } catch(e) {
    document.getElementById('history-list').innerHTML = '<div class="empty-msg">Không thể tải lịch sử</div>';
    return;
  } finally {
    loading.classList.add('hidden');
  }

  renderHistory('');
}

function renderHistory(actionFilter) {
  const items = actionFilter
    ? allInteractions.filter(it => it.action === actionFilter)
    : allInteractions;

  const countEl = document.getElementById('history-count');
  const listEl  = document.getElementById('history-list');

  const labels = { '': 'hoạt động', view: 'lượt xem', cart: 'lần thêm giỏ', rate: 'lần đánh giá' };
  countEl.textContent = `${items.length} ${labels[actionFilter] || 'hoạt động'}`;

  if (!items.length) {
    listEl.innerHTML = '<div class="empty-msg">Chưa có hoạt động nào</div>';
    return;
  }

  listEl.innerHTML = items.map(historyRow).join('');
}

function historyRow(item) {
  const img = item.image
    ? `<img src="${item.image}" loading="lazy" onerror="this.outerHTML='<div class=\\"hist-img-placeholder\\">📦</div>'">`
    : `<div class="hist-img-placeholder">📦</div>`;

  const price = item.price !== null && item.price !== undefined
    ? `<span style="color:#ee4d2d;font-weight:600;">$${item.price.toFixed(2)}</span>`
    : '<span style="color:#aaa;">Liên hệ</span>';

  const badges = {
    view: '<span class="hist-badge view">👁 Đã xem</span>',
    cart: '<span class="hist-badge cart">🛒 Đã thêm giỏ</span>',
    rate: `<span class="hist-badge rate">⭐ Đánh giá ${item.user_rating}/5</span>`,
  };
  const badge = badges[item.action] || `<span class="hist-badge">${item.action}</span>`;

  const stars = item.action === 'rate' && item.user_rating
    ? `<div class="hist-stars">${'★'.repeat(Math.round(item.user_rating))}${'☆'.repeat(5 - Math.round(item.user_rating))}</div>`
    : '';

  const date = new Date(item.timestamp * 1000).toLocaleString('vi-VN', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });

  const asin = String(item.asin).replace(/'/g, "\\'");

  return `
    <div class="history-row" onclick="window.location.href='/product/${asin}'">
      <div class="hist-img">${img}</div>
      <div class="hist-info">
        <div class="hist-title">${escapeHist(item.title)}</div>
        <div class="hist-price-row">${price}</div>
        ${stars}
        <div class="hist-meta">${badge}<span class="hist-time">${date}</span></div>
      </div>
      <div class="hist-action-btn">›</div>
    </div>`;
}

function escapeHist(s) {
  return String(s).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
}

function goToSearch() {
  const q = document.getElementById('search-input').value.trim();
  if (q) window.location.href = `/?q=${encodeURIComponent(q)}`;
}

function renderUserMenuHistory() {
  const menu       = document.getElementById('user-menu');
  const welcome    = document.getElementById('welcome-text');
  const logoutLink = document.getElementById('logout-link');
  const user       = getUser();
  if (!user) return;

  const initial = (user.username || 'U').charAt(0).toUpperCase();
  menu.innerHTML = `
    <div class="avatar">${initial}</div>
    <div>
      <div style="font-size:12px;opacity:0.85;">Xin chào</div>
      <div style="font-weight:600;">${user.username}</div>
    </div>
    <a href="/" style="font-size:12px;opacity:0.85;margin-left:4px;">Trang chủ</a>
    <button class="btn-logout" onclick="logout()">Đăng xuất</button>
  `;
  welcome.textContent = `👋 ${user.full_name || user.username}`;
  logoutLink.classList.remove('hidden');
}
