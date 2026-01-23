#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
選股條件 v5.4 篩選器 (投信加權版)
目標：找「法人有在買、籌碼乾淨、趨勢向上」的股票

篩選條件:

【基本面】
- 價格 90-300 元
- PE < 35

【技術面】
- 5日漲幅 < 15%
- 股價 > MA20
- RSI < 85

【籌碼面】
- 法人連續買超 >= 2 天
- 法人5日累積 > 300 張
- 法人1月累積 > -10,000 張

【v5.2 Bonus 加分】
- 融資3日減 + 法人買 → +1 [資減]
- 融券3日增 → +1 [軋空]
- 營收 YoY > 0% → +1

【v5.3 均線標籤】
- MA5 > MA10 → [多頭]

【v5.4 投信加權】🆕
- 投信今日買超 > 0 → +1 [投信]
- 投信連買 >= 2 天 → +1
- 投信買超 > 外資買超 → [土洋對作]

輸出說明:
- 只輸出 >= 3 分股票
- 適合當沖/隔日沖，最長 5 天
"""

import os
import requests
import urllib3
from datetime import datetime, timedelta
import json
import time
import argparse

# 解析命令列參數
parser = argparse.ArgumentParser(description='選股條件 v5.2 (融資券 + YoY)')
parser.add_argument('--offline', action='store_true', help='使用本地快取，不呼叫 API')
parser.add_argument('--date', type=str, help='指定日期 (YYYY-MM-DD)，用於查詢歷史資料。預設=今天')
ARGS = parser.parse_args()

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Backer 付費版 Token (1600 次/hr)
FINMIND_TOKENS = [
    'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMS0wNSAyMzowODozMSIsInVzZXJfaWQiOiJhdGl0aSIsImVtYWlsIjoiYXRpdGk0MzYxQGdtYWlsLmNvbSIsImlwIjoiMTExLjI0My4xNDIuOTkifQ.MEcPu8FHrrY2ES1j26NRO9Dg9E2ekEhM4B5rlCPidSI',
]
CURRENT_TOKEN_INDEX = 0

def get_finmind_token():
    """取得當前 FinMind Token (支援輪替)"""
    global CURRENT_TOKEN_INDEX
    return FINMIND_TOKENS[CURRENT_TOKEN_INDEX % len(FINMIND_TOKENS)]

def rotate_token():
    """切換到下一個 Token (當達到 rate limit 時使用)"""
    global CURRENT_TOKEN_INDEX
    CURRENT_TOKEN_INDEX += 1
    token_num = CURRENT_TOKEN_INDEX % len(FINMIND_TOKENS) + 1
    print(f'[TOKEN] 切換到 Token #{token_num}')
    return get_finmind_token()

# ===== 工具函數 =====

def is_excluded_stock(ticker):
    """判斷是否為排除的股票類型"""
    if ticker.startswith('28') or ticker.startswith('58'):  # 金融股
        return True
    if ticker.startswith('25'):  # 營建股
        return True
    if ticker.startswith('00'):  # ETF
        return True
    return False


def calculate_rsi(prices, period=14):
    """
    計算 RSI (相對強弱指標)
    
    參數:
        prices: 收盤價列表 (最新在前)，例如 [100, 99, 101, ...]
        period: RSI 週期，預設 14
    
    返回:
        RSI 值 (0-100)，如果資料不足返回 50 (中性)
    """
    if len(prices) < period + 1:
        return 50  # 資料不足，返回中性值
    
    # 反轉讓舊的在前
    prices = list(reversed(prices[:period + 1]))
    
    gains = []
    losses = []
    
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
        return 100  # 沒有跌過，RSI = 100
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return round(rsi, 1)


def calculate_kd(prices, period=9):
    """
    計算標準 KD(9,3,3) 指標 - V9 MVP

    標準公式:
        RSV(t) = (Close(t) - Low9) / (High9 - Low9) * 100
        K(t) = (2/3) * K(t-1) + (1/3) * RSV(t)
        D(t) = (2/3) * D(t-1) + (1/3) * K(t)

    參數:
        prices: 價格列表 [(date, close, volume, high, low), ...] 最新在前
        period: RSV 週期，預設 9

    返回:
        dict {
            'K_value': float,    # 今日 K 值
            'D_value': float,    # 今日 D 值
            'K_prev': float,     # 昨日 K 值 (用於判斷金叉)
            'D_prev': float,     # 昨日 D 值 (用於判斷金叉)
        }
        或 None 如果資料不足
    """
    # 需要至少 period + 1 天資料 (今天 + 昨天 + period-1 天歷史)
    if len(prices) < period + 1:
        return None

    # 反轉數據，讓舊的在前（方便迭代計算）
    prices_reversed = list(reversed(prices[:period + 10]))  # 多取一些確保計算穩定

    # 初始化 K, D
    k = 50.0
    d = 50.0
    k_prev = 50.0
    d_prev = 50.0

    # 從第 period 天開始計算（前 period-1 天用來計算第一個 RSV）
    for i in range(period - 1, len(prices_reversed)):
        # 取最近 period 天的資料（包含今天）
        window = prices_reversed[i - period + 1 : i + 1]

        # 今日收盤價
        close_today = window[-1][1]

        # period 天內的最高價和最低價
        highs = [p[3] if len(p) >= 4 else p[1] for p in window]
        lows = [p[4] if len(p) >= 5 else p[1] for p in window]

        high_9 = max(highs)
        low_9 = min(lows)

        # 計算 RSV
        if high_9 == low_9:
            rsv = 50.0  # 避免除以零
        else:
            rsv = (close_today - low_9) / (high_9 - low_9) * 100

        # 保存前一天的 K, D
        k_prev = k
        d_prev = d

        # 計算今日 K: K = (2/3) * K_prev + (1/3) * RSV
        k = (2.0 / 3.0) * k_prev + (1.0 / 3.0) * rsv

        # 計算今日 D: D = (2/3) * D_prev + (1/3) * K
        d = (2.0 / 3.0) * d_prev + (1.0 / 3.0) * k

    return {
        'K_value': round(k, 2),
        'D_value': round(d, 2),
        'K_prev': round(k_prev, 2),
        'D_prev': round(d_prev, 2),
    }


def calculate_atr(prices, period=14):
    """
    計算 ATR (Average True Range) - v5.1 新增
    
    參數:
        prices: 價格列表 [(date, close, volume, high, low), ...] 最新在前
        period: ATR 週期，預設 14
    
    返回:
        (atr_value, atr_percent, stock_type)
        - atr_value: ATR 絕對值
        - atr_percent: ATR 佔股價百分比
        - stock_type: '兔子' (活潑) 或 '烏龜' (牛皮)
    """
    if len(prices) < period + 1:
        # 資料不足，用簡化計算
        if len(prices) >= 2:
            # 用 high-low 平均
            ranges = []
            for p in prices[:min(len(prices), period)]:
                if len(p) >= 5:  # 有 high, low
                    ranges.append(p[3] - p[4])  # high - low
                else:
                    ranges.append(abs(p[1] * 0.02))  # 預設 2%
            atr = sum(ranges) / len(ranges) if ranges else prices[0][1] * 0.02
        else:
            atr = prices[0][1] * 0.02  # 預設 2%
    else:
        # 標準 ATR 計算
        true_ranges = []
        for i in range(period):
            if len(prices[i]) >= 5 and len(prices[i+1]) >= 5:
                high = prices[i][3]
                low = prices[i][4]
                prev_close = prices[i+1][1]
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            else:
                tr = abs(prices[i][1] - prices[i+1][1])
            true_ranges.append(tr)
        atr = sum(true_ranges) / len(true_ranges)
    
    current_price = prices[0][1]
    atr_pct = (atr / current_price * 100) if current_price > 0 else 2
    
    # 判斷股票類型
    if atr_pct > 2.5:
        stock_type = '兔子'  # 活潑
    elif atr_pct < 1.5:
        stock_type = '烏龜'  # 牛皮
    else:
        stock_type = '普通'
    
    return round(atr, 2), round(atr_pct, 2), stock_type


def calculate_stop_loss_atr(close_price, atr):
    """
    v5.1 ATR 通道法停損停利
    
    返回: (stop_loss, t1, t2, note)
    - stop_loss: 成本 - 2×ATR
    - t1: 成本 + 2×ATR (先賣一半)
    - t2: 成本 + 4×ATR (趨勢滿足)
    """
    if atr <= 0:
        atr = close_price * 0.02  # 預設 2%
    
    stop_loss = round(close_price - 2 * atr, 1)
    t1 = round(close_price + 2 * atr, 1)
    t2 = round(close_price + 4 * atr, 1)
    
    stop_pct = (stop_loss - close_price) / close_price * 100
    note = f"2xATR ({stop_pct:+.1f}%)"
    
    return stop_loss, t1, t2, note

def fetch_historical_prices(ticker, days=10):
    """
    抓取歷史股價（用於計算 5 日漲幅、5 日均量、ATR）
    使用 FinMind API (比證交所穩定)
    返回: [(date, close, volume, high, low), ...]，最新的在前面 (v5.1 加入 high/low)
    """
    max_retries = len(FINMIND_TOKENS)

    for attempt in range(max_retries):
        try:
            from FinMind.data import DataLoader
            dl = DataLoader()
            dl.login_by_token(api_token=get_finmind_token())

            # 計算日期範圍
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days+5)  # 多抓幾天避免假日

            start_str = start_date.strftime('%Y-%m-%d')
            end_str = end_date.strftime('%Y-%m-%d')

            # 使用 FinMind 抓歷史股價
            df = dl.taiwan_stock_daily(
                stock_id=ticker,
                start_date=start_str,
                end_date=end_str
            )

            if df is None or df.empty:
                return []

            prices = []
            for _, row in df.iterrows():
                try:
                    date_str = str(row.get('date', '')).replace('-', '')  # 2025-12-30 → 20251230
                    close = float(row.get('close', 0))
                    volume = int(row.get('Trading_Volume', 0)) // 1000  # 轉成張
                    high = float(row.get('max', close))  # v5.1: 加入最高價
                    low = float(row.get('min', close))   # v5.1: 加入最低價

                    if close > 0 and volume > 0:
                        prices.append((date_str, close, volume, high, low))
                except:
                    continue

            # 只取最近 N 天，新的在前
            return sorted(prices, key=lambda x: x[0], reverse=True)[:days]

        except ImportError:
            print(f'   [{ticker}] FinMind 未安裝')
            return []
        except Exception as e:
            if attempt < max_retries - 1:
                rotate_token()
                continue
            else:
                print(f'   [{ticker}] 歷史股價抓取失敗（已重試 {max_retries} 次）: {e}')
                return []

    return []


def fetch_institutional_history_for_stocks(tickers, days=7):
    """
    逐檔抓取法人買賣超 (v3.2 修正版 + TOKEN 輪替)
    改成逐檔抓取，避免 FinMind 免費版 API 限制

    參數:
        tickers: 股票代號清單 ['2330', '2603', ...]
        days: 查詢天數

    返回: {ticker: [{date, foreign, trust, total}, ...]}
    """
    try:
        from FinMind.data import DataLoader
        import time
    except ImportError:
        print('   [!] FinMind 未安裝，無法抓取法人資料')
        HEALTH_CHECK['errors'].append("FinMind 未安裝")
        return {}

    # 計算日期範圍
    end_date = datetime.now() - timedelta(days=1)  # 昨天
    start_date = end_date - timedelta(days=days)

    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')

    print(f'   法人資料範圍: {start_str} ~ {end_str}')
    print(f'   逐檔抓取 {len(tickers)} 檔法人資料...')

    result = {}
    success_count = 0
    retry_count = 0
    max_retries = len(FINMIND_TOKENS)

    for i, ticker in enumerate(tickers, 1):
        fetched = False

        for attempt in range(max_retries):
            try:
                dl = DataLoader()
                dl.login_by_token(api_token=get_finmind_token())

                # 逐檔抓取
                df = dl.taiwan_stock_institutional_investors(
                    stock_id=ticker,
                    start_date=start_str,
                    end_date=end_str
                )

                if df is None or df.empty:
                    fetched = True
                    break

                # 整理該檔股票的法人資料
                ticker_data = {}

                for _, row in df.iterrows():
                    date_str = str(row.get('date', '')).replace('-', '')
                    name = str(row.get('name', '')).strip()
                    buy = int(row.get('buy', 0))
                    sell = int(row.get('sell', 0))
                    net = (buy - sell) // 1000  # 轉成張

                    if not date_str:
                        continue

                    if date_str not in ticker_data:
                        ticker_data[date_str] = {
                            'date': date_str,
                            'foreign': 0,
                            'trust': 0,
                            'total': 0
                        }

                    # 累加外資和投信
                    if 'Foreign_Investor' in name:
                        ticker_data[date_str]['foreign'] += net
                    elif 'Investment_Trust' in name:
                        ticker_data[date_str]['trust'] += net

                    ticker_data[date_str]['total'] = (
                        ticker_data[date_str]['foreign'] +
                        ticker_data[date_str]['trust']
                    )

                # 轉成 list 並排序
                if ticker_data:
                    result[ticker] = sorted(
                        ticker_data.values(),
                        key=lambda x: x['date'],
                        reverse=True
                    )
                    success_count += 1

                fetched = True
                break

            except Exception as e:
                if attempt < max_retries - 1:
                    rotate_token()
                    retry_count += 1
                    time.sleep(0.3)
                    continue
                else:
                    if i <= 3:  # 只顯示前 3 筆錯誤
                        print(f'      [{ticker}] 法人失敗（已重試 {max_retries} 次）: {e}')
                    if len(HEALTH_CHECK['errors']) < 3:
                        HEALTH_CHECK['errors'].append(f"法人API: {str(e)[:50]}")
                    break

        # 進度顯示 + 避免被擋
        if i % 20 == 0:
            print(f'      法人進度: {i}/{len(tickers)} ({success_count} 成功, {retry_count} 重試)')
            time.sleep(0.5)

    HEALTH_CHECK['inst_success'] = success_count
    HEALTH_CHECK['inst_total'] = len(tickers)
    print(f'   取得 {success_count}/{len(tickers)} 檔法人資料 (共重試 {retry_count} 次)')
    return result


def fetch_financial_data():
    """
    抓取財報資料（毛利率、營業利益率）
    使用 FinMind API (含 TOKEN 輪替)
    返回: {ticker: {'gross_margin': 毛利率, 'operating_margin': 營業利益率}}
    """
    max_retries = len(FINMIND_TOKENS)

    for attempt in range(max_retries):
        try:
            from FinMind.data import DataLoader
            dl = DataLoader()
            dl.login_by_token(api_token=get_finmind_token())

            # 抓取最新一季財報
            today = datetime.now()
            # 計算最近的季度 (Q3 2024)
            year = 2024
            quarter = 3

            print(f'   目標季度: {year}Q{quarter}')

            # 抓取所有上市公司財報
            df = dl.taiwan_stock_financial_statement(
                stock_id='',  # 空字串代表全部
                start_date=f'{year}Q{quarter}'
            )

            if df is None or df.empty:
                print('   [!] FinMind 財報資料為空')
                return {}

            financial_data = {}

            for _, row in df.iterrows():
                ticker = str(row.get('stock_id', '')).strip()
                if not ticker:
                    continue

                try:
                    # 毛利率 = 毛利 / 營收
                    revenue = float(row.get('revenue', 0))
                    gross_profit = float(row.get('gross_profit', 0))
                    operating_income = float(row.get('operating_income', 0))

                    if revenue == 0:
                        continue

                    gross_margin = (gross_profit / revenue) * 100
                    operating_margin = (operating_income / revenue) * 100

                    financial_data[ticker] = {
                        'gross_margin': round(gross_margin, 2),
                        'operating_margin': round(operating_margin, 2)
                    }
                except:
                    continue

            print(f'   取得 {len(financial_data)} 檔財報資料')
            return financial_data

        except ImportError:
            print('   [!] FinMind 未安裝，跳過財報檢查')
            return {}
        except Exception as e:
            if attempt < max_retries - 1:
                rotate_token()
                continue
            else:
                print(f'   [!] 財報抓取失敗（已重試 {max_retries} 次）: {e}')
                return {}

    return {}


def calculate_5day_change(prices):
    """計算近 5 日累積漲幅

    返回: 漲幅百分比 或 None (資料不足)
    """
    if len(prices) < 5:
        return None  # 資料不足，回傳 None

    latest = prices[0][1]  # 最新收盤
    day5_ago = prices[4][1]  # 5 天前收盤

    if day5_ago == 0:
        return None  # 避免除以零

    return ((latest - day5_ago) / day5_ago) * 100


def calculate_5day_avg_volume(prices):
    """計算 5 日均量

    返回: 均量 或 None (資料不足)
    """
    if len(prices) < 5:
        return None  # 資料不足，回傳 None

    volumes = [p[2] for p in prices[:5]]
    return sum(volumes) / len(volumes)


def count_institutional_buy_days(inst_history):
    """計算法人連續買超天數"""
    if not inst_history:
        return 0

    count = 0
    for record in inst_history:
        if record['total'] > 0:
            count += 1
        else:
            break  # 一旦不是買超就停止

    return count


def analyze_institutional_leader(inst_history):
    """
    分析主力是誰 (投信 vs 外資)

    參數:
        inst_history: 法人歷史資料 [{date, foreign, trust, total}, ...]

    返回: '投信' or '外資' or '混合' or '無'
    """
    if not inst_history or len(inst_history) < 5:
        return '無'

    # 看最近 5 日的累積
    recent_5 = inst_history[:5]

    foreign_total = sum(r['foreign'] for r in recent_5)
    trust_total = sum(r['trust'] for r in recent_5)

    if trust_total <= 0 and foreign_total <= 0:
        return '無'

    # 判斷主力
    if trust_total > foreign_total * 1.5:  # 投信明顯較多
        return '投信'
    elif foreign_total > trust_total * 1.5:  # 外資明顯較多
        return '外資'
    else:
        return '混合'


def fetch_revenue_data(tickers):
    """
    抓取營收資料並計算 YoY (v5.2: 修正空窗期 fallback)
    
    解法：批量 API 一次只回傳一個月份
    所以要呼叫兩次：今年最近月 + 去年同月
    
    空窗期處理 (Gemini 建議)：
    - 1-10號若無當月資料，自動 fallback 到上個月

    參數:
        tickers: 股票代號清單 ['2330', '2603', ...]

    返回: {ticker: {'yoy': YoY成長率, 'latest_month': 最新月份}}
    """
    try:
        from FinMind.data import DataLoader
    except ImportError:
        print('   [!] FinMind 未安裝，無法抓取營收資料')
        HEALTH_CHECK['errors'].append("FinMind 未安裝")
        return {}

    tickers_set = set(tickers)
    
    print(f'   [v5.2] 批量抓取營收（今年+去年，2 次 API）...')

    try:
        dl = DataLoader()
        dl.login_by_token(api_token=get_finmind_token())

        # 1. 抓最近一個月的全市場營收
        today = datetime.now()
        df_latest = dl.taiwan_stock_month_revenue(start_date=today.strftime('%Y-%m-%d'))
        
        # Fallback: 如果今天沒資料，嘗試上個月
        if df_latest is None or df_latest.empty:
            last_month = today.replace(day=1) - timedelta(days=1)
            print(f'   [INFO] 今年無資料，fallback 到 {last_month.strftime("%Y-%m")}')
            df_latest = dl.taiwan_stock_month_revenue(start_date=last_month.strftime('%Y-%m-%d'))
        
        if df_latest is None or df_latest.empty:
            print('   [WARN] 無法取得營收資料')
            return {}
        
        # 找出最新營收月份
        latest_year = int(df_latest['revenue_year'].max())
        latest_month = int(df_latest[df_latest['revenue_year'] == latest_year]['revenue_month'].max())
        print(f'   最新營收月份: {latest_year}/{latest_month}')
        
        # 2. 抓去年同月的全市場營收
        # 關鍵修正：用「最新營收月份 - 1 年」而非「今天 - 1 年」
        year_ago_year = latest_year - 1
        # 構造去年同月的查詢日期
        year_ago_date = datetime(year_ago_year, latest_month, 15)  # 用15號確保是那個月
        df_year_ago = dl.taiwan_stock_month_revenue(start_date=year_ago_date.strftime('%Y-%m-%d'))
        
        if df_year_ago is None or df_year_ago.empty:
            print(f'   [WARN] 無法取得 {year_ago_year}/{latest_month} 營收資料')
            return {}
        
        print(f'   今年資料: {len(df_latest)} 筆, 去年資料: {len(df_year_ago)} 筆')

        # 3. 合併並計算 YoY
        result = {}
        success_count = 0

        for ticker in tickers_set:
            # 今年營收
            ticker_latest = df_latest[
                (df_latest['stock_id'] == ticker) & 
                (df_latest['revenue_year'] == latest_year) & 
                (df_latest['revenue_month'] == latest_month)
            ]
            
            if ticker_latest.empty:
                continue
            
            latest_rev = float(ticker_latest.iloc[0]['revenue'])
            if latest_rev == 0:
                continue
            
            # 去年同月營收
            ticker_year_ago = df_year_ago[
                (df_year_ago['stock_id'] == ticker) & 
                (df_year_ago['revenue_year'] == year_ago_year) & 
                (df_year_ago['revenue_month'] == latest_month)
            ]
            
            if ticker_year_ago.empty:
                continue
            
            year_ago_rev = float(ticker_year_ago.iloc[0]['revenue'])
            if year_ago_rev == 0:
                continue
            
            yoy = ((latest_rev - year_ago_rev) / year_ago_rev) * 100

            result[ticker] = {
                'yoy': round(yoy, 2),
                'latest_month': f'{latest_year}/{latest_month:02d}'
            }
            success_count += 1

        HEALTH_CHECK['revenue_success'] = success_count
        HEALTH_CHECK['revenue_total'] = len(tickers)
        print(f'   取得 {success_count}/{len(tickers)} 檔營收 YoY')
        return result

    except Exception as e:
        print(f'   [ERROR] 營收抓取失敗: {e}')
        HEALTH_CHECK['errors'].append(f"營收API: {str(e)[:50]}")
        return {}


def fetch_margin_data(tickers, days=5):
    """
    v5.2 新增：逐檔抓取融資融券資料並計算 3日變化
    
    注意：融資券 API 不支援批量 (stock_id="")，必須逐檔抓取
    
    參數:
        tickers: 股票代號清單 ['2330', '2603', ...]
        days: 查詢天數 (多抓幾天確保有 3 個交易日)
    
    返回: {ticker: {
        'margin_3day_change': 融資3日增減 (張),
        'short_3day_change': 融券3日增減 (張),
        'margin_today': 今日融資餘額,
        'short_today': 今日融券餘額,
        'is_margin_decrease': True/False (融資3日減),
        'is_short_increase': True/False (融券3日增)
    }}
    """
    try:
        from FinMind.data import DataLoader
    except ImportError:
        print('   [!] FinMind 未安裝，無法抓取融資融券資料')
        HEALTH_CHECK['errors'].append("FinMind 未安裝")
        return {}

    tickers_set = set(tickers)
    
    print(f'   [v5.2] 逐檔抓取融資融券資料 ({len(tickers)} 檔)...')

    try:
        dl = DataLoader()
        dl.login_by_token(api_token=get_finmind_token())

        # 計算日期範圍
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 5)  # 多抓幾天避免假日

        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')

        print(f'   融資券查詢範圍: {start_str} ~ {end_str}')

        result = {}
        success_count = 0

        # 逐檔抓取 (融資券 API 不支援批量)
        for i, ticker in enumerate(tickers_set, 1):
            try:
                df = dl.taiwan_stock_margin_purchase_short_sale(
                    stock_id=ticker,
                    start_date=start_str,
                    end_date=end_str
                )

                if df is None or df.empty:
                    continue

                # 排序：最新日期在前
                df = df.sort_values('date', ascending=False)

                # 取最近 4 天資料 (今日 + 3日前)
                if len(df) < 4:
                    continue  # 資料不足

                # 融資餘額 (MarginPurchaseTodayBalance)
                # 融券餘額 (ShortSaleTodayBalance)
                margin_today = int(df.iloc[0].get('MarginPurchaseTodayBalance', 0))
                margin_3day_ago = int(df.iloc[3].get('MarginPurchaseTodayBalance', 0))
                short_today = int(df.iloc[0].get('ShortSaleTodayBalance', 0))
                short_3day_ago = int(df.iloc[3].get('ShortSaleTodayBalance', 0))

                margin_3day_change = margin_today - margin_3day_ago
                short_3day_change = short_today - short_3day_ago

                result[ticker] = {
                    'margin_3day_change': margin_3day_change,
                    'short_3day_change': short_3day_change,
                    'margin_today': margin_today,
                    'short_today': short_today,
                    'is_margin_decrease': margin_3day_change < 0,  # 融資減
                    'is_short_increase': short_3day_change > 0,    # 融券增
                }
                success_count += 1

            except Exception as e:
                if i <= 3:  # 只顯示前 3 筆錯誤
                    print(f'      [{ticker}] 融資券失敗: {e}')
                continue

            # 進度顯示
            if i % 20 == 0:
                print(f'      融資券進度: {i}/{len(tickers_set)} ({success_count} 成功)')
                time.sleep(0.3)  # 避免被擋

        print(f'   取得 {success_count}/{len(tickers)} 檔融資券資料')
        HEALTH_CHECK['margin_success'] = success_count
        HEALTH_CHECK['margin_total'] = len(tickers)
        return result

    except Exception as e:
        print(f'   [ERROR] 融資券抓取失敗: {e}')
        HEALTH_CHECK['errors'].append(f"融資券API: {str(e)[:50]}")
        return {}


# ===== 主程式 =====

# 健康檢查記錄
HEALTH_CHECK = {
    'stock_count': 0,       # 證交所股票數量
    'pe_count': 0,          # PE 資料數量
    'inst_success': 0,      # 法人資料成功數
    'inst_total': 0,        # 法人資料總數
    'price_success': 0,     # 歷史股價成功數
    'price_total': 0,       # 歷史股價總數
    'revenue_success': 0,   # 營收資料成功數
    'revenue_total': 0,     # 營收資料總數
    'margin_success': 0,    # v5.2: 融資券資料成功數
    'margin_total': 0,      # v5.2: 融資券資料總數
    'warnings': [],         # 警告訊息
    'errors': [],           # API 錯誤訊息
    'data_date': '',        # 資料日期
}

def check_data_health():
    """檢查資料健康狀態，回傳警告訊息"""
    warnings = []
    
    # 加入 API 錯誤
    if HEALTH_CHECK['errors']:
        for err in HEALTH_CHECK['errors'][:3]:  # 最多顯示 3 個錯誤
            warnings.append(f"API錯誤: {err}")
    
    # 檢查證交所資料
    if HEALTH_CHECK['stock_count'] == 0:
        warnings.append("證交所 API 無資料（可能被擋或假日）")
    elif HEALTH_CHECK['stock_count'] < 50:
        warnings.append(f"證交所資料極少 ({HEALTH_CHECK['stock_count']}檔)，可能 API 異常")
    
    # 檢查 PE 資料
    if HEALTH_CHECK['pe_count'] == 0:
        warnings.append("PE API 無資料")
    elif HEALTH_CHECK['pe_count'] < 500:
        warnings.append(f"PE 資料異常少 ({HEALTH_CHECK['pe_count']}檔)")
    
    # 檢查法人資料成功率
    if HEALTH_CHECK['inst_total'] > 0:
        inst_rate = HEALTH_CHECK['inst_success'] / HEALTH_CHECK['inst_total'] * 100
        if inst_rate < 50:
            warnings.append(f"法人資料大量失敗 ({inst_rate:.0f}%)，FinMind 可能達上限")
        elif inst_rate < 80:
            warnings.append(f"法人資料成功率過低 ({inst_rate:.0f}%)")
    
    # 檢查歷史股價成功率
    if HEALTH_CHECK['price_total'] > 0:
        price_rate = HEALTH_CHECK['price_success'] / HEALTH_CHECK['price_total'] * 100
        if price_rate < 50:
            warnings.append(f"股價資料大量失敗 ({price_rate:.0f}%)，FinMind 可能達上限")
        elif price_rate < 80:
            warnings.append(f"歷史股價成功率過低 ({price_rate:.0f}%)")
    
    # 檢查營收資料成功率
    if HEALTH_CHECK['revenue_total'] > 0:
        rev_rate = HEALTH_CHECK['revenue_success'] / HEALTH_CHECK['revenue_total'] * 100
        if rev_rate < 30:
            warnings.append(f"營收資料大量失敗 ({rev_rate:.0f}%)，FinMind 可能達上限")
        elif rev_rate < 50:
            warnings.append(f"營收資料成功率過低 ({rev_rate:.0f}%)")
    
    HEALTH_CHECK['warnings'] = warnings
    return warnings

def main():
    print('=' * 80)
    print('選股條件 v5.2 - 融資券+YoY版 (法人買、散戶走、有軋空潛力)')
    print('=' * 80)

    # === Offline 模式：直接讀取快取 ===
    if ARGS.offline:
        print('\n[OFFLINE] 使用本地快取，不呼叫 API')
        print('=' * 80)

        history_dir = 'data/history'
        if not os.path.exists(history_dir):
            print('[ERROR] data/history/ 目錄不存在')
            return

        # 找最新的 json 檔案
        json_files = [f for f in os.listdir(history_dir)
                      if f.endswith('.json') and f != 'all_history.json']
        if not json_files:
            print('[ERROR] data/history/ 沒有資料檔案')
            return

        latest_file = sorted(json_files)[-1]
        cache_path = os.path.join(history_dir, latest_file)

        with open(cache_path, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)

        data_date = cache_data.get('date', '未知')
        stock_count = cache_data.get('count', 0)

        print(f'[DATA] 資料日期: {data_date}')
        print(f'[COUNT] 股票數量: {stock_count} 檔')
        print('=' * 80)

        # 直接輸出結果
        results = cache_data.get('stocks', [])
        output_results(results)
        print(f'\n[OK] 從快取載入: {len(results)} 檔 (0 API 呼叫)')
        return

    # 1. 抓取當日股價 (使用 FinMind 批量 API)
    print('\n[1/5] 抓取當日股價 (FinMind)...')
    
    from FinMind.data import DataLoader
    dl = DataLoader()
    dl.login_by_token(api_token=get_finmind_token())
    
    # 批量抓取：使用指定日期或今天
    if ARGS.date:
        target_date_str = ARGS.date
        print(f'   指定日期: {target_date_str}')
    else:
        target_date_str = datetime.now().strftime('%Y-%m-%d')
        print(f'   查詢日期: {target_date_str}')
    
    # 抓取資料
    df = dl.taiwan_stock_daily(start_date=target_date_str)
    
    if df is None or df.empty:
        # 嘗試往前一天
        target_date = datetime.strptime(target_date_str, '%Y-%m-%d')
        yesterday_str = (target_date - timedelta(days=1)).strftime('%Y-%m-%d')
        print(f'   {target_date_str} 無資料，嘗試 {yesterday_str}...')
        df = dl.taiwan_stock_daily(start_date=yesterday_str)
    
    if df is None or df.empty:
        print('   [ERROR] FinMind 無資料')
        return
    
    # 找最新交易日
    latest_date = df['date'].max()
    HEALTH_CHECK['data_date'] = str(latest_date)
    print(f'   最新交易日: {latest_date}')
    
    # 只取最新交易日的資料
    df_latest = df[df['date'] == latest_date]
    
    # === 存 raw data（篩選前）===
    raw_dir = 'data/raw'
    os.makedirs(raw_dir, exist_ok=True)
    run_time = datetime.now().strftime('%H%M')
    
    # 儲存全市場收盤價（供 V7 驗證用）
    all_market_prices = {}
    for _, row in df_latest.iterrows():
        ticker = str(row.get('stock_id', '')).strip()
        if not (ticker.isdigit() and len(ticker) == 4):
            continue
        try:
            all_market_prices[ticker] = {
                'close': float(row.get('close', 0)),
                'open': float(row.get('open', 0)),
                'high': float(row.get('max', 0)),
                'low': float(row.get('min', 0)),
                'spread': float(row.get('spread', 0)),
                'volume': int(row.get('Trading_Volume', 0)) // 1000,
            }
        except:
            continue
    
    print(f'   [RAW] 全市場 {len(all_market_prices)} 檔收盤價（將存入 candidates.json）')
    
    # 用 spread 計算漲跌幅（spread = 今收 - 昨收）
    stocks = {}
    for _, row in df_latest.iterrows():
        ticker = str(row.get('stock_id', '')).strip()
        if not (ticker.isdigit() and len(ticker) == 4):
            continue
        if is_excluded_stock(ticker):
            continue

        try:
            close = float(row.get('close', 0))
            spread = float(row.get('spread', 0))  # 漲跌金額
            prev_close = close - spread
            change_pct = (spread / prev_close * 100) if prev_close > 0 else 0
            volume = int(row.get('Trading_Volume', 0)) // 1000  # 轉成張
        except:
            continue

        if close <= 0:
            continue

        # 基本篩選 (v3.5 調整)
        if not (90 <= close <= 300):  # 價格 90-300 (避開低價股)
            continue
        if not (-2 <= change_pct <= 5):  # v3.3: 容許小回檔 -2% ~ 5%
            continue
        if volume < 800:  # 日成交量 > 800 張 (新增)
            continue

        stocks[ticker] = {
            'name': '',  # FinMind 沒給名稱，後面從 PE API 補
            'price': close,
            'change_pct': round(change_pct, 2),
            'volume': volume
        }

    HEALTH_CHECK['stock_count'] = len(stocks)
    print(f'   基本篩選後: {len(stocks)} 檔')

    # 2. 抓取本益比 + 第二階段篩選
    print('\n[2/5] 抓取本益比...')
    pe_data = {}
    stock_names = {}  # 順便抓股票名稱
    try:
        url_pe = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
        response = requests.get(url_pe, timeout=15, verify=False)
        pe_list = response.json()

        for item in pe_list:
            ticker = item.get('Code', '').strip()
            name = item.get('Name', '').strip()
            pe_str = item.get('PEratio', '')
            if ticker:
                stock_names[ticker] = name
                if pe_str:
                    try:
                        pe_data[ticker] = float(pe_str)
                    except:
                        pass
        HEALTH_CHECK['pe_count'] = len(pe_data)
        print(f'   取得 {len(pe_data)} 檔 PE 資料')
        
        # 補充股票名稱
        for ticker in stocks:
            if ticker in stock_names:
                stocks[ticker]['name'] = stock_names[ticker]
    except:
        print('   PE 抓取失敗')

    # 2.5 用 PE 再篩選一次，準備給法人查詢用
    print('   用 PE < 35 再篩選... (v3.2 放寬)')
    candidate_tickers = []
    for ticker in stocks.keys():
        pe = pe_data.get(ticker, 0)
        if pe > 0 and pe < 35:  # v3.2: 放寬到 35
            candidate_tickers.append(ticker)

    print(f'   PE 篩選後: {len(candidate_tickers)} 檔 (準備查法人)')

    # 3. 逐檔抓取法人買賣超 (改成 30 天用於計算 1 月累積)
    print('\n[3/5] 抓取法人買賣超...')
    institutional = fetch_institutional_history_for_stocks(candidate_tickers, days=30)

    # 4. 抓取歷史股價（計算 5 日漲幅、均量）
    print('\n[4/5] 計算歷史技術指標...')
    print('   (這會花一點時間，請稍候...)')

    historical_data = {}
    count = 0
    for ticker in candidate_tickers:  # 改用 candidate_tickers (已經過 PE 篩選)
        prices = fetch_historical_prices(ticker, days=20)  # v3.3: 改成 20 天支援 RSI14
        if prices:
            day5_change = calculate_5day_change(prices)
            avg_volume = calculate_5day_avg_volume(prices)

            # 只有資料完整才儲存 (避免 None 導致後續錯誤)
            if day5_change is not None and avg_volume is not None:
                historical_data[ticker] = {
                    'prices': prices,
                    '5day_change': day5_change,
                    '5day_avg_volume': avg_volume
                }
                count += 1
                if count % 10 == 0:
                    print(f'   已處理 {count} 檔...')
                    time.sleep(2)  # 避免被擋

    print(f'   取得 {len(historical_data)} 檔歷史資料 (資料完整)')

    # 5. 抓取財報（毛利率、營業利益率）
    print('\n[5/8] 抓取財報資料...')
    print('   (暫時跳過財報檢查,避免 API 問題)')
    financial_data = {}  # TODO: 修正 FinMind API 後啟用
    # financial_data = fetch_financial_data()

    # 6. 抓取營收資料（計算 YoY）- v5.2 啟用
    print('\n[6/8] 抓取營收 YoY...')
    revenue_data = fetch_revenue_data(candidate_tickers)

    # 7. v5.2 新增：抓取融資融券資料
    print('\n[7/8] 抓取融資融券資料 [v5.2]...')
    margin_data = fetch_margin_data(candidate_tickers)

    # === 存完整候選資料 (篩選前) - 供離線版本比較用 ===
    print('\n[7.5/8] 存完整候選資料 (篩選前)...')
    candidates_full = []
    for ticker in candidate_tickers:
        stock = stocks.get(ticker)
        if not stock:
            continue
        
        pe = pe_data.get(ticker, 0)
        inst = institutional.get(ticker, [])
        hist = historical_data.get(ticker, {})
        rev = revenue_data.get(ticker, {})
        margin = margin_data.get(ticker, {})
        
        # 計算基本指標
        inst_5day = sum(r['total'] for r in inst[:5]) if inst else 0
        inst_1month = sum(r['total'] for r in inst) if inst else 0
        buy_days = count_institutional_buy_days(inst)
        inst_leader = analyze_institutional_leader(inst)
        
        day5_change = hist.get('5day_change', 0)
        avg_volume = hist.get('5day_avg_volume', 0)
        prices_list = hist.get('prices', [])
        
        # MA 計算
        closes = [p[1] for p in prices_list] if prices_list else []
        ma5 = sum(closes[:5]) / 5 if len(closes) >= 5 else None
        ma10 = sum(closes[:10]) / 10 if len(closes) >= 10 else None
        ma20 = sum(closes[:20]) / 20 if len(closes) >= 20 else (sum(closes) / len(closes) if closes else 0)
        
        # RSI
        rsi = 50
        if len(prices_list) >= 15:
            closes_for_rsi = [p[1] for p in prices_list]
            rsi = calculate_rsi(closes_for_rsi, period=14)
        
        # KD (V9 MVP 新增)
        kd_data = None
        k9, d9 = None, None
        if len(prices_list) >= 10:  # 需要至少 9+1 天資料
            kd_data = calculate_kd(prices_list, period=9)
            if kd_data:
                k9 = kd_data['K_value']
                d9 = kd_data['D_value']
        
        # ATR
        atr_value, atr_pct, stock_type = calculate_atr(prices_list, period=14) if prices_list else (0, 0, '普通')

        # 投信數據 (v5.4)
        trust_5day = sum(r['trust'] for r in inst[:5]) if len(inst) >= 5 else sum(r['trust'] for r in inst) if inst else 0
        foreign_5day = sum(r['foreign'] for r in inst[:5]) if len(inst) >= 5 else sum(r['foreign'] for r in inst) if inst else 0
        trust_today = inst[0]['trust'] if inst else 0

        # 計算投信連買天數
        trust_buy_days = 0
        for record in inst:
            if record['trust'] > 0:
                trust_buy_days += 1
            else:
                break

        # K_zone 判斷 (V9 MVP)
        k_zone = None
        k_prev, d_prev = None, None
        if kd_data:
            k_val = kd_data['K_value']
            k_prev = kd_data['K_prev']
            d_prev = kd_data['D_prev']
            if k_val >= 80:
                k_zone = 'Risky'  # 排除
            elif k_val <= 50:
                k_zone = 'Ideal'
            else:
                k_zone = 'OK'

        candidates_full.append({
            'ticker': ticker,
            'name': stock.get('name', ''),
            'price': stock['price'],
            'change_pct': stock['change_pct'],
            'volume': stock['volume'],
            'pe': pe,
            'inst_5day': inst_5day,
            'inst_1month': inst_1month,
            'buy_days': buy_days,
            'inst_leader': inst_leader,
            '5day_change': round(day5_change, 2) if day5_change else 0,
            'avg_volume': int(avg_volume) if avg_volume else 0,
            'revenue_yoy': rev.get('yoy', 0),
            'rsi': round(rsi, 1),
            'k9': k9,
            'd9': d9,
            'K_value': k9,  # V9 MVP
            'D_value': d9,  # V9 MVP
            'K_prev': k_prev,  # V9 MVP
            'D_prev': d_prev,  # V9 MVP
            'K_zone': k_zone,  # V9 MVP
            'ma5': round(ma5, 2) if ma5 else None,
            'ma10': round(ma10, 2) if ma10 else None,
            'ma20': round(ma20, 2) if ma20 else None,
            'atr': round(atr_value, 2) if atr_value else 0,
            'atr_pct': round(atr_pct, 2) if atr_pct else 0,
            'stock_type': stock_type,
            'margin_3day_change': margin.get('margin_3day_change', 0),
            'short_3day_change': margin.get('short_3day_change', 0),
            'is_margin_decrease': margin.get('is_margin_decrease', False),
            'is_short_increase': margin.get('is_short_increase', False),
            # 投信數據 (v5.4)
            'trust_today': trust_today,
            'trust_5day': trust_5day,
            'foreign_5day': foreign_5day,
            'trust_buy_days': trust_buy_days,
            # 歷史價格資料 (供 V8 量縮蓄勢使用)
            'prices': prices_list[:20] if prices_list else [],  # 保留最近 20 天
        })
    
    # 存到 raw 目錄（包含全市場收盤價，方便 V7 驗證）
    candidates_file = f'{raw_dir}/{latest_date}_{run_time}_candidates.json'
    with open(candidates_file, 'w', encoding='utf-8') as f:
        json.dump({
            'date': str(latest_date),
            'timestamp': datetime.now().isoformat(),
            'count': len(candidates_full),
            'v9_spec': 'MVP-20260122',  # V9 MVP
            'kd_version': 'KD(9,3,3)',  # V9 MVP
            'note': '完整候選資料 + 全市場收盤價，用於版本比較和 V7/V9 驗證',
            'stocks': candidates_full,
            'all_prices': all_market_prices,  # 全市場收盤價（供 V7 驗證用）
        }, f, ensure_ascii=False, indent=2)
    print(f'   [RAW] 已存 {len(candidates_full)} 檔候選 + {len(all_market_prices)} 檔收盤價: {candidates_file}')

    # === V9 MVP: 漏斗篩選 ===
    print('\n[V9] 開始漏斗篩選...')

    # Universe 計數
    universe_count = len(all_market_prices)
    after_base_count = len(candidates_full)

    print(f'  Universe: {universe_count}')
    print(f'  After BASE: {after_base_count}')

    # V7 篩選：連續 3 天 Close > MA20 AND 連續 3 天 Volume < MA(Volume,20) * 0.8
    v7_candidates = []
    for stock in candidates_full:
        ticker = stock['ticker']
        hist = historical_data.get(ticker, {})
        if not hist:
            continue

        prices_list = hist['prices']  # [(date, close, volume, high, low), ...] 最新在前

        if len(prices_list) < 20:
            continue

        # 計算 MA20
        closes = [p[1] for p in prices_list]
        volumes = [p[2] for p in prices_list]
        ma20_price = sum(closes[:20]) / 20
        ma20_volume = sum(volumes[:20]) / 20

        # 檢查連續 3 天 Close > MA20
        trend_ok = all(closes[i] > ma20_price for i in range(3))

        # 檢查連續 3 天 Volume < MA20_Volume * 0.8
        squeeze_ok = all(volumes[i] < ma20_volume * 0.8 for i in range(3))

        if trend_ok and squeeze_ok:
            stock['v7_pass'] = True
            v7_candidates.append(stock)

    after_v7_count = len(v7_candidates)
    print(f'  After V7: {after_v7_count}')

    # V9 篩選：K > D AND K_prev <= D_prev AND K > K_prev AND K < 80
    v9_candidates = []
    excluded_highk = []

    for stock in v7_candidates:
        k_val = stock.get('K_value')
        d_val = stock.get('D_value')
        k_prev = stock.get('K_prev')
        d_prev = stock.get('D_prev')

        if k_val is None or d_val is None or k_prev is None or d_prev is None:
            continue

        # K >= 80 必須排除
        if k_val >= 80:
            excluded_highk.append(stock)
            continue

        # 金叉條件：K > D (今天) AND K_prev <= D_prev (昨天死叉或平) AND K > K_prev (K 上升)
        golden_cross = (k_val > d_val) and (k_prev <= d_prev) and (k_val > k_prev)

        if golden_cross:
            stock['v9_pass'] = True
            v9_candidates.append(stock)

    after_v9_count = len(v9_candidates)
    excluded_highk_count = len(excluded_highk)

    print(f'  After V9: {after_v9_count}')
    print(f'  Excluded HighK (K>=80): {excluded_highk_count}')

    print(f'\n[V9] 漏斗篩選完成')
    print(f'  Universe: {universe_count} -> After BASE: {after_base_count} -> After V7: {after_v7_count} -> After V9: {after_v9_count} -> Excluded HighK: {excluded_highk_count}')

    # 8. 最終篩選
    print('\n[8/8] 最終篩選...')
    results = []  # 符合條件的股票

    for ticker in candidate_tickers:  # 改用 candidate_tickers (已經過 PE 篩選)
        # 取得股票基本資料
        stock = stocks.get(ticker)
        if not stock:
            continue

        # 取得 PE (已經在 candidate_tickers 篩選過 PE < 25)
        pe = pe_data.get(ticker, 0)

        # 法人條件：今日買超
        inst = institutional.get(ticker, [])
        if not inst or inst[0]['total'] <= 0:
            continue

        today_inst = inst[0]['total']
        buy_days = count_institutional_buy_days(inst)

        # 計算法人 1 月累積 (取所有資料，因為已經抓 30 天了)
        inst_1month = sum(r['total'] for r in inst)

        # 分析主力
        inst_leader = analyze_institutional_leader(inst)

        # 歷史技術指標
        hist = historical_data.get(ticker, {})
        if not hist:
            continue

        day5_change = hist['5day_change']
        avg_volume = hist['5day_avg_volume']

        # 營收 YoY
        rev = revenue_data.get(ticker, {})
        revenue_yoy = rev.get('yoy', 0)

        # === v5.1 篩選條件 (Gemini 建議優化) ===

        # 近 5 日漲幅 < 15% (v5.1 放寬：避免錯過強勢飆股)
        if day5_change >= 15:
            continue

        # v3.3: 移除天數上限，只要連續買超 >= 2 天就算
        if buy_days < 2:
            continue

        # 法人 5 日累積 > 300 張 (v3.2 新增：確保有份量)
        inst_5day = sum(r['total'] for r in inst[:5])
        if inst_5day < 300:
            continue

        # 法人 1 月累積 > -10,000 張 (避免長期賣壓)
        if inst_1month <= -10000:
            continue

        # 營收 YoY > 0% - 暫時停用 (FinMind 批量 API 只回傳最近一個月)
        # if revenue_yoy <= 0:
        #     continue

        # v5.1: 移除量能硬門檻，改為加分項 (在評分區處理)

        # === v3.2 新增：MA20 趨勢確認 ===
        prices_list = hist['prices']  # [(date, close, volume), ...] 最新在前
        closes = [p[1] for p in prices_list]
        
        # 計算 MA5, MA10 和 MA20 (v5.3: 加入 MA5 用於多頭判斷)
        ma5 = sum(closes[:5]) / 5 if len(closes) >= 5 else None
        ma10 = sum(closes[:10]) / 10 if len(closes) >= 10 else None
        ma20 = sum(closes[:20]) / 20 if len(closes) >= 20 else sum(closes) / len(closes)
        
        current_price = stock['price']
        if len(prices_list) >= 5 and current_price < ma20:  # 股價要在 MA 之上
            continue

        # === v3.3 新增：RSI 過熱判斷 ===
        rsi = 50  # 預設中性
        if len(prices_list) >= 15:  # 需要至少 15 天資料計算 RSI14
            closes_for_rsi = [p[1] for p in prices_list]
            rsi = calculate_rsi(closes_for_rsi, period=14)
            if rsi >= 85:  # v5: 放寬到 85 (原本 80)
                continue

        # 財報條件（毛利率、營業利益率）- 暫時停用
        fin = financial_data.get(ticker, {})
        gross_margin = fin.get('gross_margin', 0)
        operating_margin = fin.get('operating_margin', 0)

        if financial_data:  # 只有在有財報資料時才檢查
            if gross_margin < 20:
                continue
            if operating_margin < 0:
                continue

        # === v5.1 新增：ATR 計算 ===
        atr_value, atr_pct, stock_type = calculate_atr(prices_list, period=14)
        stop_loss, t1, t2, stop_note = calculate_stop_loss_atr(current_price, atr_value)

        # === v5.1 評分系統 (Gemini 建議：硬門檻改加分項) ===
        score = 0
        score_reasons = []
        tags = []  # 特殊標籤
        bias_ma20 = (current_price - ma20) / ma20 * 100

        # 標籤判定
        if day5_change >= 10:
            tags.append('[已漲]')
        if stock['volume'] < avg_volume:
            tags.append('[整理]')
        if bias_ma20 > 1 and stock['change_pct'] > 0:
            tags.append('[攻擊]')
        # v5.3: 均線多頭排列 (MA5 > MA10) - 只加標籤不加分
        if ma5 is not None and ma10 is not None and ma5 > ma10:
            tags.append('[多頭]')
        
        # === v5.4 新增：投信標籤 ===
        # 計算投信相關數據
        trust_5day = sum(r['trust'] for r in inst[:5]) if len(inst) >= 5 else sum(r['trust'] for r in inst)
        foreign_5day = sum(r['foreign'] for r in inst[:5]) if len(inst) >= 5 else sum(r['foreign'] for r in inst)
        trust_today = inst[0]['trust'] if inst else 0
        
        # 計算投信連買天數
        trust_buy_days = 0
        for record in inst:
            if record['trust'] > 0:
                trust_buy_days += 1
            else:
                break
        
        # 投信標籤
        if trust_today > 0:
            tags.append('[投信]')
        if trust_5day > foreign_5day and trust_5day > 0:
            tags.append('[土洋對作]')

        # 1. [籌碼] 法人有在顧 (+1~2)
        if inst_5day > 0:
            score += 1
            score_reasons.append("法人買超")
        if buy_days >= 3:
            score += 1
            score_reasons.append(f"連{buy_days}天")

        # 2. [動能] 攻擊訊號
        if bias_ma20 > 1 and stock['change_pct'] > 0:
            score += 1
            score_reasons.append("攻擊")

        # 3. [量能] 人氣匯聚 (v5.1 改為加分項，不再是門檻)
        if stock['volume'] > avg_volume:
            score += 1
            score_reasons.append("量增")

        # 4. [位階] 安全不追高
        if 0 < stock['change_pct'] < 5:
            score += 1
            score_reasons.append("穩漲")

        # === v5.2 新增：Bonus 加分 ===
        
        # 取得融資券資料
        margin = margin_data.get(ticker, {})
        
        # 5. [資減] 融資3日減 + 法人買 (+1) - 散戶走、法人來
        if margin.get('is_margin_decrease', False) and inst_5day > 0:
            score += 1
            score_reasons.append("資減")
            tags.append('[資減]')
        
        # 6. [軋空] 融券3日增 (+1) - 有嘎空潛力
        if margin.get('is_short_increase', False):
            score += 1
            score_reasons.append("軋空")
            tags.append('[軋空]')
        
        # 7. [YoY] 營收成長 (+1)
        if revenue_yoy > 0:
            score += 1
            score_reasons.append(f"YoY+{revenue_yoy:.0f}%")
        
        # === v5.4 新增：投信加分 ===
        # 8. [投信買] 投信今日買超 (+1) - 投信短打適合隔日沖
        if trust_today > 0:
            score += 1
            score_reasons.append("投信買")
        
        # 9. [投信連買] 投信連續買超 >= 2 天 (+1)
        if trust_buy_days >= 2:
            score += 1
            score_reasons.append(f"投信連{trust_buy_days}天")

        # v5.1: 只顯示 >= 3 分的股票
        if score < 3:
            continue

        # === 符合所有條件，加入結果 ===
        result = {
            'ticker': ticker,
            'name': stock['name'],
            'price': stock['price'],
            'change_pct': stock['change_pct'],
            'volume': stock['volume'],
            'pe': pe,
            'inst_today': today_inst,
            'inst_5day': inst_5day,
            'inst_1month': inst_1month,
            'inst_leader': inst_leader,
            'buy_days': buy_days,
            '5day_change': round(day5_change, 2),
            'avg_volume': int(avg_volume),
            'revenue_yoy': revenue_yoy,
            'rsi': rsi,
            'gross_margin': gross_margin,
            'operating_margin': operating_margin,
            # v5.1 ATR 劇本小卡
            'ma10': round(ma10, 2) if ma10 else None,
            'ma20': round(ma20, 2),
            'atr': atr_value,
            'atr_pct': atr_pct,
            'stock_type': stock_type,
            'stop_loss': stop_loss,
            't1': t1,
            't2': t2,
            'stop_note': stop_note,
            # v5.2 融資券資料
            'margin_3day_change': margin.get('margin_3day_change', 0),
            'short_3day_change': margin.get('short_3day_change', 0),
            # v5 評分系統
            'score': score,
            'score_reasons': score_reasons,
            'tags': tags,
            'bias_ma20': round(bias_ma20, 2),
        }

        results.append(result)

    # v5: 用評分排序 (同分則依法人5日累積)
    results = sorted(results, key=lambda x: (x['score'], x['inst_5day']), reverse=True)

    # 8. 輸出結果
    output_results(results)
    
    # 9. 儲存歷史資料 (回測用)
    save_to_history(results)

    print('\n' + '=' * 80)
    print(f'[OK] 符合條件（推薦買入）: {len(results)} 檔')
    print(f'詳細結果已存到 scan_result_v3.txt')


def output_results(results):
    """輸出結果到檔案（含健康檢查報告）"""
    # 執行健康檢查
    warnings = check_data_health()
    
    with open('scan_result_v3.txt', 'w', encoding='utf-8') as f:
        today = datetime.now().strftime('%Y-%m-%d')

        f.write('=' * 150 + '\n')
        f.write(f'選股條件 v5 篩選結果 (評分系統) - {today}\n')
        f.write('=' * 150 + '\n\n')

        # 健康檢查報告
        f.write('[健康檢查]\n')
        if warnings:
            f.write('⚠️ 資料異常警告:\n')
            for w in warnings:
                f.write(f'  - {w}\n')
        else:
            f.write('✅ 資料正常\n')
        
        f.write(f'  證交所: {HEALTH_CHECK["stock_count"]} 檔\n')
        f.write(f'  PE: {HEALTH_CHECK["pe_count"]} 檔\n')
        if HEALTH_CHECK['inst_total'] > 0:
            f.write(f'  法人: {HEALTH_CHECK["inst_success"]}/{HEALTH_CHECK["inst_total"]} 成功\n')
        if HEALTH_CHECK['revenue_total'] > 0:
            f.write(f'  營收: {HEALTH_CHECK["revenue_success"]}/{HEALTH_CHECK["revenue_total"]} 成功\n')
        if HEALTH_CHECK['margin_total'] > 0:
            f.write(f'  融資券: {HEALTH_CHECK["margin_success"]}/{HEALTH_CHECK["margin_total"]} 成功\n')
        f.write('\n')

        f.write('[OK] 符合條件 (推薦買入) - v5.2 評分排序 (基礎5分+Bonus最高8分)\n')
        f.write('-' * 150 + '\n')
        f.write(f"{'#':>3} {'分':>3} {'代號':<6} {'名稱':<10} {'價格':>7} {'漲幅':>7} {'類型':<4} "
               f"{'法人5日':>10} {'主力':<6} {'標籤':<15} {'評分理由':<25}\n")
        f.write('-' * 150 + '\n')

        for i, r in enumerate(results[:20], 1):
            score = r.get('score', 0)
            reasons = r.get('score_reasons', [])
            reasons_str = ','.join(reasons) if reasons else '-'
            tags = r.get('tags', [])
            tags_str = ''.join(tags) if tags else '-'
            stock_type = r.get('stock_type', '普通')
            type_icon = '🐰' if stock_type == '兔子' else ('🐢' if stock_type == '烏龜' else '🚶')
            
            # 評分符號
            if score >= 5:
                score_icon = '🔥'
            elif score >= 4:
                score_icon = '⭐'
            else:
                score_icon = '✅'
            
            line = (f"{i:>3} {score_icon}{score} {r['ticker']:<6} {r['name']:<10} {r['price']:>7.1f} "
                   f"{r['change_pct']:>+6.2f}% {type_icon:<4} "
                   f"{r['inst_5day']:>+10,} {r['inst_leader']:<6} {tags_str:<15} {reasons_str:<25}\n")
            f.write(line)
            # Windows 終端可能無法顯示 emoji，改用 safe print
            try:
                print(line.strip())
            except UnicodeEncodeError:
                # Fallback: 移除 emoji 後再印
                line_safe = line.replace('🔥', '*').replace('⭐', '+').replace('✅', 'v').replace('🐰', 'R').replace('🐢', 'T').replace('🚶', '-')
                print(line_safe.strip())

        f.write(f'\n共 {len(results)} 檔\n')
        
        # === v5.2 新增：ATR 劇本小卡 (含融資券) ===
        if results:
            f.write('\n' + '=' * 60 + '\n')
            f.write('📋 【v5.2 ATR 劇本小卡】操作指引\n')
            f.write('=' * 60 + '\n\n')
            
            for i, r in enumerate(results[:10], 1):  # 最多顯示 10 檔
                score = r.get('score', 0)
                stock_type = r.get('stock_type', '普通')
                type_icon = '🐰' if stock_type == '兔子' else ('🐢' if stock_type == '烏龜' else '🚶')
                atr = r.get('atr', 0)
                atr_pct = r.get('atr_pct', 0)
                tags = r.get('tags', [])
                tags_str = ' '.join(tags) if tags else ''
                
                # v5.2 融資券資料
                margin_change = r.get('margin_3day_change', 0)
                short_change = r.get('short_3day_change', 0)
                revenue_yoy = r.get('revenue_yoy', 0)
                
                # 計算停損停利百分比
                stop_pct = (r['stop_loss'] - r['price']) / r['price'] * 100
                t1_pct = (r['t1'] - r['price']) / r['price'] * 100
                t2_pct = (r['t2'] - r['price']) / r['price'] * 100
                
                # v5.3 新增：建議入場價 (收盤價 - 0.5*ATR ~ 收盤價)
                entry_low = round(r['price'] - 0.5 * atr, 0)
                entry_high = round(r['price'], 0)
                
                # 評分符號 (v5.2: 最高 8 分)
                if score >= 6:
                    score_icon = '🔥👑'  # 超強
                elif score >= 5:
                    score_icon = '🔥⭐'  # 滿分+加分
                elif score >= 4:
                    score_icon = '⭐'
                else:
                    score_icon = '✅'
                
                f.write(f"{score_icon} {score}分 {r['name']} ({r['ticker']}) ${r['price']:.1f} {tags_str}\n")
                f.write(f"   📊 特性: {type_icon} {stock_type} (ATR ${atr} = {atr_pct}%)\n")
                f.write(f"   📈 法人: {r['inst_leader']}連{r['buy_days']}買 {r['inst_5day']:+,}張\n")
                
                # v5.2 新增：融資券資訊
                if margin_change != 0 or short_change != 0:
                    f.write(f"   💰 融資: {margin_change:+,}張(3日)  融券: {short_change:+,}張(3日)\n")
                if revenue_yoy != 0:
                    f.write(f"   📊 營收: YoY {revenue_yoy:+.1f}%\n")
                
                f.write(f"   ────────────────────────────────────\n")
                f.write(f"   💵 進場: ${entry_low:.0f}~${entry_high:.0f} (回檔0.5ATR接)\n")
                f.write(f"   🛡️ 停損: ${r['stop_loss']:.1f} ({stop_pct:+.1f}%)  跌破快逃\n")
                f.write(f"   🎯 T1:   ${r['t1']:.1f} ({t1_pct:+.1f}%)  先賣一半\n")
                f.write(f"   🚀 T2:   ${r['t2']:.1f} ({t2_pct:+.1f}%)  趨勢滿足\n")
                f.write('\n')
            
            # === v5.4 極簡行動卡 (LINE推送專用) ===
            f.write('\n' + '=' * 60 + '\n')
            f.write('📱 【極簡行動卡】LINE推送用\n')
            f.write('=' * 60 + '\n\n')

            # 取得大盤資訊
            market_change = HEALTH_CHECK.get('market_change_pct', 0)
            market_sign = '+' if market_change >= 0 else ''
            data_date = HEALTH_CHECK.get('data_date', datetime.now().strftime('%Y-%m-%d'))

            # 開頭框線
            f.write('━' * 25 + '\n')
            f.write(f"📊 {data_date} 選股 (大盤{market_sign}{market_change:.2f}%)\n")
            f.write('━' * 25 + '\n\n')

            for r in results[:6]:  # 最多 6 檔
                score = r.get('score', 0)
                stock_type = r.get('stock_type', '普通')
                type_icon = '🐰' if stock_type == '兔子' else ('🐢' if stock_type == '烏龜' else '🚶')
                atr = r.get('atr', 0)

                # 評分符號 (滿分8分)
                score_icon = '🔥' if score >= 5 else ('⭐' if score >= 4 else '✅')

                # 建議入場價
                entry_low = int(r['price'] - 0.5 * atr)
                entry_high = int(r['price'])

                # 停損停利整數
                stop_int = int(r['stop_loss'])
                t1_int = int(r['t1'])
                t2_int = int(r['t2'])

                # 籌碼+特殊標籤
                chip_tags = []
                if r.get('margin_3day_change', 0) < 0:
                    chip_tags.append('資減')
                if r.get('short_3day_change', 0) > 0:
                    chip_tags.append('軋空')

                # 投信買入
                if '投信買' in r.get('score_reasons', []):
                    chip_tags.append('投信')

                # YoY 顯著成長
                yoy = r.get('yoy_growth', 0)
                if yoy >= 10:
                    chip_tags.append(f"YoY+{int(yoy)}%")

                # 注意股警示
                warning_text = ''
                if '注意股' in r['name'] or r.get('is_warning_stock', False):
                    warning_text = '   ⚠️注意股 建議觀望\n'

                # 組合第二行文字
                chip_line = f"   {r['inst_leader']}連{r['buy_days']}買"
                if chip_tags:
                    chip_line += '｜' + '｜'.join(chip_tags)

                # 輸出格式 (3行精簡)
                f.write(f"{score_icon} {r['name']} {r['ticker']} ${r['price']:.1f} ⟨{score}分⟩{type_icon}\n")
                f.write(f"{chip_line}\n")
                if warning_text:
                    f.write(warning_text)
                f.write(f"   💵{entry_low}~{entry_high}｜🛡️{stop_int}｜🎯{t1_int}/{t2_int}\n\n")

            # 結尾框線
            f.write('━' * 25 + '\n')
        
        # 警告摘要
        if warnings:
            f.write('\n⚠️ 警告: ' + ', '.join(warnings) + '\n')
        
        f.write('=' * 140 + '\n')


def save_to_history(results):
    """
    儲存每日掃描結果到歷史檔案 (v3.4 新增)
    用於累積資料做歷史回測
    
    v3.6 修正: 使用資料日期 (交易日) 而非執行日期，避免同日多次執行覆蓋
    """
    import json
    import os
    
    # 使用資料日期（交易日），不是執行日期
    data_date = HEALTH_CHECK.get('data_date', datetime.now().strftime('%Y-%m-%d'))
    history_dir = 'data/history'
    
    # 確保目錄存在
    os.makedirs(history_dir, exist_ok=True)
    
    # 轉換結果為可序列化格式
    history_entry = {
        'date': data_date,
        'timestamp': datetime.now().isoformat(),
        'count': len(results),
        'stocks': []
    }
    
    for r in results:
        stock_data = {
            'ticker': r['ticker'],
            'name': r['name'],
            'price': r['price'],
            'change_pct': r['change_pct'],
            'pe': r['pe'],
            'inst_5day': r['inst_5day'],
            'inst_1month': r['inst_1month'],
            'inst_leader': r['inst_leader'],
            'buy_days': r['buy_days'],
            '5day_change': r['5day_change'],
            'revenue_yoy': r['revenue_yoy'],
            'rsi': r.get('rsi', 0),
            # v5.1 ATR 劇本小卡
            'atr': r.get('atr', 0),
            'atr_pct': r.get('atr_pct', 0),
            'stock_type': r.get('stock_type', '普通'),
            'stop_loss': r.get('stop_loss'),
            't1': r.get('t1'),
            't2': r.get('t2'),
            'stop_note': r.get('stop_note', ''),
            'ma10': r.get('ma10'),
            'ma20': r.get('ma20'),
            # v5.2 融資券資料
            'margin_3day_change': r.get('margin_3day_change', 0),
            'short_3day_change': r.get('short_3day_change', 0),
            # v5 評分系統
            'score': r.get('score', 0),
            'score_reasons': r.get('score_reasons', []),
            'tags': r.get('tags', []),
            'bias_ma20': r.get('bias_ma20', 0),
        }
        history_entry['stocks'].append(stock_data)
    
    # 儲存當日結果（加入時間戳避免覆蓋）
    run_time = datetime.now().strftime('%H%M')
    daily_file = f'{history_dir}/{data_date}_{run_time}.json'
    with open(daily_file, 'w', encoding='utf-8') as f:
        json.dump(history_entry, f, ensure_ascii=False, indent=2)
    
    print(f'📁 歷史資料已存: {daily_file}')
    
    # 也追加到總歷史檔 (方便查詢)
    all_history_file = f'{history_dir}/all_history.json'
    all_history = []
    
    if os.path.exists(all_history_file):
        try:
            with open(all_history_file, 'r', encoding='utf-8') as f:
                all_history = json.load(f)
        except:
            all_history = []
    
    # 移除舊的同日資料 (避免重複)
    all_history = [h for h in all_history if h.get('date') != data_date]
    all_history.append(history_entry)
    
    # 只保留最近 90 天
    all_history = sorted(all_history, key=lambda x: x['date'])[-90:]
    
    with open(all_history_file, 'w', encoding='utf-8') as f:
        json.dump(all_history, f, ensure_ascii=False, indent=2)
    
    print(f'📊 總歷史資料: {len(all_history)} 天')


if __name__ == '__main__':
    main()
