"""
Precompute bought-together associations — cross-category only.

Vấn đề với phiên bản cũ:
  - Lift explode với count thấp (lift=24175 từ 3 user → noise)
  - Không lọc same-category → case recommend case thay vì screen protector

Fix:
  - Chỉ đếm co-occurrence giữa các item KHÁC category (cross-category)
  - Dùng Dice score = 2*count(A,B) / (freq_A + freq_B) — bounded [0,1], symmetric
  - MIN_SUPPORT = 5 (tối thiểu 5 user cùng tương tác)

Output: api_artifacts/bought_together.json
  { "item_idx": [[item_idx, dice_score, count], ...] }  — top 20, sorted desc
"""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')

from collections import defaultdict
from pathlib import Path
import pandas as pd

ARTIFACTS_DIR = Path('api_artifacts')
TOP_K        = 20
MIN_SUPPORT  = 5
MAX_PER_USER = 60   # cap để tránh O(n²) explosion

# ── Load metadata để detect subcategory ────────────────────────────────────
SUBCATEGORIES = {
    'Ốp lưng & Bao da':        ['phone case', 'back case', 'back cover', 'wallet case',
                                 'bumper', 'holster', 'flip case', 'folio case',
                                 'protective case', 'slim case', 'tpu case', 'silicone case'],
    'Kính cường lực':           ['screen protector', 'tempered glass', 'privacy screen',
                                 'glass screen', 'privacy glass'],
    'Sạc & Adapter':            ['charger', 'charging pad', 'wireless charger', 'fast charger',
                                 'car charger', 'wall charger', 'charging dock', 'charging station'],
    'Cáp kết nối':              ['usb cable', 'lightning cable', 'type-c cable', 'type c cable',
                                 'charging cable', 'data cable', 'usb-c cable', 'braided cable'],
    'Đồng hồ & Vòng đeo':      ['smart watch', 'smartwatch', 'apple watch', 'samsung watch',
                                 'fitness tracker', 'watch band', 'watch strap',
                                 'watch charger', 'watch case'],
    'Giá đỡ & Kẹp':            ['phone mount', 'car mount', 'phone holder', 'phone stand',
                                 'desk stand', 'car holder', 'dashboard mount',
                                 'windshield mount', 'bike mount', 'wall mount'],
    'Pin & Sạc dự phòng':      ['power bank', 'portable charger', 'backup battery',
                                 'battery pack', 'portable battery'],
    'Bảo vệ Camera':           ['camera lens protector', 'camera protector', 'lens protector',
                                 'camera screen protector', 'camera cover'],
    'Tai nghe & Loa':          ['earphone', 'headphone', 'earbud', 'bluetooth speaker',
                                 'portable speaker', 'wireless earphone'],
    'Nhẫn & Grip':             ['phone ring', 'ring holder', 'pop socket', 'popsocket',
                                 'phone grip', 'finger ring', 'ring stand'],
    'Bút & Bàn phím':          ['stylus', 'apple pencil', 'bluetooth keyboard',
                                 'wireless keyboard'],
    'Selfie & Chụp ảnh':       ['selfie stick', 'selfie ring', 'tripod', 'monopod'],
}

print('Loading metadata...')
meta     = pd.read_parquet(ARTIFACTS_DIR / 'meta_api.parquet')
item_map = pd.read_parquet(ARTIFACTS_DIR / 'item_map.parquet')
i2asin   = dict(zip(item_map['i'], item_map['asin']))
meta_dict = meta.set_index('asin').to_dict('index')

def detect_cat(item_idx: int) -> str | None:
    asin  = str(i2asin.get(item_idx, ''))
    title = str(meta_dict.get(asin, {}).get('title', '')).lower()
    for cat, kws in SUBCATEGORIES.items():
        if any(kw in title for kw in kws):
            return cat
    return None

# Cache categories cho toàn bộ items
print('Pre-caching item categories...')
item_cats: dict[int, str | None] = {}
for i in range(len(item_map)):
    item_cats[i] = detect_cat(i)
cat_counts = sum(1 for c in item_cats.values() if c)
print(f'  Items có category: {cat_counts:,} / {len(item_cats):,}')

