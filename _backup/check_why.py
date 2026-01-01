#!/usr/bin/env python3
"""檢查為什麼緯創和長榮沒過"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from FinMind.data import DataLoader
from datetime import datetime, timedelta
import requests
import urllib3
import time
import logging

# 關閉 FinMind 的 INFO log
logging.getLogger('FinMind').setLevel(logging.WARNING)
urllib3.disable_warnings()

FINMIND_TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMS0wMSAxNTo1MzoyMCIsInVzZXJfaWQiOiJhdGl0aSIsImlwIjoiMTExLjI0My4xNDIuOTkifQ.NmNnOo6KP0bmvvdFQ68L6SM1DChuxrW7Z1P5onzPWlU'

dl = DataLoader()
dl.login_by_token(api_token=FINMIND_TOKEN)

# 股價資料
print("載入股價資料...")
url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
r = requests.get(url, timeout=15, verify=False)
stock_data = {item['Code']: item for item in r.json()}

# PE 資料
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

def check_stock(ticker, name):
    print(f"\n{'='*60}")
    print(f"{ticker} {name}")
    print('='*60)
    
    # 基本資料
    item = stock_data.get(ticker, {})
    if not item:
        print("找不到股票")
        return
    
    close = float(item.get('ClosingPrice', '0').replace(',', '') or 0)
    change_str = item.get('Change', '0').replace(',', '').replace('+', '')
    change = float(change_str) if change_str and change_str != 'X' else 0
    prev_close = close - change
    change_pct = (change / prev_close * 100) if prev_close > 0 else 0
    volume = int(item.get('TradeVolume', '0').replace(',', '') or 0) // 1000
    pe = pe_data.get(ticker, 0)
    
    print(f"股價: {close}, 漲幅: {change_pct:.2f}%, 成交量: {volume}張, PE: {pe}")
    
    # 條件檢查
    checks = []
    checks.append(("價格 30-300", 30 <= close <= 300, close))
    checks.append(("漲幅 0-5%", 0 <= change_pct <= 5, f"{change_pct:.2f}%"))
    checks.append(("成交量 >800張", volume > 800, f"{volume}張"))
    checks.append(("PE <35", 0 < pe < 35, pe))
    
    # 法人資料
    time.sleep(0.3)
    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=30)
    df = dl.taiwan_stock_institutional_investors(stock_id=ticker, start_date=start_date.strftime('%Y-%m-%d'), end_date=end_date.strftime('%Y-%m-%d'))
    
    ticker_data = {}
    for _, row in df.iterrows():
        date_str = str(row.get('date', '')).replace('-', '')
        name_col = str(row.get('name', '')).strip()
        buy = int(row.get('buy', 0))
        sell = int(row.get('sell', 0))
        net = (buy - sell) // 1000
        if date_str not in ticker_data:
            ticker_data[date_str] = {'date': date_str, 'total': 0}
        if 'Foreign_Investor' in name_col or 'Investment_Trust' in name_col:
            ticker_data[date_str]['total'] += net
    
    inst = sorted(ticker_data.values(), key=lambda x: x['date'], reverse=True)
    
    today_inst = inst[0]['total'] if inst else 0
    checks.append(("今日法人買超", today_inst > 0, f"{today_inst:+,}張"))
    
    buy_days = 0
    for r in inst:
        if r['total'] > 0:
            buy_days += 1
        else:
            break
    checks.append(("買超 2-7天", 2 <= buy_days <= 7, f"{buy_days}天"))
    
    inst_5day = sum(r['total'] for r in inst[:5])
    checks.append(("5日累積 >300張", inst_5day > 300, f"{inst_5day:+,}張"))
    
    inst_1month = sum(r['total'] for r in inst)
    checks.append(("1月累積 >-10000張", inst_1month > -10000, f"{inst_1month:+,}張"))
    
    # 歷史股價
    time.sleep(0.3)
    df_price = dl.taiwan_stock_daily(stock_id=ticker, start_date=(datetime.now() - timedelta(days=15)).strftime('%Y-%m-%d'), end_date=datetime.now().strftime('%Y-%m-%d'))
    prices = []
    for _, row in df_price.iterrows():
        prices.append((row['date'], float(row['close']), int(row['Trading_Volume']) // 1000))
    prices = sorted(prices, key=lambda x: x[0], reverse=True)
    
    if len(prices) >= 5:
        day5_change = ((prices[0][1] - prices[4][1]) / prices[4][1]) * 100
        checks.append(("5日漲幅 <10%", day5_change < 10, f"{day5_change:.2f}%"))
        
        avg_vol = sum(p[2] for p in prices[:5]) / 5
        checks.append(("今量 >5日均量", volume > avg_vol, f"{volume}/{avg_vol:.0f}"))
        
        closes = [p[1] for p in prices]
        ma = sum(closes) / len(closes)
        checks.append(("股價 >MA", close > ma, f"{close:.1f}/{ma:.1f}"))
    
    # 營收
    time.sleep(0.3)
    df_rev = dl.taiwan_stock_month_revenue(stock_id=ticker, start_date='2024-01-01', end_date='2025-12-31')
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
            checks.append(("營收 YoY >0%", yoy > 0, f"{yoy:.1f}%"))
    
    # 輸出結果
    print("\n條件檢查:")
    passed = 0
    failed = 0
    failed_items = []
    for check_name, result, value in checks:
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {check_name}: {value}")
        if result:
            passed += 1
        else:
            failed += 1
            failed_items.append(check_name)
    
    print(f"\n結果: {passed} 通過, {failed} 未通過")
    if failed == 0:
        print(">>> 符合所有條件!")
    else:
        print(f">>> 被刷掉原因: {', '.join(failed_items)}")

# 檢查三檔股票
print("\n" + "="*60)
print("股票條件檢查報告")
print("="*60)

check_stock('3231', '緯創')
check_stock('2603', '長榮')
check_stock('2376', '技嘉')
