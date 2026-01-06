
# FinMind API Tokens
# 支援 Token 輪替 (當達到 rate limit 時)
FINMIND_TOKENS = [
    'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMS0wNSAyMzowODozMSIsInVzZXJfaWQiOiJhdGl0aSIsImVtYWlsIjoiYXRpdGk0MzYxQGdtYWlsLmNvbSIsImlwIjoiMTExLjI0My4xNDIuOTkifQ.MEcPu8FHrrY2ES1j26NRO9Dg9E2ekEhM4B5rlCPidSI',  # 2026-01-05 最新付費版 (Backer)
    'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMS0wMyAwMDoxODoyNSIsInVzZXJfaWQiOiJhdGl0aSIsImlwIjoiMTExLjI0My4xNDIuOTkifQ.0AoJDWaK-mWt1OhdyL6JdOI5TOkSpNEe-tDoI34aHjI',
    'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMS0wMSAyMjowNTozNSIsInVzZXJfaWQiOiJhdGl0aTQzNiIsImlwIjoiMTExLjI0My4xNDIuOTkifQ.ejONnKY_3b9tqA7wh47d2r5yfUKCFWybdNSkrJp3C10',
]

# 篩選條件設定
SCREENING_CRITERIA = {
    'price_min': 30,
    'price_max': 300,
    'pe_max': 35,
    'volume_min': 800,         # 日成交量
    'inst_5day_min': 300,      # 法人 5 日買超張數
    'inst_1month_min': -10000, # 法人 1 月累積買超 (避免法人大撤退)
    'rsi_max': 80,             # 避免過熱
}

# 檔案路徑設定
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
CACHE_DIR = os.path.join(DATA_DIR, 'cache')
HISTORY_DIR = os.path.join(DATA_DIR, 'history')

# 確保目錄存在
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)

REVENUE_CACHE_PATH = os.path.join(CACHE_DIR, 'revenue_cache.pkl')
