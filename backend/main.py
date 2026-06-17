"""
FastAPI Server — Shopee-style Recsys Demo
Run: uvicorn main:app --reload
"""
import json
import time
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import re
from pydantic import BaseModel, Field, field_validator

import auth
from recommender import HybridRecommender

# ─────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).resolve().parent.parent.parent  # D:\DA.My
ARTIFACTS_DIR = BASE_DIR / 'api_artifacts'
FRONTEND_DIR  = BASE_DIR / 'app' / 'frontend'

# ─────────────────────────────────────────────────────────
# APP INIT
# ─────────────────────────────────────────────────────────
app = FastAPI(title='Recsys Shop Demo', version='2.0')
app.add_middleware(CORSMiddleware, allow_origins=['*'],
                   allow_methods=['*'], allow_headers=['*'])

print('=' * 60)
print('Starting Recsys Shop Demo Server...')
print('=' * 60)
auth.init_db()
rec = HybridRecommender(str(ARTIFACTS_DIR))

# Seed demo users từ dataset Amazon
_hist_path = ARTIFACTS_DIR / 'user_history.json'
if _hist_path.exists():
    with open(_hist_path) as _f:
        _user_hist = json.load(_f)
    _idx2asin = {i: str(asin) for i, asin in enumerate(rec.idx2asin)}
    auth.seed_demo_users(_idx2asin, _user_hist)

print('=' * 60)
print('Server ready! Open: http://localhost:8000')
print('=' * 60)

# ─────────────────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ─────────────────────────────────────────────────────────
class RegisterReq(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)
    password: str = Field(..., min_length=5)
    confirm_password: str
    full_name: str = ''

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v.encode('utf-8')) > 72:
            raise ValueError('Mật khẩu không được vượt quá 72 ký tự')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Mật khẩu phải có ít nhất 1 chữ viết hoa')
        if not re.search(r'[@#&$*!]', v):
            raise ValueError('Mật khẩu phải có ít nhất 1 ký tự đặc biệt (@#&$*!)')
        return v

class LoginReq(BaseModel):
    username: str
    password: str

class RateReq(BaseModel):
    asin: str
    rating: float = Field(..., ge=1, le=5)

class ViewReq(BaseModel):
    asin: str

class CartReq(BaseModel):
    asin: str

class CartRecommendReq(BaseModel):
    asins: list[str]

# ─────────────────────────────────────────────────────────
# AUTH DEPENDENCY
# ─────────────────────────────────────────────────────────
def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """Xác thực token từ header 'Authorization: Bearer xxx'."""
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401, 'Chưa đăng nhập')
    token = authorization.replace('Bearer ', '')
    payload = auth.decode_token(token)
    if not payload:
        raise HTTPException(401, 'Token không hợp lệ hoặc đã hết hạn')
    user = auth.get_user_by_id(payload['user_id'])
    if not user:
        raise HTTPException(401, 'User không tồn tại')
    return user

