#!/usr/bin/env python3
"""簡化篩選測試 - 不含法人資料"""

import requests
import urllib3
urllib3.disable_warnings()

# 1. 抓股價
url = 'https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL'
r = requests.get(url, timeout=15, verify=False)
data = r.json()

# 2. 抓 PE
url_pe = 'https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL'
r_pe = requests.get(url_pe, timeout=15, verify=False)
pe_data = {item['Code']: float(item['PEratio']) for item in r_pe.json() if item.get('PEratio')}

# 3. 篩選 (不含法人)
results = []
for item in data:
    ticker = item.get('Code', '')
    if not (ticker.isdigit() and len(ticker) == 4):
        continue
    if ticker.startswith('28') or ticker.startswith('58') or ticker.startswith('25') or ticker.startswith('00'):
        continue
    
    try:
        close = float(item.get('ClosingPrice', '0').replace(',', '') or 0)
        change_str = item.get('Change', '0').replace(',', '').replace('+', '')
        change = float(change_str) if change_str and change_str != 'X' else 0
        prev = close - change
        pct = (change / prev * 100) if prev > 0 else 0
        volume = int(item.get('TradeVolume', '0').replace(',', '') or 0) // 1000
    except:
        continue
    
    if close <= 0 or volume <= 0:
        continue
    
    pe = pe_data.get(ticker, 0)
    
    # v3.2 基本面條件 (不含法人)
    if 30 <= close <= 300 and 0 <= pct <= 5 and volume >= 800 and 0 < pe < 35:
        results.append({
            'ticker': ticker,
            'name': item.get('Name', ''),
            'price': close,
            'pct': pct,
            'volume': volume,
            'pe': pe
        })

print(f'基本面篩選 (不含法人): {len(results)} 檔')
print('-' * 50)
for r in results[:15]:
    print(f"{r['ticker']} {r['name'][:6]:6} {r['price']:>7.1f} {r['pct']:>+5.1f}% PE={r['pe']:.1f} 量={r['volume']}")
if len(results) > 15:
    print(f'... 還有 {len(results) - 15} 檔')
