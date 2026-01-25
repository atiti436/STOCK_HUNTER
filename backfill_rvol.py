"""
補填歷史 RVol 資料
將 volume、avg_volume、rvol 補進所有 history JSON

用法：python backfill_rvol.py
"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

# FinMind Token（從 scan_20260106.py 複製）
FINMIND_TOKENS = [
    'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMS0wNSAyMzowODozMSIsInVzZXJfaWQiOiJhdGl0aSIsImVtYWlsIjoiYXRpdGk0MzYxQGdtYWlsLmNvbSIsImlwIjoiMTExLjI0My4xNDIuOTkifQ.MEcPu8FHrrY2ES1j26NRO9Dg9E2ekEhM4B5rlCPidSI',
]
CURRENT_TOKEN_INDEX = 0

def get_finmind_token():
    global CURRENT_TOKEN_INDEX
    return FINMIND_TOKENS[CURRENT_TOKEN_INDEX % len(FINMIND_TOKENS)]

def fetch_historical_prices_for_date(ticker, target_date, days=10):
    """
    抓取指定日期的歷史股價
    target_date: '2026-01-07' 格式
    返回: [(date, close, volume, high, low), ...] 最新在前
    """
    try:
        from FinMind.data import DataLoader
        dl = DataLoader()
        dl.login_by_token(api_token=get_finmind_token())

        # 計算日期範圍：target_date 往前 days*2 天（避免假日影響）
        end_date = datetime.strptime(target_date, '%Y-%m-%d')
        start_date = end_date - timedelta(days=days * 2)

        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')

        df = dl.taiwan_stock_daily(
            stock_id=ticker,
            start_date=start_str,
            end_date=end_str
        )

        if df is None or df.empty:
            return []

        prices = []
        for _, row in df.iterrows():
            date_str = str(row.get('date', ''))[:10]
            close = float(row.get('close', 0))
            volume = int(row.get('Trading_Volume', 0)) // 1000  # 轉成張
            high = float(row.get('max', row.get('high', close)))
            low = float(row.get('min', row.get('low', close)))

            if close > 0 and volume > 0:
                prices.append((date_str, close, volume, high, low))

        # 排序：最新在前，只取到 target_date 為止
        prices = sorted(prices, key=lambda x: x[0], reverse=True)
        prices = [p for p in prices if p[0] <= target_date]

        return prices[:days]

    except Exception as e:
        print(f'   [{ticker}] 錯誤: {e}')
        return []

def calculate_volume_metrics(prices):
    """
    計算成交量指標
    prices: [(date, close, volume, high, low), ...] 最新在前
    返回: (today_volume, avg_volume_5d, rvol)
    """
    if not prices or len(prices) < 1:
        return 0, 0, 0

    today_volume = prices[0][2]

    # 5日平均量（不含今天）
    if len(prices) >= 6:
        volumes = [p[2] for p in prices[1:6]]
        avg_volume = sum(volumes) / len(volumes)
    elif len(prices) >= 2:
        volumes = [p[2] for p in prices[1:]]
        avg_volume = sum(volumes) / len(volumes)
    else:
        avg_volume = today_volume

    # RVol
    rvol = round(today_volume / avg_volume, 2) if avg_volume > 0 else 0

    return today_volume, int(avg_volume), rvol

def backfill_history_file(filepath):
    """補填單一 history JSON 檔案"""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    target_date = data.get('date', '')
    stocks = data.get('stocks', [])

    if not target_date or not stocks:
        return False, 0

    # 檢查是否已經有 rvol
    if stocks and 'rvol' in stocks[0]:
        return False, 0  # 已經補過了

    updated_count = 0

    for stock in stocks:
        ticker = stock.get('ticker', '')
        if not ticker:
            continue

        # 拉歷史價格
        prices = fetch_historical_prices_for_date(ticker, target_date, days=10)

        if prices:
            volume, avg_volume, rvol = calculate_volume_metrics(prices)
            stock['volume'] = volume
            stock['avg_volume'] = avg_volume
            stock['rvol'] = rvol
            updated_count += 1
            print(f'   [{ticker}] volume={volume}, avg={avg_volume}, rvol={rvol}')
        else:
            stock['volume'] = 0
            stock['avg_volume'] = 0
            stock['rvol'] = 0
            print(f'   [{ticker}] 無資料')

        # 避免 API rate limit
        time.sleep(0.3)

    # 寫回檔案
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return True, updated_count

def main():
    history_dir = Path('data/history')

    # 找所有 history JSON（排除 all_history.json）
    json_files = sorted([
        f for f in history_dir.glob('*.json')
        if f.name != 'all_history.json' and f.name.startswith('2026')
    ])

    print(f'找到 {len(json_files)} 個歷史檔案')
    print('=' * 50)

    total_updated = 0
    files_updated = 0

    for filepath in json_files:
        print(f'\n處理: {filepath.name}')

        try:
            updated, count = backfill_history_file(filepath)
            if updated:
                files_updated += 1
                total_updated += count
                print(f'   [OK] 更新 {count} 檔股票')
            else:
                print(f'   [SKIP] 已補過或無資料')
        except Exception as e:
            print(f'   [ERROR] {e}')

    print('\n' + '=' * 50)
    print(f'完成！更新 {files_updated} 個檔案，共 {total_updated} 筆股票資料')

if __name__ == '__main__':
    main()
