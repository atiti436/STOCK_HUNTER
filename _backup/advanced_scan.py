#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
進階篩選：法人買超 + 低漲幅（找剛起漲的）
輸出到檔案
"""

import requests
import urllib3
from datetime import datetime, timedelta
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CONFIG = {
    "MIN_PRICE": 10,
    "MAX_PRICE": 500,
    "MIN_VOLUME": 500,
    "API_TIMEOUT": 15,
}

# 1. 抓取當日所有股票
url_stocks = 'https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL'
response = requests.get(url_stocks, timeout=15, verify=False)
stock_data = response.json()

stocks = {}
for item in stock_data:
    ticker = item.get('Code', '')
    if not (ticker.isdigit() and len(ticker) == 4):
        continue
    if ticker.startswith('00'):
        continue
    
    try:
        close = float(item.get('ClosingPrice', '0').replace(',', '') or 0)
        change_str = item.get('Change', '0').replace(',', '').replace('+', '')
        change = float(change_str) if change_str and change_str != 'X' else 0
        prev_close = close - change
        change_pct = (change / prev_close * 100) if prev_close > 0 else 0
        volume = int(item.get('TradeVolume', '0').replace(',', '') or 0) // 1000
    except:
        continue
    
    if close <= 0:
        continue
    
    stocks[ticker] = {
        'name': item.get('Name', ''),
        'price': close,
        'change_pct': round(change_pct, 2),
        'volume': volume
    }

# 2. 抓取法人資料
institutional = {}
for days_ago in range(7):
    target_date = datetime.now() - timedelta(days=days_ago)
    date_str = target_date.strftime('%Y%m%d')
    
    try:
        url_inst = "https://www.twse.com.tw/rwd/zh/fund/T86"
        params = {
            'date': date_str,
            'selectType': 'ALLBUT0999',
            'response': 'json'
        }
        
        response = requests.get(url_inst, params=params, timeout=15, verify=False)
        data = response.json()
        
        if data.get('stat') != 'OK' or not data.get('data'):
            continue
        
        for item in data['data']:
            try:
                ticker = item[0].strip()
                if not (ticker.isdigit() and len(ticker) == 4):
                    continue
                
                foreign = int(item[4].replace(',', '')) if item[4] != '--' else 0
                trust = int(item[10].replace(',', '')) if item[10] != '--' else 0
                
                institutional[ticker] = {
                    'foreign': foreign,
                    'trust': trust,
                    'total': foreign + trust
                }
            except:
                continue
        
        if institutional:
            inst_date = date_str
            break
    except:
        continue

# 3. 抓取本益比
pe_data = {}
try:
    url_pe = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
    response = requests.get(url_pe, timeout=15, verify=False)
    pe_list = response.json()
    
    for item in pe_list:
        ticker = item.get('Code', '').strip()
        pe_str = item.get('PEratio', '')
        if ticker and pe_str:
            try:
                pe_data[ticker] = float(pe_str)
            except:
                pass
except:
    pass

# 4. 篩選
results = []
for ticker, stock in stocks.items():
    if not (CONFIG['MIN_PRICE'] <= stock['price'] <= CONFIG['MAX_PRICE']):
        continue
    if stock['volume'] < CONFIG['MIN_VOLUME']:
        continue
    
    inst = institutional.get(ticker, {})
    total_inst = inst.get('total', 0)
    if total_inst <= 0:
        continue
    
    if not (0 <= stock['change_pct'] <= 5):
        continue
    
    pe = pe_data.get(ticker, 0)
    if pe > 30 or pe <= 0:
        continue
    
    results.append({
        'ticker': ticker,
        'name': stock['name'],
        'price': stock['price'],
        'change_pct': stock['change_pct'],
        'volume': stock['volume'],
        'foreign': inst.get('foreign', 0),
        'trust': inst.get('trust', 0),
        'total_inst': total_inst,
        'pe': pe
    })

results = sorted(results, key=lambda x: x['total_inst'], reverse=True)

# 輸出到檔案
with open('scan_result.txt', 'w', encoding='utf-8') as f:
    f.write('=' * 80 + '\n')
    f.write(f'篩選結果 - 法人買超({inst_date}) + 漲幅0-5% + PE<30 + 量>500張\n')
    f.write('=' * 80 + '\n\n')
    
    f.write(f"{'#':>3} {'代號':<6} {'名稱':<8} {'價格':>7} {'漲幅':>7} {'外資(張)':>12} {'投信(張)':>12} {'PE':>6}\n")
    f.write('-' * 80 + '\n')
    
    for i, r in enumerate(results[:30], 1):
        f.write(f"{i:>3} {r['ticker']:<6} {r['name']:<8} {r['price']:>7.1f} {r['change_pct']:>+6.2f}% {r['foreign']:>+12,} {r['trust']:>+12,} {r['pe']:>6.1f}\n")
    
    f.write('\n' + '=' * 80 + '\n')
    f.write(f'共 {len(results)} 檔符合條件\n')

print(f'Done! {len(results)} stocks. See scan_result.txt')
