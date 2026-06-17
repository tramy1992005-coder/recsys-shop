"""
Authentication & User Database
- SQLite cho users + interactions
- Password hashing với bcrypt
- JWT token cho session
"""
import hashlib
import base64
import sqlite3
import time
from pathlib import Path
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import jwt, JWTError

# ─────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────
DB_PATH    = Path(__file__).parent / 'users.db'

# Demo accounts — seeded từ dataset Amazon
DEMO_CONFIGS = [
    {'username': 'demo01', 'full_name': 'Demo User 1', 'hist_id': '285'},
    {'username': 'demo02', 'full_name': 'Demo User 2', 'hist_id': '379'},
    {'username': 'demo03', 'full_name': 'Demo User 3', 'hist_id': '3556'},
]
DEMO_PASSWORD = 'Demo@123'
SECRET_KEY = 'recsys-demo-secret-key-change-in-production-2024'
ALGORITHM  = 'HS256'
TOKEN_EXP_HOURS = 24

pwd_ctx = CryptContext(schemes=['bcrypt'], deprecated='auto')

# ─────────────────────────────────────────────────────────
# DATABASE INIT
# ─────────────────────────────────────────────────────────
def init_db():
    """Tạo bảng users + interactions nếu chưa có."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            created_at INTEGER NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            asin TEXT NOT NULL,
            action TEXT NOT NULL,
            rating REAL,
            timestamp INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_user_inter ON interactions(user_id)')
    conn.commit()
    conn.close()
    print(f'[Auth] DB ready: {DB_PATH}')

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ─────────────────────────────────────────────────────────
# USERS
# ─────────────────────────────────────────────────────────
def _prehash(pw: str) -> str:
    """SHA-256 → base64 (44 ASCII chars) — bypasses bcrypt's 72-byte limit entirely."""
    digest = hashlib.sha256(pw.encode('utf-8')).digest()
    return base64.b64encode(digest).decode('ascii')

def hash_password(pw: str) -> str:
    # bcrypt giới hạn 72 bytes
    return pwd_ctx.hash(pw[:72])

def verify_password(pw: str, hashed: str) -> bool:
    return pwd_ctx.verify(pw[:72], hashed)

def create_user(username: str, password: str, full_name: str = '') -> dict:
    """Tạo user mới. Raise ValueError nếu username đã tồn tại."""
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT id FROM users WHERE username = ?', (username,))
    if c.fetchone():
        conn.close()
        raise ValueError('Tên đăng nhập đã tồn tại')
    c.execute(
        'INSERT INTO users (username, password_hash, full_name, created_at) VALUES (?, ?, ?, ?)',
        (username, hash_password(password), full_name, int(time.time()))
    )
    user_id = c.lastrowid
    conn.commit()
    conn.close()
    return {'id': user_id, 'username': username, 'full_name': full_name}

def authenticate(username: str, password: str) -> dict | None:
    """Kiểm tra đăng nhập. Trả về user dict hoặc None."""
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username = ?', (username,))
    row = c.fetchone()
    conn.close()
    if not row or not verify_password(password, row['password_hash']):
        return None
    return {'id': row['id'], 'username': row['username'], 'full_name': row['full_name']}

def get_user_by_id(user_id: int) -> dict | None:
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT id, username, full_name FROM users WHERE id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

# ─────────────────────────────────────────────────────────
# INTERACTIONS
# ─────────────────────────────────────────────────────────
def log_interaction(user_id: int, asin: str, action: str, rating: float | None = None):
    """
    Lưu hành vi user. action: 'view', 'rate', 'click'.
    """
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        'INSERT INTO interactions (user_id, asin, action, rating, timestamp) VALUES (?, ?, ?, ?, ?)',
        (user_id, asin, action, rating, int(time.time()))
    )
    conn.commit()
    conn.close()

def get_user_interactions(user_id: int, limit: int = 100) -> list:
    """Lấy lịch sử user (dùng cho recommendation)."""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        '''SELECT asin, action, rating, timestamp 
           FROM interactions 
           WHERE user_id = ? 
           ORDER BY timestamp DESC LIMIT ?''',
        (user_id, limit)
    )
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def seed_demo_users(idx2asin: dict, user_history: dict, max_per_user: int = 100):
    """
    Tạo demo users với lịch sử từ dataset Amazon.
    Luôn xóa và re-seed interactions để đảm bảo khớp với artifacts hiện tại.
    """
    for cfg in DEMO_CONFIGS:
        conn = get_conn()
        c = conn.cursor()
        c.execute('SELECT id FROM users WHERE username = ?', (cfg['username'],))
        row = c.fetchone()
        if row:
            user_id = row['id']
            # Xóa interactions cũ — có thể dùng ASIN từ artifacts cũ không còn hợp lệ
            c.execute('DELETE FROM interactions WHERE user_id = ?', (user_id,))
        else:
            c.execute(
                'INSERT INTO users (username, password_hash, full_name, created_at) VALUES (?, ?, ?, ?)',
                (cfg['username'], hash_password(DEMO_PASSWORD), cfg['full_name'], int(time.time()))
            )
            user_id = c.lastrowid

        hist = user_history.get(cfg['hist_id'], [])[:max_per_user]
        ts = int(time.time()) - len(hist) * 3600
        inserted = 0
        for entry in hist:
            item_idx, rating = int(entry[0]), float(entry[1])
            asin = idx2asin.get(item_idx)
            if not asin:
                continue
            c.execute(
                'INSERT INTO interactions (user_id, asin, action, rating, timestamp) VALUES (?, ?, ?, ?, ?)',
                (user_id, asin, 'rate', rating, ts)
            )
            ts += 3600
            inserted += 1
        conn.commit()
        conn.close()
        print(f'[Auth] Seeded {cfg["username"]} ({inserted} interactions)')

def count_user_interactions(user_id: int) -> int:
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM interactions WHERE user_id = ?', (user_id,))
    n = c.fetchone()[0]
    conn.close()
    return n

# ─────────────────────────────────────────────────────────
# JWT TOKEN
# ─────────────────────────────────────────────────────────
def create_token(user_id: int, username: str) -> str:
    payload = {
        'sub': str(user_id),
        'username': username,
        'exp': datetime.utcnow() + timedelta(hours=TOKEN_EXP_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {'user_id': int(payload['sub']), 'username': payload['username']}
    except JWTError:
        return None
