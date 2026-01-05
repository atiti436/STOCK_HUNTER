#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v4.0 策略回測腳本

目標：驗證 v4.0 選股策略在 2024 年的表現

輸出：
- 總推薦次數
- 勝率（5日後漲 / 10日後漲）
- 平均報酬
- 最佳/最差案例

使用方式：
    python backtest_v4.py

注意：
    - 需要 FinMind API Token
    - 回測期間：2024-01-01 ~ 2024-12-31
    - 會花較長時間（預計 10-30 分鐘）
"""

import os
import json
import time
from datetime import datetime, timedelta
from collections import defaultdict

# ===== FinMind 設定 =====
FINMIND_TOKENS = [
    'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMS0wMSAxNTo1MzoyMCIsInVzZXJfaWQiOiJhdGl0aSIsImlwIjoiMTExLjI0My4xNDIuOTkifQ.NmNnOo6KP0bmvvdFQ68L6SM1DChuxrW7Z1P5onzPWlU',
    'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMS0wMSAwNTo1OToyMiIsInVzZXJfaWQiOiIxMjM0NTY3OG5hbiIsImlwIjoiMS4xNzIuMTEzLjMxIn0.wr0l3_dXhZKr33J5MVTE7_OdKJTILcOLmLIJaF-xLdE',
    'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMS0wMSAyMjowODo1OCIsInVzZXJfaWQiOiJ4aWFpIiwiaXAiOiIxMTEuMjQzLjE0Mi45OSJ9.-sWtQw0UY8FkMCR8Tg_Lp9kO-UkRhjLTqRrlDXXpk10',
]
CURRENT_TOKEN_INDEX = 0


def get_finmind_token():
    return FINMIND_TOKENS[CURRENT_TOKEN_INDEX]


def rotate_token():
    global CURRENT_TOKEN_INDEX
    CURRENT_TOKEN_INDEX = (CURRENT_TOKEN_INDEX + 1) % len(FINMIND_TOKENS)
    print(f'   🔄 切換 Token #{CURRENT_TOKEN_INDEX + 1}')


# ===== 工具函數 =====

def is_excluded_stock(ticker):
    """排除金融、營建、ETF"""
    if ticker.startswith('00'):  # ETF
        return True
    if ticker.startswith('28') or ticker.startswith('58'):  # 金融
        return True
    if ticker.startswith('25'):  # 營建
        return True
    return False


def calculate_rsi(prices, period=14):
    """計算 RSI"""
    if len(prices) < period + 1:
        return 50

    gains = []
    losses = []
    for i in range(period):
        change = prices[i] - prices[i + 1]  # 最新在前，所以是 [i] - [i+1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)


# ===== 資料抓取 =====

def fetch_stock_prices_twse(ticker, year, month):
    """
    用證交所 API 抓單一股票的月股價
    返回: [(date, open, close, volume), ...]
    """
    import requests
    
    date_str = f'{year}{month:02d}01'
    url = f'https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={date_str}&stockNo={ticker}'
    
    try:
        resp = requests.get(url, timeout=10, verify=False)
        data = resp.json()
        
        if data.get('stat') != 'OK' or 'data' not in data:
            return []
        
        results = []
        for row in data['data']:
            # row: ['114/01/02', '5,000', '100.0', '101.0', '99.0', '100.5', '+0.5', '3,000']
            try:
                # 日期格式: 114/01/02 -> 2025-01-02
                date_parts = row[0].split('/')
                y = int(date_parts[0]) + 1911
                m = int(date_parts[1])
                d = int(date_parts[2])
                date = f'{y}-{m:02d}-{d:02d}'
                
                volume = int(row[1].replace(',', '')) // 1000  # 轉成張
                open_price = float(row[3].replace(',', ''))
                close_price = float(row[6].replace(',', ''))
                
                results.append((date, open_price, close_price, volume))
            except:
                continue
        
        return results
    except:
        return []


def fetch_all_stock_prices(start_date, end_date):
    """
    用證交所 API 抓取股票歷史股價（改用 TWSE，無 API 限制）
    返回: {ticker: {date: {'open': x, 'close': x, 'volume': x}}}
    """
    import requests
    
    print(f'📊 抓取股價資料 {start_date} ~ {end_date}...', flush=True)
    print('   使用證交所 STOCK_DAY API（無次數限制，但較慢）', flush=True)
    
    # 先抓當日股票清單（用證交所 OpenAPI）
    stock_list = []
    try:
        url = 'https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL'
        resp = requests.get(url, timeout=15, verify=False)
        data = resp.json()
        
        for item in data:
            ticker = item.get('Code', '')
            if ticker.isdigit() and len(ticker) == 4 and not is_excluded_stock(ticker):
                stock_list.append(ticker)
        
        print(f'   股票數量: {len(stock_list)}')
    except Exception as e:
        print(f'   [!] 抓取股票清單失敗: {e}')
        return {}
    
    # 計算需要抓的月份
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    
    months = []
    current = start.replace(day=1)
    while current <= end:
        months.append((current.year, current.month))
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    
    print(f'   月份數: {len(months)}')
    
    # 不限制股票數量（完整回測）
    print(f'   使用全部 {len(stock_list)} 檔')
    
    # 逐檔逐月抓取
    all_prices = {}
    success = 0
    
    for i, ticker in enumerate(stock_list):
        ticker_data = {}
        
        for year, month in months:
            results = fetch_stock_prices_twse(ticker, year, month)
            for date, open_p, close_p, vol in results:
                ticker_data[date] = {
                    'open': open_p,
                    'close': close_p,
                    'volume': vol
                }
            time.sleep(0.3)  # 避免被擋
        
        if ticker_data:
            all_prices[ticker] = ticker_data
            success += 1
        
        if (i + 1) % 20 == 0:
            print(f'   進度: {i + 1}/{len(stock_list)} ({success} 成功)')
    
    print(f'   完成: {success}/{len(stock_list)} 股票')
    return all_prices


def fetch_all_institutional(start_date, end_date):
    """
    用證交所 T86 API 抓取法人買賣超（免費無限制！）
    返回: {ticker: {date: {'foreign': x, 'trust': x, 'total': x}}}
    """
    import requests
    
    print(f'📊 抓取法人資料 {start_date} ~ {end_date}...')
    print('   使用證交所 T86 API（免費無限制）')
    
    all_inst = defaultdict(dict)
    
    # 取得所有交易日
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    
    current = start
    success_days = 0
    total_days = 0
    
    while current <= end:
        date_str = current.strftime('%Y%m%d')
        
        url = f'https://www.twse.com.tw/fund/T86?response=json&date={date_str}&selectType=ALLBUT0999'
        
        try:
            resp = requests.get(url, timeout=15, verify=False)
            data = resp.json()
            
            if data.get('stat') == 'OK' and data.get('data'):
                for row in data['data']:
                    try:
                        ticker = row[0].strip()
                        if not (ticker.isdigit() and len(ticker) == 4):
                            continue
                        
                        # 解析法人買賣超（單位是股，要除以1000變成張）
                        # index 4: 外資買賣超
                        # index 10: 投信買賣超
                        # index 18: 三大法人買賣超
                        foreign = int(row[4].replace(',', '')) // 1000
                        trust = int(row[10].replace(',', '')) // 1000
                        total = int(row[18].replace(',', '')) // 1000
                        
                        date_formatted = current.strftime('%Y-%m-%d')
                        all_inst[ticker][date_formatted] = {
                            'foreign': foreign,
                            'trust': trust,
                            'total': total
                        }
                    except:
                        continue
                
                success_days += 1
                if success_days % 10 == 0:
                    print(f'   進度: {success_days} 交易日')
            
            total_days += 1
            time.sleep(0.3)  # 避免過快
            
        except Exception as e:
            if total_days % 10 == 0:
                print(f'   {date_str} 跳過: {e}')
        
        current += timedelta(days=1)
    
    print(f'   完成: {len(all_inst)} 股票, {success_days} 交易日')
    return dict(all_inst)


# ===== 回測邏輯 =====

def get_trading_days(prices_data, start_date, end_date):
    """取得有交易的日期清單"""
    all_dates = set()
    for ticker_data in prices_data.values():
        all_dates.update(ticker_data.keys())
    
    trading_days = sorted([d for d in all_dates 
                          if start_date <= d <= end_date])
    return trading_days


def simulate_v4_selection(date, prices_data, inst_data):
    """
    模擬某一天的 v4.0 選股
    返回符合條件的股票清單
    """
    recommendations = []
    
    for ticker, price_history in prices_data.items():
        if is_excluded_stock(ticker):
            continue
        
        # 取得那天的資料
        if date not in price_history:
            continue
        
        today_price = price_history[date]
        close = today_price['close']
        volume = today_price['volume']
        
        # 基本篩選
        if not (30 <= close <= 300):
            continue
        if volume < 800:
            continue
        
        # 取得過去 20 天的價格（計算 MA、RSI）
        sorted_dates = sorted(price_history.keys(), reverse=True)
        date_idx = sorted_dates.index(date) if date in sorted_dates else -1
        if date_idx < 0:
            continue
        
        past_20_dates = sorted_dates[date_idx:date_idx + 20]
        if len(past_20_dates) < 10:  # 至少需要 10 天資料
            continue
        
        past_closes = [price_history[d]['close'] for d in past_20_dates]
        past_volumes = [price_history[d]['volume'] for d in past_20_dates]
        
        # 計算技術指標
        ma20 = sum(past_closes[:20]) / len(past_closes[:20]) if len(past_closes) >= 5 else close
        ma10 = sum(past_closes[:10]) / len(past_closes[:10]) if len(past_closes) >= 10 else close
        avg_volume = sum(past_volumes[:5]) / min(5, len(past_volumes))
        
        # 計算 RSI
        rsi = calculate_rsi(past_closes, period=14) if len(past_closes) >= 15 else 50
        
        # 計算今日漲幅
        prev_close = past_closes[1] if len(past_closes) > 1 else close
        change_pct = (close - prev_close) / prev_close * 100 if prev_close > 0 else 0
        
        # 計算 5 日漲幅
        day5_close = past_closes[4] if len(past_closes) > 4 else close
        day5_change = (close - day5_close) / day5_close * 100 if day5_close > 0 else 0
        
        # v4.0 篩選條件
        if not (-2 <= change_pct <= 5):
            continue
        if day5_change >= 10:  # 5 日漲幅 < 10%
            continue
        if close < ma20:  # 股價 > MA20
            continue
        if rsi >= 80:  # RSI < 80
            continue
        if volume < avg_volume:  # 今日量 > 均量
            continue
        
        # 法人條件（使用證交所 T86 資料）
        ticker_inst = inst_data.get(ticker, {})
        inst_dates = sorted([d for d in ticker_inst.keys() if d <= date], reverse=True)[:7]
        
        # 必須有法人資料
        if not inst_dates:
            continue
        
        # 今日法人買超
        today_inst = ticker_inst.get(date, {})
        if today_inst.get('total', 0) <= 0:
            continue
        
        # 計算連續買超天數
        buy_days = 0
        for d in inst_dates:
            if ticker_inst[d].get('total', 0) > 0:
                buy_days += 1
            else:
                break
        
        # 連續買超 >= 2 天
        if buy_days < 2:
            continue
        
        # 5 日累積 >= 300 張
        inst_5day = sum(ticker_inst.get(d, {}).get('total', 0) for d in inst_dates[:5])
        if inst_5day < 300:
            continue
        
        # 通過所有條件，加入推薦
        recommendations.append({
            'ticker': ticker,
            'date': date,
            'price': close,
            'change_pct': round(change_pct, 2),
            'volume': volume,
            'buy_days': buy_days,
            'inst_5day': inst_5day,
            'rsi': rsi,
        })
    
    # 排序：優先法人買超，其次成交量
    recommendations = sorted(recommendations, key=lambda x: (x['inst_5day'], x['volume']), reverse=True)[:6]
    
    return recommendations


def calculate_returns(recommendations, prices_data):
    """
    計算每個推薦的報酬
    """
    results = []
    
    for rec in recommendations:
        ticker = rec['ticker']
        date = rec['date']
        entry_price = rec['price']
        
        ticker_prices = prices_data.get(ticker, {})
        sorted_dates = sorted(ticker_prices.keys())
        
        if date not in sorted_dates:
            continue
        
        date_idx = sorted_dates.index(date)
        
        # 5 日後價格
        day5_price = None
        if date_idx + 5 < len(sorted_dates):
            day5_date = sorted_dates[date_idx + 5]
            day5_price = ticker_prices[day5_date]['close']
        
        # 10 日後價格
        day10_price = None
        if date_idx + 10 < len(sorted_dates):
            day10_date = sorted_dates[date_idx + 10]
            day10_price = ticker_prices[day10_date]['close']
        
        # 計算報酬
        return_5d = ((day5_price - entry_price) / entry_price * 100) if day5_price else None
        return_10d = ((day10_price - entry_price) / entry_price * 100) if day10_price else None
        
        results.append({
            **rec,
            'return_5d': round(return_5d, 2) if return_5d else None,
            'return_10d': round(return_10d, 2) if return_10d else None,
            'win_5d': return_5d > 0 if return_5d else None,
            'win_10d': return_10d > 0 if return_10d else None,
        })
    
    return results


# ===== 報告產生 =====

def generate_report(all_results):
    """產生回測報告"""
    # 過濾有效結果
    valid_5d = [r for r in all_results if r['return_5d'] is not None]
    valid_10d = [r for r in all_results if r['return_10d'] is not None]
    
    # 計算統計
    total = len(all_results)
    
    win_5d = len([r for r in valid_5d if r['win_5d']])
    win_10d = len([r for r in valid_10d if r['win_10d']])
    
    win_rate_5d = (win_5d / len(valid_5d) * 100) if valid_5d else 0
    win_rate_10d = (win_10d / len(valid_10d) * 100) if valid_10d else 0
    
    avg_return_5d = sum(r['return_5d'] for r in valid_5d) / len(valid_5d) if valid_5d else 0
    avg_return_10d = sum(r['return_10d'] for r in valid_10d) / len(valid_10d) if valid_10d else 0
    
    # 最佳/最差案例
    best_5d = max(valid_5d, key=lambda x: x['return_5d']) if valid_5d else None
    worst_5d = min(valid_5d, key=lambda x: x['return_5d']) if valid_5d else None
    
    best_10d = max(valid_10d, key=lambda x: x['return_10d']) if valid_10d else None
    worst_10d = min(valid_10d, key=lambda x: x['return_10d']) if valid_10d else None
    
    # 產生報告
    report = {
        'period': '2025-01-01 ~ 2025-12-31',
        'total_recommendations': total,
        'stats_5d': {
            'valid_count': len(valid_5d),
            'wins': win_5d,
            'win_rate': round(win_rate_5d, 1),
            'avg_return': round(avg_return_5d, 2),
            'best': best_5d,
            'worst': worst_5d,
        },
        'stats_10d': {
            'valid_count': len(valid_10d),
            'wins': win_10d,
            'win_rate': round(win_rate_10d, 1),
            'avg_return': round(avg_return_10d, 2),
            'best': best_10d,
            'worst': worst_10d,
        },
        'all_results': all_results,
    }
    
    return report


def print_report(report):
    """印出報告"""
    print('\n' + '=' * 60)
    print('📊 v4.0 策略回測報告')
    print('=' * 60)
    print(f"回測期間: {report['period']}")
    print(f"總推薦次數: {report['total_recommendations']}")
    
    print('\n【5 日後報酬】')
    s5 = report['stats_5d']
    print(f"  有效樣本: {s5['valid_count']}")
    print(f"  勝率: {s5['win_rate']}% ({s5['wins']}/{s5['valid_count']})")
    print(f"  平均報酬: {s5['avg_return']:+.2f}%")
    if s5['best']:
        print(f"  最佳: {s5['best']['ticker']} {s5['best']['date']} +{s5['best']['return_5d']:.1f}%")
    if s5['worst']:
        print(f"  最差: {s5['worst']['ticker']} {s5['worst']['date']} {s5['worst']['return_5d']:.1f}%")
    
    print('\n【10 日後報酬】')
    s10 = report['stats_10d']
    print(f"  有效樣本: {s10['valid_count']}")
    print(f"  勝率: {s10['win_rate']}% ({s10['wins']}/{s10['valid_count']})")
    print(f"  平均報酬: {s10['avg_return']:+.2f}%")
    if s10['best']:
        print(f"  最佳: {s10['best']['ticker']} {s10['best']['date']} +{s10['best']['return_10d']:.1f}%")
    if s10['worst']:
        print(f"  最差: {s10['worst']['ticker']} {s10['worst']['date']} {s10['worst']['return_10d']:.1f}%")
    
    print('\n' + '=' * 60)
    
    # 判定
    if s5['win_rate'] >= 55 and s5['avg_return'] > 0:
        print('✅ 策略有效！5 日勝率 > 55% 且平均報酬為正')
    elif s10['win_rate'] >= 55 and s10['avg_return'] > 0:
        print('⚠️ 策略需優化：5 日不穩，但 10 日有效')
    else:
        print('❌ 策略需檢討：勝率或報酬不佳')


# ===== 主程式 =====

def main():
    print('=' * 60)
    print('v4.0 策略回測')
    print('=' * 60)
    
    start_date = '2025-01-01'
    end_date = '2025-12-31'
    
    # 檢查快取
    cache_dir = 'data/backtest_cache'
    os.makedirs(cache_dir, exist_ok=True)
    
    prices_cache = f'{cache_dir}/prices_2025.json'
    inst_cache = f'{cache_dir}/institutional_2025.json'
    
    # 抓取或載入股價資料
    if os.path.exists(prices_cache):
        print(f'📂 載入股價快取: {prices_cache}')
        with open(prices_cache, 'r') as f:
            prices_data = json.load(f)
    else:
        prices_data = fetch_all_stock_prices(start_date, end_date)
        with open(prices_cache, 'w') as f:
            json.dump(prices_data, f)
        print(f'💾 股價快取已存: {prices_cache}')
    
    # 抓取或載入法人資料
    if os.path.exists(inst_cache):
        print(f'📂 載入法人快取: {inst_cache}')
        with open(inst_cache, 'r') as f:
            inst_data = json.load(f)
    else:
        inst_data = fetch_all_institutional(start_date, end_date)
        with open(inst_cache, 'w') as f:
            json.dump(inst_data, f)
        print(f'💾 法人快取已存: {inst_cache}')
    
    # 取得交易日
    trading_days = get_trading_days(prices_data, start_date, end_date)
    print(f'\n📅 交易日數: {len(trading_days)}')
    
    # 模擬回測
    print('\n🔄 開始回測...')
    all_recommendations = []
    
    for i, date in enumerate(trading_days):
        recs = simulate_v4_selection(date, prices_data, inst_data)
        all_recommendations.extend(recs)
        
        if i % 20 == 0:
            print(f'   進度: {i}/{len(trading_days)} ({len(all_recommendations)} 推薦)')
    
    print(f'\n📊 總推薦數: {len(all_recommendations)}')
    
    # 計算報酬
    print('\n📈 計算報酬...')
    results = calculate_returns(all_recommendations, prices_data)
    
    # 產生報告
    report = generate_report(results)
    print_report(report)
    
    # 儲存結果
    result_file = f'{cache_dir}/backtest_result.json'
    with open(result_file, 'w', encoding='utf-8') as f:
        # 不儲存完整結果（太大），只存統計
        report_small = {k: v for k, v in report.items() if k != 'all_results'}
        report_small['sample_results'] = results[:50]  # 只存前 50 筆
        json.dump(report_small, f, ensure_ascii=False, indent=2)
    
    print(f'\n💾 結果已存: {result_file}')


if __name__ == '__main__':
    main()
