"""
Hybrid Recommender — ALS + Item2Vec + Content + Popularity
- User MỚI (< 3 interactions) → Popularity
- User CÓ LỊCH SỬ          → Hybrid (ALS + Item2Vec + Content + Popularity)
- Bought-together            → Item2Vec cosine sim, cross-category filter
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path


# Sản phẩm bổ sung theo logic mua kèm thực tế
COMPLEMENTARY_MAP: dict[str, list[str]] = {
    'Ốp lưng & Bao da':          ['Kính cường lực', 'Bảo vệ Camera', 'Sạc & Adapter', 'Nhẫn & Grip điện thoại'],
    'Kính cường lực':             ['Ốp lưng & Bao da', 'Bảo vệ Camera', 'Sạc & Adapter'],
    'Sạc & Adapter':              ['Cáp kết nối', 'Pin & Sạc dự phòng', 'Giá đỡ & Kẹp điện thoại'],
    'Cáp kết nối':                ['Sạc & Adapter', 'Pin & Sạc dự phòng', 'Giá đỡ & Kẹp điện thoại'],
    'Đồng hồ & Vòng đeo':        ['Sạc & Adapter', 'Cáp kết nối', 'Ốp lưng & Bao da'],
    'Giá đỡ & Kẹp điện thoại':   ['Sạc & Adapter', 'Cáp kết nối', 'Ốp lưng & Bao da'],
    'Pin & Sạc dự phòng':         ['Cáp kết nối', 'Sạc & Adapter', 'Giá đỡ & Kẹp điện thoại'],
    'Bảo vệ Camera':              ['Kính cường lực', 'Ốp lưng & Bao da', 'Selfie & Chụp ảnh'],
    'Tai nghe & Loa':             ['Sạc & Adapter', 'Cáp kết nối', 'Giá đỡ & Kẹp điện thoại'],
    'Nhẫn & Grip điện thoại':     ['Ốp lưng & Bao da', 'Kính cường lực', 'Selfie & Chụp ảnh'],
    'Bút cảm ứng & Bàn phím':    ['Giá đỡ & Kẹp điện thoại', 'Sạc & Adapter', 'Cáp kết nối'],
    'Selfie & Chụp ảnh':          ['Bảo vệ Camera', 'Giá đỡ & Kẹp điện thoại', 'Nhẫn & Grip điện thoại'],
}

# Sub-categories dựa trên keyword trong title
SUBCATEGORIES: dict[str, list[str]] = {
    'Ốp lưng & Bao da':      ['phone case', 'back case', 'back cover', 'wallet case',
                               'bumper', 'holster', 'flip case', 'folio case',
                               'protective case', 'slim case', 'tpu case', 'silicone case'],
    'Kính cường lực':         ['screen protector', 'tempered glass', 'privacy screen',
                               'glass screen', 'privacy glass'],
    'Sạc & Adapter':          ['charger', 'charging pad', 'wireless charger', 'fast charger',
                               'car charger', 'wall charger', 'charging dock', 'charging station'],
    'Cáp kết nối':            ['usb cable', 'lightning cable', 'type-c cable', 'type c cable',
                               'charging cable', 'data cable', 'usb-c cable', 'braided cable'],
    'Đồng hồ & Vòng đeo':    ['smart watch', 'smartwatch', 'apple watch', 'samsung watch',
                               'fitness tracker', 'watch band', 'watch strap',
                               'watch charger', 'watch case'],
    'Giá đỡ & Kẹp điện thoại': ['phone mount', 'car mount', 'phone holder', 'phone stand',
                                  'desk stand', 'car holder', 'dashboard mount',
                                  'windshield mount', 'bike mount', 'wall mount'],
    'Pin & Sạc dự phòng':     ['power bank', 'portable charger', 'backup battery',
                               'battery pack', 'portable battery'],
    'Bảo vệ Camera':          ['camera lens protector', 'camera protector', 'lens protector',
                               'camera screen protector', 'camera cover'],
    'Tai nghe & Loa':         ['earphone', 'headphone', 'earbud', 'bluetooth speaker',
                               'portable speaker', 'wireless earphone'],
    'Nhẫn & Grip điện thoại': ['phone ring', 'ring holder', 'pop socket', 'popsocket',
                               'phone grip', 'finger ring', 'ring stand'],
    'Bút cảm ứng & Bàn phím': ['stylus', 'apple pencil', 'bluetooth keyboard',
                                'wireless keyboard'],
    'Selfie & Chụp ảnh':      ['selfie stick', 'selfie ring', 'tripod', 'monopod'],
}


class HybridRecommender:
    def __init__(self, artifacts_dir: str):
        self.dir = Path(artifacts_dir)
        self._load()

    def _load(self):
        print(f'[Recommender] Loading from {self.dir} ...')

        # Config
        with open(self.dir / 'config.json') as f:
            self.config = json.load(f)
        # 4-signal weights (ALS, Item2Vec, Content, Popularity) — từ grid search
        self.alpha   = self.config['hybrid_alpha']          # ALS
        self.beta    = self.config['hybrid_beta']           # Item2Vec
        self.gamma   = self.config['hybrid_gamma']          # Content
        self.delta   = self.config.get('hybrid_delta', 0.1) # Popularity
        self.n_items = self.config['n_items']

        # Maps
        self.item_map = pd.read_parquet(self.dir / 'item_map.parquet')
        self.i2idx    = dict(zip(self.item_map['asin'], self.item_map['i']))
        self.idx2asin = self.item_map.sort_values('i')['asin'].values

        # Meta
        self.meta      = pd.read_parquet(self.dir / 'meta_api.parquet')
        self.meta_dict = self.meta.set_index('asin').to_dict('index')

        # Price fallback: category median (dùng khi sản phẩm không có giá)
        self._price_by_cat = (
            self.meta.groupby('main_category')['price'].median()
            .dropna().to_dict()
        )
        self._global_price_median = float(self.meta['price'].median())

        # Response cache (dict-based) — tránh tính lại cho cùng asin
        self._cache_product: dict = {}
        self._cache_similar: dict = {}
        self._cache_bought:  dict = {}
        self._cache_store:   dict = {}
        self._cache_popular: dict = {}

        # ALS item factors
        self.I_als = np.load(self.dir / 'als_I.npy')

        # Content similarity (precomputed top-100 per item)
        self.sim_idx = np.load(self.dir / 'content_sim_idx.npy')
        self.sim_val = np.load(self.dir / 'content_sim_val.npy')

        # Popularity
        self.pop_ranked = np.load(self.dir / 'pop_ranked.npy')
        self.pop_scores = np.load(self.dir / 'pop_scores.npy')
        self.pop_norm   = self.pop_scores / max(self.pop_scores.max(), 1)

        # Item2Vec embeddings (Word2Vec on purchase sequences, trained in notebook)
        i2v_emb_path  = self.dir / 'item2vec_emb.npy'
        i2v_mask_path = self.dir / 'item2vec_has_emb.npy'
        if i2v_emb_path.exists() and i2v_mask_path.exists():
            raw  = np.load(i2v_emb_path).astype(np.float32)   # (n_items, 64)
            norms = np.linalg.norm(raw, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            self.i2v_emb = raw / norms                         # L2-normalised → dot = cosine
            self.i2v_has = np.load(i2v_mask_path)              # bool mask
            n_has = int(self.i2v_has.sum())
            print(f'[Recommender] Item2Vec: {n_has:,}/{len(self.i2v_has):,} items have embeddings')
        else:
            self.i2v_emb = None
            self.i2v_has = None
            print('[Recommender] Item2Vec embeddings not found — using ALS+Content fallback')

        print(f'[Recommender] Ready: {self.n_items:,} items')

    # ─────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────
    def _item_info(self, idx: int) -> dict:
        asin = str(self.idx2asin[idx])
        m    = self.meta_dict.get(asin, {})
        price_raw = m.get('price')
        if price_raw is not None and not pd.isna(price_raw):
            price = float(price_raw)
        else:
            # Fallback: median giá theo danh mục, tránh hiển thị "Liên hệ"
            cat   = str(m.get('main_category', '') or '')
            price = self._price_by_cat.get(cat, self._global_price_median)
        return {
            'asin'    : asin,
            'title'   : str(m.get('title',         '') or '')[:200],
            'brand'   : str(m.get('store',          '') or ''),
            'category': str(m.get('main_category',  '') or ''),
            'price'   : price,
            'rating'  : float(m.get('avg_rating',   0) or 0),
            'n_rating': int(m.get('rating_number',  0) or 0),
            'image'   : str(m.get('image_url',      '') or ''),
            'sold'    : int(self.pop_scores[idx]) if idx < len(self.pop_scores) else 0,
        }

    def _normalize(self, arr: np.ndarray) -> np.ndarray:
        valid = arr > -np.inf
        if not valid.any():
            return arr
        amin, amax = arr[valid].min(), arr[valid].max()
        if amax == amin:
            return arr
        out = np.full_like(arr, -np.inf)
        out[valid] = (arr[valid] - amin) / (amax - amin)
        return out

    def _build_user_vector(self, interactions: list) -> tuple[np.ndarray, np.ndarray, np.ndarray | None] | None:
        """
        Build user embedding (ALS) and optionally Item2Vec user vector.
        Returns: (als_user_vec, seen_item_indices, i2v_user_vec or None)
        """
        weights = {'view': 1.0, 'click': 1.5, 'cart': 2.5, 'rate': 3.0}
        valid_items, valid_weights = [], []
        for it in interactions:
            asin = it['asin']
            if asin not in self.i2idx:
                continue
            idx = self.i2idx[asin]
            w = weights.get(it['action'], 1.0)
            if it.get('rating'):
                w *= (it['rating'] / 5.0) * 2
            valid_items.append(idx)
            valid_weights.append(w)

        if not valid_items:
            return None

        idxs = np.array(valid_items)
        wts  = np.array(valid_weights, dtype=np.float32)

        # ALS weighted average
        als_vec = (self.I_als[idxs].T @ wts) / wts.sum()

        # Item2Vec weighted average (only over items that have embeddings)
        i2v_vec = None
        if self.i2v_emb is not None:
            mask = self.i2v_has[idxs]
            if mask.any():
                sub_idxs = idxs[mask]
                sub_wts  = wts[mask]
                i2v_vec  = (self.i2v_emb[sub_idxs].T @ sub_wts) / sub_wts.sum()
                norm = np.linalg.norm(i2v_vec)
                if norm > 0:
                    i2v_vec = i2v_vec / norm

        return als_vec, idxs, i2v_vec

    def _item2vec_topk(self, i: int, k: int, exclude: set | None = None) -> list[tuple[int, float]]:
        """
        Item2Vec cosine similarity top-k neighbours for item index i.
        Returns list of (item_idx, score) sorted descending.
        """
        if self.i2v_emb is None or not self.i2v_has[i]:
            return []
        sims = self.i2v_emb @ self.i2v_emb[i]   # (n_items,) dot product = cosine (L2-normed)
        sims[i] = -1.0                            # exclude self
        if exclude:
            for ex in exclude:
                if ex < len(sims):
                    sims[ex] = -1.0
        # Only consider items that have embeddings
        sims[~self.i2v_has] = -1.0
        fetch = min(k + 20, self.n_items - 1)
        top   = np.argpartition(-sims, fetch)[:fetch]
        top   = top[np.argsort(-sims[top])]
        return [(int(j), float(sims[j])) for j in top if sims[j] > -1.0][:k]

    # ─────────────────────────────────────────────────────────
    # MAIN RECOMMEND
    # ─────────────────────────────────────────────────────────
    def recommend(self, interactions: list, k: int = 12) -> tuple[list, str]:
        """
        Main entry point — tự chọn thuật toán dựa trên số interactions.
        Returns: (list of items, algorithm name)
        """
        if len(interactions) < 3:
            return self.popular(k), 'Popularity (Cold-start)'

        result = self._build_user_vector(interactions)
        if result is None:
            return self.popular(k), 'Popularity (No valid history)'

        als_vec, seen_items, i2v_vec = result

        # Signal 1: ALS collaborative filtering
        als_s = self._normalize((als_vec @ self.I_als.T).copy())

        # Signal 2: Item2Vec (if available)
        if i2v_vec is not None:
            i2v_s = self.i2v_emb @ i2v_vec   # cosine since both L2-normed
            i2v_s = self._normalize(i2v_s.copy())
            use_i2v = True
        else:
            i2v_s = np.zeros(self.n_items, dtype=np.float32)
            use_i2v = False

        # Signal 3: Content-based (từ items rating cao)
        cb_s = np.zeros(self.n_items, dtype=np.float32)
        rated = [(self.i2idx[it['asin']], it['rating'])
                 for it in interactions
                 if it['asin'] in self.i2idx
                 and it.get('rating') is not None
                 and it['rating'] >= 4]
        for (idx, r) in rated:
            cb_s[self.sim_idx[idx]] += self.sim_val[idx] * (r / 5.0)
        cb_s = self._normalize(cb_s)

        # Blend: weights từ config.json (grid search best weights)
        if use_i2v:
            # 4-signal: ALS + Item2Vec + Content + Popularity
            final = (self.alpha * als_s + self.beta * i2v_s
                     + self.gamma * cb_s + self.delta * self.pop_norm)
            algo  = 'Hybrid (ALS + Item2Vec + Content + Popularity)'
        else:
            # 3-signal fallback: phân phối lại weight của I2V theo tỉ lệ
            denom  = self.alpha + self.gamma + self.delta
            w_als  = self.alpha / denom
            w_cb   = self.gamma / denom
            w_pop  = self.delta / denom
            final  = w_als * als_s + w_cb * cb_s + w_pop * self.pop_norm
            algo   = 'Hybrid (ALS + Content + Popularity)'

        final[seen_items] = -np.inf

        top = np.argpartition(-final, k)[:k]
        top = top[np.argsort(-final[top])]
        return [self._item_info(int(i)) for i in top], algo

    def popular(self, k: int = 12) -> list:
        if k not in self._cache_popular:
            self._cache_popular[k] = [self._item_info(int(i)) for i in self.pop_ranked[:k]]
        return self._cache_popular[k]

    def similar_items(self, asin: str, k: int = 10) -> list:
        """
        Sản phẩm tương tự.
        Primary: Item2Vec cosine similarity (94% coverage).
        Fallback: TF-IDF content similarity.
        """
        cache_key = (asin, k)
        if cache_key in self._cache_similar:
            return self._cache_similar[cache_key]

        result: list = []
        if asin in self.i2idx:
            i = self.i2idx[asin]
            if self.i2v_emb is not None and self.i2v_has[i]:
                pairs = self._item2vec_topk(i, k)
                if pairs:
                    result = [self._item_info(j) for j, _ in pairs]
            if not result:
                result = [self._item_info(int(x)) for x in self.sim_idx[i][:k]]

        self._cache_similar[cache_key] = result
        return result

    def get_product(self, asin: str) -> dict | None:
        if asin in self._cache_product:
            return self._cache_product[asin]
        result = self._item_info(self.i2idx[asin]) if asin in self.i2idx else None
        self._cache_product[asin] = result
        return result

    def more_from_store(self, asin: str, k: int = 8) -> tuple[list, str]:
        """Sản phẩm khác của cùng store/brand. Fallback: cùng danh mục nếu store có ít sản phẩm."""
        cache_key = (asin, k)
        if cache_key in self._cache_store:
            return self._cache_store[cache_key]

        result: list = []
        label  = 'Same Store'

        if asin in self.i2idx:
            m     = self.meta_dict.get(asin, {})
            store = str(m.get('store', '') or '').strip()

            if store:
                mask   = self.meta['store'].str.lower().str.strip() == store.lower()
                subset = self.meta[mask & (self.meta['asin'] != asin)].copy()
                if not subset.empty:
                    subset['_pop'] = subset['asin'].map(
                        lambda a: int(self.pop_scores[self.i2idx[a]]) if a in self.i2idx else 0
                    )
                    top    = subset.sort_values('_pop', ascending=False).head(k)
                    result = [self._item_info(self.i2idx[a]) for a in top['asin'] if a in self.i2idx]

            # Fallback: cùng danh mục khi store không đủ sản phẩm
            if len(result) < 2:
                label = 'Same Category'
                cat   = str(m.get('main_category', '') or '').strip()
                if cat:
                    cat_mask  = (self.meta['main_category'] == cat) & (self.meta['asin'] != asin)
                    cat_sub   = self.meta[cat_mask].copy()
                    if not cat_sub.empty:
                        cat_sub['_pop'] = cat_sub['asin'].map(
                            lambda a: int(self.pop_scores[self.i2idx[a]]) if a in self.i2idx else 0
                        )
                        top_cat = cat_sub.sort_values('_pop', ascending=False).head(k)
                        result  = [self._item_info(self.i2idx[a]) for a in top_cat['asin'] if a in self.i2idx]

        self._cache_store[cache_key] = (result, label)
        return result, label

    def search(self, query: str, k: int = 20) -> list:
        if not query or len(query) < 2:
            return []
        q    = query.lower()
        mask = self.meta['title'].str.lower().str.contains(q, na=False, regex=False)
        results = self.meta[mask].head(k)
        return [self._item_info(self.i2idx[a]) for a in results['asin'] if a in self.i2idx]

    def _keyword_mask(self, keywords: list[str]) -> 'pd.Series':
        titles = self.meta['title'].str.lower()
        mask   = pd.Series(False, index=self.meta.index)
        for kw in keywords:
            mask |= titles.str.contains(kw, regex=False, na=False)
        return mask

    def get_categories(self) -> list[str]:
        if hasattr(self, '_cached_categories'):
            return self._cached_categories
        known  = set(self.i2idx.keys())
        result = []
        for name, kws in SUBCATEGORIES.items():
            count = (self._keyword_mask(kws) & self.meta['asin'].isin(known)).sum()
            if count >= 50:
                result.append(name)
        self._cached_categories = result
        return result

    def browse_by_category(self, category: str = None, k: int = 30) -> list:
        if not category:
            return self.popular(k)
        if category in SUBCATEGORIES:
            known  = set(self.i2idx.keys())
            mask   = self._keyword_mask(SUBCATEGORIES[category]) & self.meta['asin'].isin(known)
            subset = self.meta[mask].copy()
            subset['_pop'] = subset['asin'].map(
                lambda a: int(self.pop_scores[self.i2idx[a]]) if a in self.i2idx else 0
            )
            top = subset.sort_values('_pop', ascending=False).head(k)
            return [self._item_info(self.i2idx[a]) for a in top['asin'] if a in self.i2idx]
        mask  = self.meta['main_category'].str.lower() == category.lower()
        items = self.meta[mask].head(k)
        return [self._item_info(self.i2idx[a]) for a in items['asin'] if a in self.i2idx]

    def _detect_subcategory(self, asin: str) -> str | None:
        m     = self.meta_dict.get(asin, {})
        title = str(m.get('title', '')).lower()
        for name, kws in SUBCATEGORIES.items():
            if any(kw in title for kw in kws):
                return name
        return None

    def recommend_from_cart(self, cart_asins: list[str], k: int = 8) -> list:
        """
        Gợi ý sản phẩm bổ sung cho giỏ hàng.
        Scoring: Item2Vec (0.6) + Content (0.25) + Complementary boost (0.3) + Pop (0.1)
        """
        valid_idx = [self.i2idx[a] for a in cart_asins if a in self.i2idx]
        if not valid_idx:
            return self.popular(k)

        known = set(self.i2idx.keys())
        scores = np.zeros(self.n_items, dtype=np.float32)

        # ── Signal 1: Item2Vec (primary — 0.6 weight) ────────────────────────
        if self.i2v_emb is not None:
            i2v_vecs = [self.i2v_emb[idx] for idx in valid_idx if self.i2v_has[idx]]
            if i2v_vecs:
                cart_vec = np.array(i2v_vecs).mean(axis=0).astype(np.float32)
                norm = np.linalg.norm(cart_vec)
                if norm > 0:
                    cart_vec /= norm
                i2v_s = self.i2v_emb @ cart_vec
                i2v_s[~self.i2v_has] = 0.0
                scores += 0.6 * np.clip(i2v_s, 0, None)

        # ── Signal 2: TF-IDF content similarity (secondary — 0.25) ───────────
        for idx in valid_idx:
            scores[self.sim_idx[idx]] += 0.25 * self.sim_val[idx]

        # ── Signal 3: Complementary category soft boost (+0.3 binary mask) ───
        # Soft boost — không override Item2Vec, chỉ ưu tiên hơn trong cùng score range
        cart_cats: set[str] = set()
        for asin in cart_asins:
            cat = self._detect_subcategory(asin)
            if cat:
                cart_cats.add(cat)

        if cart_cats:
            comp_cats: set[str] = set()
            for cat in cart_cats:
                for c in COMPLEMENTARY_MAP.get(cat, []):
                    if c not in cart_cats:
                        comp_cats.add(c)
            if comp_cats:
                comp_mask = np.zeros(self.n_items, dtype=np.float32)
                for cat in comp_cats:
                    mask = self._keyword_mask(SUBCATEGORIES[cat]) & self.meta['asin'].isin(known)
                    for asin in self.meta[mask]['asin']:
                        if asin in self.i2idx:
                            comp_mask[self.i2idx[asin]] = 1.0
                scores += 0.3 * comp_mask

        # ── Signal 4: Popularity tie-breaker (0.1) ────────────────────────────
        scores += 0.1 * self.pop_norm

        # ── Remove cart items ─────────────────────────────────────────────────
        for idx in valid_idx:
            scores[idx] = -np.inf

        if scores.max() <= 0:
            return self.popular(k)

        k_fetch = min(k + 5, self.n_items - 1)
        top     = np.argpartition(-scores, k_fetch)[:k_fetch]
        top     = top[np.argsort(-scores[top])][:k]
        return [self._item_info(int(i)) for i in top if scores[i] > -np.inf]

    def bought_together(self, asin: str, k: int = 6) -> list:
        """
        'Thường mua kèm' dùng Item2Vec cosine similarity.

        Pipeline:
          1. Item2Vec cosine similarity → ứng viên (loại same-subcategory)
          2. Bổ sung từ complementary categories + content sim nếu chưa đủ
        """
        cache_key = (asin, k)
        if cache_key in self._cache_bought:
            return self._cache_bought[cache_key]
        if asin not in self.i2idx:
            self._cache_bought[cache_key] = []
            return []
        i   = self.i2idx[asin]
        cat = self._detect_subcategory(asin)

        # ── Bước 1: Item2Vec cosine similarity ────────────────────────────────
        i2v_results: list[tuple[int, float]] = []
        if self.i2v_emb is not None and self.i2v_has[i]:
            sims = self.i2v_emb @ self.i2v_emb[i]
            sims[i] = -1.0
            sims[~self.i2v_has] = -1.0

            # Cross-category filter: drop same subcategory
            fetch   = min(k * 8, self.n_items - 1)
            cands   = np.argpartition(-sims, fetch)[:fetch]
            cands   = cands[np.argsort(-sims[cands])]

            for j in cands:
                if len(i2v_results) >= k:
                    break
                j = int(j)
                if sims[j] < 0:
                    break
                cat_j = self._detect_subcategory(str(self.idx2asin[j]))
                # Skip items in same subcategory if both have known categories
                if cat is not None and cat_j is not None and cat_j == cat:
                    continue
                # Blend i2v cosine + popularity for ranking
                score = 0.7 * float(sims[j]) + 0.3 * float(self.pop_norm[j])
                i2v_results.append((j, score))

        if len(i2v_results) >= k:
            return [self._item_info(j) for j, _ in i2v_results[:k]]

        # ── Bước 2: Complementary categories bổ sung ──────────────────────────
        seen = {i} | {j for j, _ in i2v_results}
        comp_cats = COMPLEMENTARY_MAP.get(cat, []) if cat else []
        known     = set(self.i2idx.keys())
        comp_items: list[tuple[int, float]] = []

        if comp_cats:
            for cat_name in comp_cats:
                mask = self._keyword_mask(SUBCATEGORIES[cat_name]) & self.meta['asin'].isin(known)
                for asin_c in self.meta[mask]['asin']:
                    if asin_c not in self.i2idx:
                        continue
                    j = self.i2idx[asin_c]
                    if j in seen:
                        continue
                    # Score: i2v sim (if available) + popularity
                    if self.i2v_emb is not None and self.i2v_has[i] and self.i2v_has[j]:
                        sim_score = float(self.i2v_emb[i] @ self.i2v_emb[j])
                        score = 0.5 * sim_score + 0.5 * float(self.pop_norm[j])
                    else:
                        score = float(self.pop_norm[j])
                    comp_items.append((j, score))
                    seen.add(j)

            comp_items.sort(key=lambda x: -x[1])

        combined = i2v_results + comp_items
        if combined:
            result = [self._item_info(j) for j, _ in combined[:k]]
            self._cache_bought[cache_key] = result
            return result

        # ── Bước 3: Fallback content similarity ────────────────────────────────
        fallback = [(int(j), 0.4 * float(v) + 0.2 * float(self.pop_norm[j]))
                    for j, v in zip(self.sim_idx[i], self.sim_val[i]) if int(j) != i]
        fallback.sort(key=lambda x: -x[1])
        result = [self._item_info(j) for j, _ in fallback[:k]]
        self._cache_bought[cache_key] = result
        return result
