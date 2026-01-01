#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Debug script for 緯創 3231"""

from FinMind.data import DataLoader
from datetime import datetime, timedelta

dl = DataLoader()

# 模擬 scan_v3.py 的邏輯
end_date = datetime.now() - timedelta(days=1)
start_date = end_date - timedelta(days=30)

print(f'日期範圍: {start_date.strftime("%Y-%m-%d")} ~ {end_date.strftime("%Y-%m-%d")}')

df = dl.taiwan_stock_institutional_investors(
    stock_id='3231',
    start_date=start_date.strftime('%Y-%m-%d'),
    end_date=end_date.strftime('%Y-%m-%d')
)

print(f'共 {len(df)} 筆資料')
print(f'日期: {sorted(df["date"].unique())}')

# 計算買超天數
ticker_data = {}
for _, row in df.iterrows():
    date_str = str(row.get('date', '')).replace('-', '')
    name = str(row.get('name', '')).strip()
    buy = int(row.get('buy', 0))
    sell = int(row.get('sell', 0))
    net = (buy - sell) // 1000  # 轉成張
    
    if date_str not in ticker_data:
        ticker_data[date_str] = {'date': date_str, 'foreign': 0, 'trust': 0, 'total': 0}
    
    if 'Foreign_Investor' in name:
        ticker_data[date_str]['foreign'] += net
    elif 'Investment_Trust' in name:
        ticker_data[date_str]['trust'] += net
    
    ticker_data[date_str]['total'] = ticker_data[date_str]['foreign'] + ticker_data[date_str]['trust']

# 排序（最新在前）
inst_history = sorted(ticker_data.values(), key=lambda x: x['date'], reverse=True)

print('\n法人買賣超歷史 (最新10天):')
for r in inst_history[:10]:
    status = '✅' if r['total'] > 0 else '❌'
    print(f"  {r['date']}: 外資 {r['foreign']:+,} 投信 {r['trust']:+,} 合計 {r['total']:+,} {status}")

# 計算連續買超天數
count = 0
for record in inst_history:
    if record['total'] > 0:
        count += 1
    else:
        break
print(f'\n連續買超天數: {count}')

# v3.1 條件：3-5 天
# v3.2 條件：2-7 天
print(f'v3.1 條件 (3-5天): {"✅ 通過" if 3 <= count <= 5 else "❌ 未通過"}')
print(f'v3.2 條件 (2-7天): {"✅ 通過" if 2 <= count <= 7 else "❌ 未通過"}')
