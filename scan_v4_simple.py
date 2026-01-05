#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
選股條件 v4 Simple - 最簡化保險版本
目標：找「法人有在買、趨勢向上、還沒過熱」的股票

簡化策略：
- ✅ For 迴圈逐檔抓（最保險）
- ✅ 法人只抓 5 天（夠判斷趨勢）
- ✅ 每個 API 都 print 原始資料（方便 debug）
- ✅ 一定能跑完，不會超時

篩選條件：
【基本面】價格 30-300、PE<35、營收YoY>0%
【技術面】漲幅-2%~5%、5日漲幅<10%、量>均量、價>MA、RSI<80
【籌碼面】法人連買>=2天、5日累積>300張、日量>800張
"""

import os
import requests
import urllib3
from datetime import datetime, timedelta
import json
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# FinMind Tokens
FINMIND_TOKENS = [
    'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMS0wMyAwMDoxODoyNSIsInVzZXJfaWQiOiJhdGl0aSIsImlwIjoiMTExLjI0My4xNDIuOTkifQ.0AoJDWaK-mWt1OhdyL6JdOI5TOkSpNEe-tDoI34aHjI',
    'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMS0wMSAyMjowNTozNSIsInVzZXJfaWQiOiJhdGl0aTQzNiIsImlwIjoiMTExLjI0My4xNDIuOTkifQ.ejONnKY_3b9tqA7wh47d2r5yfUKCFWybdNSkrJp3C10',
    'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMS0wMSAyMjowODo1OCIsInVzZXJfaWQiOiJ4aWFpIiwiaXAiOiIxMTEuMjQzLjE0Mi45OSJ9.-sWtQw0UY8FkMCR8Tg_Lp9kO-UkRhjLTqRrlDXXpk10',
]
CURRENT_TOKEN_INDEX = 0

def get_finmind_token():
    global CURRENT_TOKEN_INDEX
    return FINMIND_TOKENS[CURRENT_TOKEN_INDEX % len(FINMIND_TOKENS)]

def rotate_token():
    global CURRENT_TOKEN_INDEX
    CURRENT_TOKEN_INDEX += 1
    token_num = CURRENT_TOKEN_INDEX % len(FINMIND_TOKENS) + 1
    print(f'[TOKEN] 切換到 Token #{token_num}')
    return get_finmind_token()

def is_excluded_stock(ticker):
    if ticker.startswith('28') or ticker.startswith('58'):  # 金融
        return True
    if ticker.startswith('25'):  # 營建
        return True
    if ticker.startswith('00'):  # ETF
        return True
    return False

def calculate_rsi(prices, period=14):
    """計算 RSI"""
    if len(prices) < period + 1:
        return 50
    prices = list(reversed(prices[:period + 1]))
    gains, losses = [], []
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 1)

def calculate_stop_loss(close_price, ma10, ma20):
    """動態停損"""
    if not ma10 or not ma20:
        return close_price * 0.93, '-7% 硬停損'
    deviation = ((close_price - ma20) / ma20) * 100
    if deviation > 5:
        stop_loss = ma10
        note = f'守MA10 (噴出股, 乖離{deviation:.1f}%)'
    else:
        stop_loss = ma20
        note = f'守MA20 (起漲股, 乖離{deviation:.1f}%)'
    hard_stop = close_price * 0.93
    if stop_loss < hard_stop:
        stop_loss = hard_stop
        note = '-7% 硬停損'
    return round(stop_loss, 1), note

# ===== 步驟1：批量抓股價 =====
def fetch_all_stocks():
    from FinMind.data import DataLoader
    dl = DataLoader()
    dl.login_by_token(api_token=get_finmind_token())

    print('[1/6] 批量抓股價...')
    today = datetime.now().strftime('%Y-%m-%d')
    print(f'   目標日期: {today}')

    df = dl.taiwan_stock_daily(start_date=today, end_date=today)
    if df is None or df.empty:
        print('   今日無資料，試昨天...')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        df = dl.taiwan_stock_daily(start_date=yesterday, end_date=yesterday)

    print(f'   抓到 {len(df)} 筆')
    print(f'   [DEBUG] 前3筆preview:')
    for i in range(min(3, len(df))):
        row = df.iloc[i]
        print(f'      {row.get("stock_id")} {row.get("close")} {row.get("Trading_turnover")}')

    stocks = {}
    for _, row in df.iterrows():
        ticker = str(row.get('stock_id', '')).strip()
        if not (ticker.isdigit() and len(ticker) == 4):
            continue
        if is_excluded_stock(ticker):
            continue
        try:
            close = float(row.get('close', 0))
            open_price = float(row.get('open', 0))
            volume = int(row.get('Trading_turnover', 0))
            if close > 0 and open_price > 0:
                change_pct = ((close - open_price) / open_price) * 100
            else:
                change_pct = 0
            if not (30 <= close <= 300):
                continue
            if not (-2 <= change_pct <= 5):
                continue
            if volume < 800:
                continue
            stocks[ticker] = {
                'name': '',
                'price': close,
                'change_pct': round(change_pct, 2),
                'volume': volume
            }
        except:
            continue
    print(f'   篩選後: {len(stocks)} 檔')
    return stocks

# ===== 步驟2：PE 篩選 =====
def fetch_pe_ratios(stocks):
    print('[2/6] 抓 PE 本益比...')
    url = 'https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d?date='
    date_str = datetime.now().strftime('%Y%m%d')
    try:
        resp = requests.get(url + date_str, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10, verify=False)
        data = resp.json()
        pe_data = {}
        stock_names = {}
        for item in data.get('data', []):
            ticker = str(item[0]).strip()
            name = str(item[1]).strip()
            pe_str = str(item[5]).strip()
            stock_names[ticker] = name
            if pe_str == '-' or pe_str == 'N/A':
                continue
            try:
                pe = float(pe_str.replace(',', ''))
                if 0 < pe < 35:
                    pe_data[ticker] = pe
            except:
                continue
        print(f'   PE<35: {len(pe_data)} 檔')
        print(f'   [DEBUG] 前3檔PE:')
        for i, (t, p) in enumerate(list(pe_data.items())[:3]):
            print(f'      {t} PE={p}')
        for ticker in stocks:
            if ticker in stock_names:
                stocks[ticker]['name'] = stock_names[ticker]
        return pe_data
    except Exception as e:
        print(f'   錯誤: {e}')
        return {}

# ===== 步驟3：法人（FOR 迴圈，5天）=====
def fetch_institutional_simple(tickers):
    from FinMind.data import DataLoader
    print(f'[3/6] 逐檔抓法人（{len(tickers)} 檔，每檔5天）...')
    dl = DataLoader()
    dl.login_by_token(api_token=get_finmind_token())
    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=7)
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')
    print(f'   日期: {start_str} ~ {end_str}')

    institutional = {}
    success, fail = 0, 0
    for i, ticker in enumerate(tickers, 1):
        try:
            print(f'   [{i}/{len(tickers)}] {ticker} ...', end=' ', flush=True)
            df = dl.taiwan_stock_institutional_investors(
                stock_id=ticker, start_date=start_str, end_date=end_str)
            if df is None or df.empty:
                print('空')
                fail += 1
                continue
            print(f'{len(df)}天', end='')
            if i <= 3:
                print(f' [DEBUG: {df.iloc[0].to_dict()}]', end='')
            records = []
            for _, row in df.sort_values('date', ascending=False).iterrows():
                foreign = int(row.get('Foreign_Investor_diff', 0)) / 1000
                trust = int(row.get('Investment_Trust_diff', 0)) / 1000
                total = foreign + trust
                records.append({
                    'date': str(row.get('date', '')),
                    'foreign': round(foreign),
                    'trust': round(trust),
                    'total': round(total)
                })
            institutional[ticker] = records[:5]
            success += 1
            print()
            time.sleep(0.1)
        except Exception as e:
            print(f'錯: {e}')
            fail += 1
            if 'Limit' in str(e) or '429' in str(e):
                rotate_token()
                dl.login_by_token(api_token=get_finmind_token())
                time.sleep(2)
    print(f'   成功{success} 失敗{fail}')
    return institutional

# ===== 步驟4：歷史股價（FOR 迴圈）=====
def fetch_historical_simple(tickers):
    from FinMind.data import DataLoader
    print(f'[4/6] 逐檔抓歷史股價（{len(tickers)} 檔，每檔10天）...')
    dl = DataLoader()
    dl.login_by_token(api_token=get_finmind_token())
    end_date = datetime.now()
    start_date = end_date - timedelta(days=15)
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')
    print(f'   日期: {start_str} ~ {end_str}')

    historical = {}
    success, fail = 0, 0
    for i, ticker in enumerate(tickers, 1):
        try:
            print(f'   [{i}/{len(tickers)}] {ticker} ...', end=' ', flush=True)
            df = dl.taiwan_stock_daily(stock_id=ticker, start_date=start_str, end_date=end_str)
            if df is None or df.empty:
                print('空')
                fail += 1
                continue
            print(f'{len(df)}天', end='')
            if i <= 3:
                print(f' [DEBUG: close={df.iloc[0].get("close")}]', end='')
            prices = []
            for _, row in df.sort_values('date', ascending=False).iterrows():
                close = float(row.get('close', 0))
                volume = int(row.get('Trading_turnover', 0))
                if close > 0:
                    prices.append((str(row.get('date', '')), close, volume))
            if len(prices) >= 5:
                closes = [p[1] for p in prices]
                volumes = [p[2] for p in prices]
                ma10 = sum(closes[:10]) / 10 if len(closes) >= 10 else None
                ma20 = sum(closes[:20]) / 20 if len(closes) >= 20 else (sum(closes) / len(closes) if closes else None)
                day5_change = ((closes[0] - closes[4]) / closes[4] * 100) if len(closes) >= 5 else 0
                avg_volume = sum(volumes[:5]) / 5 if len(volumes) >= 5 else 0
                rsi = calculate_rsi(closes)
                historical[ticker] = {
                    'prices': prices[:10],
                    'ma10': ma10,
                    'ma20': ma20,
                    '5day_change': round(day5_change, 2),
                    '5day_avg_volume': round(avg_volume),
                    'rsi': rsi
                }
                success += 1
            else:
                fail += 1
            print()
            time.sleep(0.1)
        except Exception as e:
            print(f'錯: {e}')
            fail += 1
            if 'Limit' in str(e) or '429' in str(e):
                rotate_token()
                dl.login_by_token(api_token=get_finmind_token())
                time.sleep(2)
    print(f'   成功{success} 失敗{fail}')
    return historical

# ===== 步驟5：營收（FOR 迴圈）=====
def fetch_revenue_simple(tickers):
    from FinMind.data import DataLoader
    print(f'[5/6] 逐檔抓營收（{len(tickers)} 檔）...')
    dl = DataLoader()
    dl.login_by_token(api_token=get_finmind_token())
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')

    revenue = {}
    success, fail = 0, 0
    for i, ticker in enumerate(tickers, 1):
        try:
            print(f'   [{i}/{len(tickers)}] {ticker} ...', end=' ', flush=True)
            df = dl.taiwan_stock_month_revenue(stock_id=ticker, start_date=start_str, end_date=end_str)
            if df is None or df.empty:
                print('空')
                fail += 1
                continue
            df_sorted = df.sort_values('revenue_month', ascending=False)
            latest = df_sorted.iloc[0]
            yoy = float(latest.get('revenue_year_on_year', 0))
            print(f'YoY={yoy:.1f}%', end='')
            if i <= 3:
                print(f' [DEBUG: {latest.get("revenue_month")}]', end='')
            revenue[ticker] = {'yoy': round(yoy, 2)}
            success += 1
            print()
            time.sleep(0.1)
        except Exception as e:
            print(f'錯: {e}')
            fail += 1
            if 'Limit' in str(e) or '429' in str(e):
                rotate_token()
                dl.login_by_token(api_token=get_finmind_token())
                time.sleep(2)
    print(f'   成功{success} 失敗{fail}')
    return revenue

# ===== 步驟6：財報（FOR 迴圈）=====
def fetch_financials_simple(tickers):
    from FinMind.data import DataLoader
    print(f'[6/6] 逐檔抓財報（{len(tickers)} 檔）...')
    dl = DataLoader()
    dl.login_by_token(api_token=get_finmind_token())
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')

    financials = {}
    success, fail = 0, 0
    for i, ticker in enumerate(tickers, 1):
        try:
            print(f'   [{i}/{len(tickers)}] {ticker} ...', end=' ', flush=True)
            df = dl.taiwan_stock_financial_statement(stock_id=ticker, start_date=start_str, end_date=end_str)
            if df is None or df.empty:
                print('空')
                fail += 1
                continue
            df_sorted = df.sort_values('date', ascending=False)
            latest = df_sorted.iloc[0]
            revenue = float(latest.get('revenue', 0))
            gross_profit = float(latest.get('gross_profit', 0))
            operating_income = float(latest.get('operating_income', 0))
            gross_margin = (gross_profit / revenue * 100) if revenue > 0 else 0
            operating_margin = (operating_income / revenue * 100) if revenue > 0 else 0
            print(f'毛利={gross_margin:.1f}%', end='')
            if i <= 3:
                print(f' [DEBUG: rev={revenue}]', end='')
            financials[ticker] = {
                'gross_margin': round(gross_margin, 2),
                'operating_margin': round(operating_margin, 2)
            }
            success += 1
            print()
            time.sleep(0.1)
        except Exception as e:
            print(f'錯: {e}')
            fail += 1
            if 'Limit' in str(e) or '429' in str(e):
                rotate_token()
                dl.login_by_token(api_token=get_finmind_token())
                time.sleep(2)
    print(f'   成功{success} 失敗{fail}')
    return financials

# ===== 篩選與評分 =====
def filter_and_rank(stocks, pe_data, institutional, historical, revenue, financials):
    print('\n篩選候選股...')
    candidate_tickers = set(stocks.keys()) & set(pe_data.keys())
    print(f'  PE 篩選後: {len(candidate_tickers)} 檔')

    results = []
    for ticker in candidate_tickers:
        stock = stocks[ticker]
        inst = institutional.get(ticker, [])
        hist = historical.get(ticker, {})
        rev = revenue.get(ticker, {})
        fin = financials.get(ticker, {})

        if not inst or not hist:
            continue

        # 籌碼面
        inst_5day = sum(r['total'] for r in inst[:5])
        buy_days = 0
        for r in inst[:5]:
            if r['total'] > 0:
                buy_days += 1
            else:
                break
        if buy_days < 2 or inst_5day < 300:
            continue

        # 技術面
        day5_change = hist.get('5day_change', 0)
        avg_volume = hist.get('5day_avg_volume', 0)
        ma10 = hist.get('ma10')
        ma20 = hist.get('ma20')
        rsi = hist.get('rsi', 50)
        if day5_change >= 10 or stock['volume'] <= avg_volume:
            continue
        if ma20 and stock['price'] < ma20:
            continue
        if rsi >= 80:
            continue

        # 營收
        rev_yoy = rev.get('yoy', -999)
        if rev_yoy <= 0:
            continue

        # 通過！
        stop_loss, stop_note = calculate_stop_loss(stock['price'], ma10, ma20)
        results.append({
            'ticker': ticker,
            'name': stock['name'],
            'price': stock['price'],
            'change_pct': stock['change_pct'],
            'pe': pe_data[ticker],
            'inst_5day': inst_5day,
            'buy_days': buy_days,
            'rsi': rsi,
            'revenue_yoy': rev_yoy,
            'stop_loss': stop_loss,
            'stop_note': stop_note,
            'score': buy_days * 10 + (inst_5day / 100)
        })

    results = sorted(results, key=lambda x: x['score'], reverse=True)
    print(f'\n最終通過: {len(results)} 檔')
    return results

# ===== 儲存結果 =====
def save_results(results):
    today = datetime.now().strftime('%Y-%m-%d')
    history_dir = 'data/history'
    os.makedirs(history_dir, exist_ok=True)

    history_entry = {
        'date': today,
        'timestamp': datetime.now().isoformat(),
        'count': len(results),
        'stocks': [
            {
                'ticker': r['ticker'],
                'name': r['name'],
                'price': r['price'],
                'change_pct': r['change_pct'],
                'pe': r['pe'],
                'inst_5day': r['inst_5day'],
                'revenue_yoy': r['revenue_yoy'],
                'rsi': r['rsi'],
                'stop_loss': r['stop_loss'],
                'score': r['score']
            } for r in results
        ]
    }

    daily_file = f'{history_dir}/{today}.json'
    with open(daily_file, 'w', encoding='utf-8') as f:
        json.dump(history_entry, f, ensure_ascii=False, indent=2)
    print(f'✅ 已存: {daily_file}')

# ===== 主程式 =====
def main():
    print('='*80)
    print('選股程式 v4 Simple - 最保險版本')
    print('='*80)

    stocks = fetch_all_stocks()
    if not stocks:
        print('[ERROR] 無股票資料')
        return

    pe_data = fetch_pe_ratios(stocks)
    candidate_tickers = list(set(stocks.keys()) & set(pe_data.keys()))
    print(f'\n候選股: {len(candidate_tickers)} 檔')
    if not candidate_tickers:
        print('[ERROR] 無候選股')
        return

    institutional = fetch_institutional_simple(candidate_tickers)
    historical = fetch_historical_simple(candidate_tickers)
    revenue = fetch_revenue_simple(candidate_tickers)
    financials = fetch_financials_simple(candidate_tickers)

    results = filter_and_rank(stocks, pe_data, institutional, historical, revenue, financials)
    save_results(results)

    print('\n' + '='*80)
    print(f'推薦股票 TOP {min(10, len(results))}')
    print('='*80)
    for i, r in enumerate(results[:10], 1):
        print(f'{i}. {r["ticker"]} {r["name"]} ${r["price"]} ({r["change_pct"]:+.2f}%)')
        print(f'   PE={r["pe"]:.1f} | 法人5日={r["inst_5day"]}張 | RSI={r["rsi"]} | 營收YoY={r["revenue_yoy"]:.1f}%')
        print(f'   停損: {r["stop_loss"]} ({r["stop_note"]})')

if __name__ == '__main__':
    main()
