#!/usr/bin/env python3
"""檢查技嘉為什麼這次沒過"""
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import requests
import urllib3
urllib3.disable_warnings()

dl = DataLoader()

print("=== 技嘉 2376 完整檢查 ===\n")

# 1. 基本資料
url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
r = requests.get(url, timeout=15, verify=False)
stock_data = {item['Code']: item for item in r.json()}

item = stock_data.get('2376', {})
close = float(item.get('ClosingPrice', '0').replace(',', '') or 0)
change_str = item.get('Change', '0').replace(',', '').replace('+', '')
change = float(change_str) if change_str and change_str != 'X' else 0
prev_close = close - change
change_pct = (change / prev_close * 100) if prev_close > 0 else 0
volume = int(item.get('TradeVolume', '0').replace(',', '') or 0) // 1000

print(f"股價: {close}")
print(f"漲幅: {change_pct:.2f}%")
print(f"成交量: {volume} 張")

# 條件檢查
print(f"\n[條件檢查]")
print(f"1. 價格 30-300: {30 <= close <= 300} ({close})")
print(f"2. 漲幅 0-5%: {0 <= change_pct <= 5} ({change_pct:.2f}%)")
print(f"3. 成交量 >800: {volume > 800} ({volume})")

# PE
url = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
r = requests.get(url, timeout=15, verify=False)
pe_data = {}
for item in r.json():
    code = item.get('Code', '').strip()
    pe_str = item.get('PEratio', '')
    if code and pe_str:
        try:
            pe_data[code] = float(pe_str)
        except:
            pass

pe = pe_data.get('2376', 0)
print(f"4. PE <35: {0 < pe < 35} ({pe})")

# 法人
end_date = datetime.now() - timedelta(days=1)
start_date = end_date - timedelta(days=30)
df = dl.taiwan_stock_institutional_investors(stock_id='2376', start_date=start_date.strftime('%Y-%m-%d'), end_date=end_date.strftime('%Y-%m-%d'))

ticker_data = {}
for _, row in df.iterrows():
    date_str = str(row.get('date', '')).replace('-', '')
    name = str(row.get('name', '')).strip()
    buy = int(row.get('buy', 0))
    sell = int(row.get('sell', 0))
    net = (buy - sell) // 1000
    if date_str not in ticker_data:
        ticker_data[date_str] = {'date': date_str, 'f': 0, 't': 0, 'total': 0}
    if 'Foreign_Investor' in name:
        ticker_data[date_str]['f'] += net
    elif 'Investment_Trust' in name:
        ticker_data[date_str]['t'] += net
    ticker_data[date_str]['total'] = ticker_data[date_str]['f'] + ticker_data[date_str]['t']

inst = sorted(ticker_data.values(), key=lambda x: x['date'], reverse=True)

today_inst = inst[0]['total'] if inst else 0
print(f"5. 今日法人買超: {today_inst > 0} ({today_inst:+,})")

buy_days = 0
for r in inst:
    if r['total'] > 0:
        buy_days += 1
    else:
        break
print(f"6. 買超 2-7天: {2 <= buy_days <= 7} ({buy_days}天)")

inst_5day = sum(r['total'] for r in inst[:5])
print(f"7. 5日累積 >300: {inst_5day > 300} ({inst_5day:+,})")

inst_1month = sum(r['total'] for r in inst)
print(f"8. 1月累積 >-10000: {inst_1month > -10000} ({inst_1month:+,})")

# 歷史股價
df_price = dl.taiwan_stock_daily(stock_id='2376', start_date=(datetime.now() - timedelta(days=15)).strftime('%Y-%m-%d'), end_date=datetime.now().strftime('%Y-%m-%d'))
prices = []
for _, row in df_price.iterrows():
    prices.append((row['date'], float(row['close']), int(row['Trading_Volume']) // 1000))
prices = sorted(prices, key=lambda x: x[0], reverse=True)

if len(prices) >= 5:
    day5_change = ((prices[0][1] - prices[4][1]) / prices[4][1]) * 100
    print(f"9. 5日漲幅 <10%: {day5_change < 10} ({day5_change:.2f}%)")
    
    avg_vol = sum(p[2] for p in prices[:5]) / 5
    print(f"10. 今量 >5日均量: {volume > avg_vol} ({volume}/{avg_vol:.0f})")
    
    closes = [p[1] for p in prices]
    ma = sum(closes) / len(closes)
    print(f"11. 股價 >MA: {close > ma} ({close}/{ma:.1f})")

# 營收
df_rev = dl.taiwan_stock_month_revenue(stock_id='2376', start_date='2024-01-01', end_date='2025-12-31')
if not df_rev.empty and len(df_rev) >= 13:
    df_rev = df_rev.sort_values('date')
    latest = df_rev.iloc[-1]
    latest_revenue = latest['revenue']
    latest_month = latest['revenue_month']
    latest_year = latest['revenue_year']
    
    year_ago = df_rev[(df_rev['revenue_month'] == latest_month) & (df_rev['revenue_year'] == latest_year - 1)]
    if not year_ago.empty:
        year_ago_revenue = year_ago.iloc[0]['revenue']
        yoy = ((latest_revenue - year_ago_revenue) / year_ago_revenue) * 100 if year_ago_revenue > 0 else 0
        print(f"12. 營收 YoY >0%: {yoy > 0} ({yoy:.1f}%)")
