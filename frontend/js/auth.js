// ─────────────────────────────────────────────────────────
// AUTH HELPER FUNCTIONS (dùng chung cho login/register/app)
// ─────────────────────────────────────────────────────────

const API = '/api';
const TOKEN_KEY = 'recsys_token';
const USER_KEY  = 'recsys_user';

// Lưu/đọc/xóa session
function saveSession(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}
function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}
function getUser() {
  const u = localStorage.getItem(USER_KEY);
  return u ? JSON.parse(u) : null;
}
function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}
function isLoggedIn() {
  return !!getToken();
}

// Fetch có Authorization header
async function authFetch(url, options = {}) {
  const token = getToken();
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(url, { ...options, headers });
  if (res.status === 401) {
    clearSession();
    if (!window.location.pathname.match(/\/(login|register)/)) {
      window.location.href = '/login';
    }
    throw new Error('Phiên đăng nhập đã hết');
  }
  return res;
}

// Hiển thị lỗi trên form
function showError(msg) {
  const el = document.getElementById('error-msg');
  el.textContent = msg;
  el.classList.remove('hidden');
}
function clearError() {
  const el = document.getElementById('error-msg');
  if (el) el.classList.add('hidden');
}

// ─────────────────────────────────────────────────────────
// PASSWORD HELPERS
// ─────────────────────────────────────────────────────────
function truncateTo72Bytes(str) {
  const bytes = new TextEncoder().encode(str);
  if (bytes.length <= 72) return str;
  return new TextDecoder('utf-8', { fatal: false }).decode(bytes.slice(0, 72));
}

function validatePassword(pw) {
  const byteLen = new TextEncoder().encode(pw).length;
  if (pw.length < 5)           return 'Mật khẩu tối thiểu 5 ký tự';
  if (byteLen > 72)            return 'Mật khẩu không được vượt quá 72 ký tự';
  if (!/[A-Z]/.test(pw))      return 'Mật khẩu phải có ít nhất 1 chữ viết hoa';
  if (!/[@#&$*!]/.test(pw))   return 'Mật khẩu phải có ít nhất 1 ký tự đặc biệt (@#&$*!)';
  return null;
}

// ─────────────────────────────────────────────────────────
// PASSWORD TOGGLE
// ─────────────────────────────────────────────────────────
function initPasswordToggles() {
  document.querySelectorAll('.toggle-pw').forEach(btn => {
    btn.addEventListener('click', () => {
      const input = document.getElementById(btn.dataset.target);
      const showing = input.type === 'text';
      input.type = showing ? 'password' : 'text';
      btn.classList.toggle('showing', !showing);
    });
  });
}

// ─────────────────────────────────────────────────────────
// REGISTER
// ─────────────────────────────────────────────────────────
function initRegister() {
  // Nếu đã login → redirect home
  if (isLoggedIn()) {
    window.location.href = '/';
    return;
  }

  initPasswordToggles();

  const form = document.getElementById('register-form');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearError();
    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = 'Đang xử lý...';

    const data = {
      username: form.username.value.trim(),
      full_name: form.full_name.value.trim(),
      password: form.password.value,
      confirm_password: form.confirm_password.value,
    };

    const pwErr = validatePassword(data.password);
    if (pwErr) {
      showError(pwErr);
      btn.disabled = false;
      btn.textContent = 'ĐĂNG KÝ';
      return;
    }

    if (data.password !== data.confirm_password) {
      showError('Mật khẩu xác nhận không khớp');
      btn.disabled = false;
      btn.textContent = 'ĐĂNG KÝ';
      return;
    }

    try {
      const res = await fetch(`${API}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      const result = await res.json();
      if (!res.ok) {
        showError(result.detail || 'Đăng ký thất bại');
        btn.disabled = false;
        btn.textContent = 'ĐĂNG KÝ';
        return;
      }
      saveSession(result.token, result.user);
      window.location.href = '/';
    } catch (err) {
      showError('Lỗi kết nối: ' + err.message);
      btn.disabled = false;
      btn.textContent = 'ĐĂNG KÝ';
    }
  });
}

// ─────────────────────────────────────────────────────────
// DEMO USERS
// ─────────────────────────────────────────────────────────
async function loadDemoUsers() {
  try {
    const res = await fetch(`${API}/demo-users`);
    if (!res.ok) return;
    const data = await res.json();
    if (!data.users || !data.users.length) return;
    const list = document.getElementById('demo-list');
    list.innerHTML = data.users.map(u => `
      <div class="demo-user-card" onclick="quickLogin('${u.username}', '${data.password}')">
        <div class="demo-avatar">${u.username.slice(-2).toUpperCase()}</div>
        <div class="demo-info">
          <div class="demo-username">${u.full_name || u.username}</div>
          <div class="demo-stats">${u.n_interactions} lượt tương tác từ dataset</div>
        </div>
        <span class="demo-btn">Thử →</span>
      </div>`).join('');
    document.getElementById('demo-section').classList.remove('hidden');
  } catch (e) {}
}

function quickLogin(username, password) {
  document.getElementById('username').value = username;
  document.getElementById('password').value = password;
  document.getElementById('login-form').dispatchEvent(new Event('submit'));
}

// ─────────────────────────────────────────────────────────
// LOGIN
// ─────────────────────────────────────────────────────────
function initLogin() {
  if (isLoggedIn()) {
    window.location.href = '/';
    return;
  }

  initPasswordToggles();
  loadDemoUsers();

  const form = document.getElementById('login-form');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearError();
    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = 'Đang đăng nhập...';

    const data = {
      username: form.username.value.trim(),
      password: form.password.value,
    };

    try {
      const res = await fetch(`${API}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      const result = await res.json();
      if (!res.ok) {
        showError(result.detail || 'Đăng nhập thất bại');
        btn.disabled = false;
        btn.textContent = 'ĐĂNG NHẬP';
        return;
      }
      saveSession(result.token, result.user);
      window.location.href = '/';
    } catch (err) {
      showError('Lỗi kết nối: ' + err.message);
      btn.disabled = false;
      btn.textContent = 'ĐĂNG NHẬP';
    }
  });
}

// ─────────────────────────────────────────────────────────
// LOGOUT
// ─────────────────────────────────────────────────────────
function logout() {
  clearSession();
  window.location.href = '/login';
}
