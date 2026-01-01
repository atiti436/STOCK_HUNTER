#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""快速篩選今日強勢股"""

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

print('🔄 抓取今日全市場股票資料...')

# 1. 抓取所有股票
url = 'https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL'
response = requests.get(url, timeout=15, verify=False)
data = response.json()

# 2. 篩選條件
stocks = []
for item in data:
    ticker = item.get('Code', '')
    name = item.get('Name', '')
    
    if not (ticker.isdigit() and len(ticker) == 4):
        continue
    if ticker.startswith('00'):
        continue
    
    try:
        close_str = item.get('ClosingPrice', '0').replace(',', '')
        close = float(close_str) if close_str else 0
        
        change_str = item.get('Change', '0').replace(',', '').replace('+', '')
        change = float(change_str) if change_str and change_str != 'X' else 0
        
        prev_close = close - change
        change_pct = (change / prev_close * 100) if prev_close > 0 else 0
        
        volume_str = item.get('TradeVolume', '0').replace(',', '')
        volume = int(volume_str) if volume_str else 0
        volume_lots = volume // 1000
        
        turnover_str = item.get('TradeValue', '0').replace(',', '')
        turnover = int(turnover_str) if turnover_str else 0
    except:
        continue
    
    if close <= 0:
        continue
    
    # 基本篩選：價格 10-500、成交量 > 300張、成交金額 > 500萬
    if 10 <= close <= 500 and volume_lots >= 300 and turnover >= 5_000_000:
        # 漲超過 3%
        if change_pct >= 3.0:
            stocks.append({
                'ticker': ticker,
                'name': name,
                'price': close,
                'change_pct': round(change_pct, 2),
                'volume': volume_lots,
                'turnover': turnover
            })

# 3. 排序：按漲幅
stocks = sorted(stocks, key=lambda x: x['change_pct'], reverse=True)

print(f'\n📊 今日強勢股 TOP 20 (漲幅 >= 3%)')
print('=' * 60)
for i, s in enumerate(stocks[:20], 1):
    vol_str = f"{s['volume']:,}"
    print(f"{i:2}. {s['ticker']} {s['name']:<8} ${s['price']:>7.1f} | {s['change_pct']:+5.2f}% | {vol_str:>8}張")

print('\n⚠️ 這只是初步篩選，需要進一步看法人和財報')
print(f'共 {len(stocks)} 檔符合條件')