# ── Load user history ───────────────────────────────────────────────────────
print('\nLoading user_history.json...')
with open(ARTIFACTS_DIR / 'user_history.json') as f:
    user_hist = json.load(f)
print(f'  {len(user_hist):,} users')

item_freq = defaultdict(int)                        # item_idx → n_users
cooccur   = defaultdict(lambda: defaultdict(int))   # item_a → item_b → count

cross_kept = 0
same_skipped = 0

print('Computing CROSS-CATEGORY co-occurrences...')
for n, (uid, hist) in enumerate(user_hist.items()):
    items = list({int(e[0]) for e in hist})

    # Cap heavy users: ưu tiên items có rating cao
    if len(items) > MAX_PER_USER:
        sorted_hist = sorted(hist, key=lambda x: -float(x[1]))
        items = list({int(e[0]) for e in sorted_hist[:MAX_PER_USER]})

    for i in items:
        item_freq[i] += 1

    for a in range(len(items)):
        for b in range(a + 1, len(items)):
            ia, ib = items[a], items[b]
            cat_a = item_cats.get(ia)
            cat_b = item_cats.get(ib)

            # Bỏ qua nếu cùng category → không phải "mua kèm"
            if cat_a is not None and cat_b is not None and cat_a == cat_b:
                same_skipped += 1
                continue

            cooccur[ia][ib] += 1
            cooccur[ib][ia] += 1
            cross_kept += 1

    if (n + 1) % 20_000 == 0:
        print(f'  {n+1:,} users | cross-pairs: {cross_kept:,} | same-cat skipped: {same_skipped:,}')

print(f'\nDone.')
print(f'  Cross-category pairs kept  : {cross_kept:,}')
print(f'  Same-category pairs skipped: {same_skipped:,}')
print(f'  Items with co-occ data     : {len(cooccur):,}')

# ── Tính Dice score & build top-K ──────────────────────────────────────────
print('\nComputing Dice scores & building top-K lists...')
bought_together = {}

for item_a, neighbors in cooccur.items():
    scored = []
    freq_a = item_freq[item_a]
    for item_b, count in neighbors.items():
        if count < MIN_SUPPORT:
            continue
        freq_b = item_freq[item_b]
        # Dice coefficient = 2*|A∩B| / (|A| + |B|)  — bounded [0,1]
        dice = (2 * count) / (freq_a + freq_b)
        scored.append((item_b, round(dice, 5), count))

    if scored:
        scored.sort(key=lambda x: -x[1])
        bought_together[item_a] = scored[:TOP_K]

print(f'Items với bought-together data: {len(bought_together):,}')

# Stats
all_dice   = [e[1] for v in bought_together.values() for e in v]
all_counts = [e[2] for v in bought_together.values() for e in v]
if all_dice:
    all_dice.sort()
    print(f'Dice — min:{min(all_dice):.4f}  median:{all_dice[len(all_dice)//2]:.4f}  max:{max(all_dice):.4f}')
    all_counts.sort()
    print(f'Count — min:{min(all_counts)}  median:{all_counts[len(all_counts)//2]}  max:{max(all_counts)}')

# Verify quality: xem vài examples
print('\n=== SAMPLE RESULTS ===')
import random
random.seed(42)
sample_keys = random.sample(list(bought_together.keys()), min(5, len(bought_together)))
for key in sample_keys:
    asin = str(i2asin.get(int(key), ''))
    title = str(meta_dict.get(asin, {}).get('title', ''))[:55]
    print(f'\n[{asin}] {title}')
    for entry in bought_together[key][:4]:
        asin_b = str(i2asin.get(int(entry[0]), ''))
        title_b = str(meta_dict.get(asin_b, {}).get('title', ''))[:60]
        print(f'  dice={entry[1]:.4f} cnt={entry[2]}  → {title_b}')

# Save
out = ARTIFACTS_DIR / 'bought_together.json'
with open(out, 'w') as f:
    json.dump(bought_together, f)
print(f'\nSaved → {out}  ({out.stat().st_size / 1024:.0f} KB)')