def get_current_user_optional(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    """Như trên nhưng cho phép guest (chưa login)."""
    if not authorization or not authorization.startswith('Bearer '):
        return None
    token = authorization.replace('Bearer ', '')
    payload = auth.decode_token(token)
    if not payload:
        return None
    return auth.get_user_by_id(payload['user_id'])

# ═════════════════════════════════════════════════════════
# AUTH ENDPOINTS
# ═════════════════════════════════════════════════════════
@app.post('/api/auth/register')
def register(req: RegisterReq):
    if req.password != req.confirm_password:
        raise HTTPException(400, 'Mật khẩu xác nhận không khớp')
    try:
        user = auth.create_user(req.username, req.password, req.full_name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    token = auth.create_token(user['id'], user['username'])
    return {'success': True, 'user': user, 'token': token}

@app.post('/api/auth/login')
def login(req: LoginReq):
    user = auth.authenticate(req.username, req.password)
    if not user:
        raise HTTPException(401, 'Tên đăng nhập hoặc mật khẩu sai')
    token = auth.create_token(user['id'], user['username'])
    return {'success': True, 'user': user, 'token': token}

@app.get('/api/auth/me')
def me(user: dict = Depends(get_current_user)):
    n = auth.count_user_interactions(user['id'])
    return {'user': user, 'n_interactions': n}

# ═════════════════════════════════════════════════════════
# PRODUCT ENDPOINTS
# ═════════════════════════════════════════════════════════
@app.get('/api/products/popular')
def popular(k: int = 20):
    """Top sản phẩm phổ biến (cho banner trang chủ)."""
    return {'items': rec.popular(k=k), 'algorithm': 'Popularity'}

@app.get('/api/products/{asin}')
def product_detail(asin: str):
    """Chi tiết 1 sản phẩm."""
    item = rec.get_product(asin)
    if not item:
        raise HTTPException(404, 'Sản phẩm không tồn tại')
    return item

@app.get('/api/products/{asin}/similar')
def similar(asin: str, k: int = 10):
    """Sản phẩm tương tự (Content-Based)."""
    items = rec.similar_items(asin, k=k)
    if not items:
        raise HTTPException(404, 'Không tìm thấy sản phẩm tương tự')
    return {'asin': asin, 'items': items, 'algorithm': 'Content-Based (TF-IDF)'}

@app.get('/api/products/{asin}/bought-together')
def bought_together(asin: str, k: int = 6):
    """Sản phẩm thường mua kèm (Complementary + ALS)."""
    items = rec.bought_together(asin, k=k)
    return {'asin': asin, 'items': items, 'algorithm': 'Complementary + ALS'}

@app.get('/api/search')
def search(q: str, k: int = 30):
    """Search sản phẩm theo từ khóa."""
    return {'query': q, 'items': rec.search(q, k=k)}

@app.get('/api/category/{category}')
def category(category: str, k: int = 30):
    return {'category': category, 'items': rec.browse_by_category(category, k=k)}

@app.get('/api/demo-users')
def get_demo_users():
    """Trả về thông tin demo accounts để hiển thị trên login page."""
    result = []
    for cfg in auth.DEMO_CONFIGS:
        conn = auth.get_conn()
        c = conn.cursor()
        c.execute('SELECT id FROM users WHERE username = ?', (cfg['username'],))
        row = c.fetchone()
        conn.close()
        if row:
            result.append({
                'username':      cfg['username'],
                'full_name':     cfg['full_name'],
                'n_interactions': auth.count_user_interactions(row['id']),
            })
    return {'users': result, 'password': auth.DEMO_PASSWORD}

@app.get('/api/categories')
def list_categories():
    """Danh sách categories thực tế trong dataset."""
    return {'categories': rec.get_categories()}

@app.post('/api/cart/recommend')
def cart_recommend(req: CartRecommendReq, k: int = 8):
    """Gợi ý dựa trên toàn bộ giỏ hàng — Item2Vec + Complementary."""
    items = rec.recommend_from_cart(req.asins, k=k)
    return {'items': items, 'algorithm': 'Item2Vec + Complementary'}

@app.get('/api/products/{asin}/store-items')
def store_items(asin: str, k: int = 8):
    """Sản phẩm khác từ cùng cửa hàng/store. Fallback: cùng danh mục."""
    items, label = rec.more_from_store(asin, k=k)
    return {'asin': asin, 'items': items, 'algorithm': label}

# Cache /api/recommend theo user_id — TTL 60s để tránh tính lại matrix ops khi user điều hướng
_rec_cache: dict[int, tuple[float, dict]] = {}  # {user_id: (timestamp, response)}
_REC_TTL = 60  # seconds

# ═════════════════════════════════════════════════════════
# RECOMMENDATION (cần login)
# ═════════════════════════════════════════════════════════
@app.get('/api/recommend')
def recommend(k: int = 12, user: dict = Depends(get_current_user)):
    """Gợi ý cá nhân hóa cho user đã login."""
    uid = user['id']
    now = time.time()
    cached_ts, cached_res = _rec_cache.get(uid, (0, None))
    if cached_res is not None and (now - cached_ts) < _REC_TTL:
        return cached_res
    interactions = auth.get_user_interactions(uid, limit=200)
    items, algo = rec.recommend(interactions, k=k)
    result = {
        'user_id': uid,
        'n_interactions': len(interactions),
        'items': items,
        'algorithm': algo,
    }
    _rec_cache[uid] = (now, result)
    return result

# ═════════════════════════════════════════════════════════
# USER BEHAVIOR TRACKING
# ═════════════════════════════════════════════════════════
@app.post('/api/track/view')
def track_view(req: ViewReq, user: dict = Depends(get_current_user)):
    """Lưu hành vi xem sản phẩm."""
    auth.log_interaction(user['id'], req.asin, 'view')
    return {'success': True}

@app.post('/api/track/cart')
def track_cart(req: CartReq, user: dict = Depends(get_current_user)):
    """Lưu hành vi thêm vào giỏ (signal mạnh cho recommender)."""
    auth.log_interaction(user['id'], req.asin, 'cart')
    return {'success': True}

@app.post('/api/track/rate')
def track_rate(req: RateReq, user: dict = Depends(get_current_user)):
    """Lưu rating user cho sản phẩm."""
    auth.log_interaction(user['id'], req.asin, 'rate', rating=req.rating)
    return {'success': True}

@app.get('/api/user/history')
def my_history(limit: int = 30, user: dict = Depends(get_current_user)):
    """Lịch sử mua/xem của user hiện tại."""
    interactions = auth.get_user_interactions(user['id'], limit=limit)
    # Enrich với product info
    enriched = []
    for it in interactions:
        product = rec.get_product(it['asin'])
        if product:
            enriched.append({**product, 'action': it['action'],
                             'user_rating': it.get('rating'),
                             'timestamp': it['timestamp']})
    return {'items': enriched}

# ═════════════════════════════════════════════════════════
# SERVE FRONTEND
# ═════════════════════════════════════════════════════════
app.mount('/css', StaticFiles(directory=str(FRONTEND_DIR / 'css')), name='css')
app.mount('/js',  StaticFiles(directory=str(FRONTEND_DIR / 'js')),  name='js')

@app.get('/')
def home():
    return FileResponse(FRONTEND_DIR / 'index.html')

@app.get('/login')
def login_page():
    return FileResponse(FRONTEND_DIR / 'login.html')

@app.get('/register')
def register_page():
    return FileResponse(FRONTEND_DIR / 'register.html')

@app.get('/product/{asin}')
def product_page(asin: str):
    return FileResponse(FRONTEND_DIR / 'product.html')

@app.get('/history')
def history_page():
    return FileResponse(FRONTEND_DIR / 'history.html')
