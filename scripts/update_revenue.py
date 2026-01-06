
# 每月營收更新腳本
import sys
import os

# 把專案根目錄加入路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.fetcher import FinMindFetcher
from src.cache import RevenueCache
from src.config import REVENUE_CACHE_PATH 
from datetime import datetime, timedelta

def update_revenue():
    print('='*60)
    print(f'Starting Revenue Update Job: {datetime.now()}')
    print('='*60)
    
    fetcher = FinMindFetcher()
    
    # 1. 取得全市場股票代號
    # 為了省事，先抓一次 Daily 拿所有代號
    print("[1/3] Fetching Stock List...")
    # 使用昨天 (因為今天凌晨可能沒資料)
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    df_daily = fetcher.get_daily_snapshot(date_str=yesterday)
    
    if df_daily is None or df_daily.empty:
        # 再試試前天 (避開假日)
        day_before = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
        print(f"      Retry with {day_before}...")
        df_daily = fetcher.get_daily_snapshot(date_str=day_before)
        
    if df_daily is None or df_daily.empty:
        print("[ERROR] Failed to fetch stock list")
        return
        
    all_tickers = df_daily['stock_id'].unique().tolist()
    # 過濾掉權證等 (長度>4 通常要注意, 但有些 65xx 興櫃也是 4 碼)
    # 簡單過濾：只留 4 碼數字
    tickers = [t for t in all_tickers if len(t) == 4 and t.isdigit()]
    
    print(f"      Target: {len(tickers)} stocks")
    
    # 2. 逐檔抓取營收
    print("[2/3] Fetching Revenue Data (Sequential)...")
    # 正式版：抓取全部
    # print("      [TEST MODE] Limiting to first 5 stocks for validation")
    # tickers = tickers[:5]  
    
    revenue_map = {}
    results = fetcher.get_revenue_batch(tickers)
    
    # 3. 計算 YoY 並整理
    print("[3/3] Processing & Caching...")
    for ticker, df in results.items():
        if df.empty: continue
        
        # 邏輯同 scan_v4.py
        try:
            latest = df.iloc[-1]
            rev_now = float(latest.get('revenue', 0))
            if rev_now == 0: continue
            
            yy = latest.get('revenue_year')
            mm = latest.get('revenue_month')
            
            # 找去年同期
            prev = df[(df['revenue_year'] == yy-1) & (df['revenue_month'] == mm)]
            if prev.empty: continue
            
            rev_prev = float(prev.iloc[0]['revenue'])
            if rev_prev == 0: continue
            
            yoy = ((rev_now - rev_prev) / rev_prev) * 100
            
            revenue_map[ticker] = {
                'yoy': round(yoy, 2),
                'date': f"{yy}/{mm:02d}"
            }
        except:
            continue
            
    # 存檔
    cache = RevenueCache(REVENUE_CACHE_PATH)
    if cache.save(revenue_map):
        print(f"[SUCCESS] Revenue cache saved to {REVENUE_CACHE_PATH}")
        print(f"          Total records: {len(revenue_map)}")
    else:
        print("[ERROR] Failed to save cache")

if __name__ == "__main__":
    update_revenue()
