#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
選股條件 v3.4 篩選器 (含劇本小卡)
目標：找「法人有在買、趨勢向上、還沒過熱」的股票

篩選條件（所有條件都必須符合）:

【基本面】
- 價格 30-300 元
- PE < 35
- 營收 YoY > 0%

【技術面】
- 今日漲幅 -2% ~ 5% (v3.3: 容許小回檔)
- 近 5 日累積漲幅 < 10%
- 今日量 > 5 日均量
- 股價 > MA
- RSI < 80 (v3.3 新增: 避免過熱)

【籌碼面】
- 法人連續買超 >= 2 天 (v3.3: 移除上限)
- 法人 5 日累積 > 300 張
- 日成交量 > 800 張
- 法人 1 月累積 > -10,000 張

【v3.4 新增：劇本小卡】
- 動態停損：乖離>5%守MA10，乖離<5%守MA20，底線-7%
- 停利目標：+20%

輸出說明:
- 只輸出符合所有條件的股票
- 適合短波段操作 (3-10 天)
"""

import os
import requests
import urllib3
from datetime import datetime, timedelta
import json
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# FinMind API Tokens (多帳號輪替，每個 600次/小時)
FINMIND_TOKENS = [
    'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMS0wMSAxNTo1MzoyMCIsInVzZXJfaWQiOiJhdGl0aSIsImlwIjoiMTExLjI0My4xNDIuOTkifQ.NmNnOo6KP0bmvvdFQ68L6SM1DChuxrW7Z1P5onzPWlU',
    'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMS0wMSAyMjowNTozNSIsInVzZXJfaWQiOiJhdGl0aTQzNiIsImlwIjoiMTExLjI0My4xNDIuOTkifQ.ejONnKY_3b9tqA7wh47d2r5yfUKCFWybdNSkrJp3C10',
    'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMS0wMSAyMjowODo1OCIsInVzZXJfaWQiOiJ4aWFpIiwiaXAiOiIxMTEuMjQzLjE0Mi45OSJ9.-sWtQw0UY8FkMCR8Tg_Lp9kO-UkRhjLTqRrlDXXpk10',
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


def calculate_stop_loss(close_price, ma10, ma20):
    """
    動態停損 (v3.4):
    - 乖離 > 5% (噴出股) → 停損守 MA10 (緊)
    - 乖離 < 5% (起漲股) → 停損守 MA20 (寬)
    - 底線：-7% 硬停損
    
    返回: (停損價, 說明)
    """
    # 1. 算乖離率
    bias_ma20 = (close_price - ma20) / ma20 if ma20 and ma20 > 0 else 0

    # 2. 決定停損基準線
    if bias_ma20 > 0.05:  # 高出 5% 以上 (噴出股)
        technical_stop = ma10 if ma10 else close_price * 0.95
        note = f"守MA10"
    else:  # 還在低檔 (剛起漲)
        technical_stop = ma20 if ma20 else close_price * 0.93
        note = f"守MA20"

    # 3. 雙刀流：取技術停損與 -7% 較高者 (離現價較近者)
    hard_stop = close_price * 0.93  # -7%
    final_stop = max(technical_stop or hard_stop, hard_stop)
    
    return round(final_stop, 2), note


def calculate_v4_score(stock_data, inst_data, ma20):
    """
    v4.0 計分函數（Gemini 融合版）
    
    參數：
        stock_data: {price, volum

e, change_pct, ...}
        inst_data: 法人歷史資料 [{date, foreign, trust, total}, ...]
        ma20: MA20 價格
    
    返回：
        score: int (0-7)
        reasons: list[str]
    """
    score = 0
    reasons = []
    
    price = stock_data['price']
    volume = stock_data['volume']
    change_pct = stock_data['change_pct']
    
    # === 籌碼面（最高 4 分）===
    
    # 計算 5 日買超
    net_buy_5days = sum(r['total'] for r in inst_data[:5]) if inst_data else 0
    
    # [基礎分] 有大人顧
    if net_buy_5days > 0:
        score += 1
        reasons.append("法人買超")
    
    # [力道分] 緯創型（錢砸很多）
    if net_buy_5days > 5000:
        score += 2
        reasons.append(f"力道強({net_buy_5days//1000}K張)")
    elif net_buy_5days > 1000:
        score += 1
        reasons.append(f"有買超({net_buy_5days//1000}K張)")
    
    # [時機分] 技嘉型（剛開始買）
    buy_days = count_institutional_buy_days(inst_data)
    if 1 <= buy_days <= 3:
        score += 1
        reasons.append(f"剛買{buy_days}天")
    
    # === 動能面（最高 2 分）===
    
    # [量能] 有人點火
    avg_vol = stock_data.get('avg_volume', 0)
    if avg_vol > 0 and volume > avg_vol:
        score += 1
        reasons.append("量增")
    
    # [漲幅] 剛起漲
    if 0 < change_pct <= 4:
        score += 1
        reasons.append("剛起漲")
    elif change_pct > 5:
        # 漲太多不加分（已經提示是缺點）
        pass
    
    # === 安全面（最高 1 分）===
    
    # [乖離] 離月線近
    if ma20 and ma20 > 0:
        bias = (price - ma20) / ma20 * 100
        if bias < 8:
            score += 1
            reasons.append("位階安全")
    
    return score, reasons


def calculate_batch_profit(price):
    """
    計算分批停利價格（v4.0）
    避免「200 一瞬間」問題
    
    返回：{
        'batch_1': {'price': xxx, 'pct': 4, 'note': '保本'},
        'batch_2': {...},
        'batch_3': {...},
    }
    """
    return {
        'batch_1': {
            'price': round(price * 1.04, 1),
            'pct': 4,
            'note': '保本先跑'
        },
        'batch_2': {
            'price': round(price * 1.07, 1),
            'pct': 7,
            'note': '主要目標'
        },
        'batch_3': {
            'price': round(price * 1.10, 1),
            'pct': 10,
            'note': '賺更多'
        },
    }

def fetch_historical_prices(ticker, days=10):
    """
    抓取歷史股價（用於計算 5 日漲幅、5 日均量）
    使用 FinMind API (比證交所穩定)
    返回: [(date, close, volume), ...]，最新的在前面
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

                    if close > 0 and volume > 0:
                        prices.append((date_str, close, volume))
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
    抓取營收資料並計算 YoY (含 TOKEN 輪替)
    使用 FinMind API，逐檔抓取

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

    # 計算日期範圍 (最近 400 天，涵蓋 1 年多，才能比對 YoY)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=400)

    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')

    print(f'   營收資料範圍: {start_str} ~ {end_str}')
    print(f'   需查詢 {len(tickers)} 檔 (逐檔抓取)...')

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
                df = dl.taiwan_stock_month_revenue(
                    stock_id=ticker,
                    start_date=start_str,
                    end_date=end_str
                )

                if df is None or df.empty or len(df) < 1:
                    fetched = True
                    break

                # 計算 YoY
                latest = df.iloc[-1]  # 最新的一筆
                latest_month = latest.get('revenue_month')
                latest_year = latest.get('revenue_year')
                latest_revenue = float(latest.get('revenue', 0))

                if latest_revenue == 0:
                    fetched = True
                    break

                # 找去年同期 (month 相同, year - 1)
                year_ago_data = df[(df['revenue_month'] == latest_month) &
                                   (df['revenue_year'] == latest_year - 1)]

                if year_ago_data.empty:
                    fetched = True
                    break

                year_ago_revenue = float(year_ago_data.iloc[0]['revenue'])
                if year_ago_revenue == 0:
                    fetched = True
                    break

                yoy = ((latest_revenue - year_ago_revenue) / year_ago_revenue) * 100

                result[ticker] = {
                    'yoy': round(yoy, 2),
                    'latest_month': f'{latest_year}/{latest_month:02d}'
                }
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
                        print(f'      [{ticker}] 失敗（已重試 {max_retries} 次）: {e}')
                    break

        # 進度顯示 + 避免被擋
        if i % 10 == 0:
            print(f'      進度: {i}/{len(tickers)} ({success_count} 成功, {retry_count} 重試)')
            time.sleep(0.3)

    HEALTH_CHECK['revenue_success'] = success_count
    HEALTH_CHECK['revenue_total'] = len(tickers)
    print(f'   取得 {success_count}/{len(tickers)} 檔營收資料 (共重試 {retry_count} 次)')
    return result


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
    print('選股條件 v3.2 - 短波段優化版 (法人剛進場、趨勢向上、還沒噴)')
    print('=' * 80)

    # 1. 抓取當日股價
    print('\n[1/5] 抓取當日股價...')
    url_stocks = 'https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL'
    response = requests.get(url_stocks, timeout=15, verify=False)
    stock_data = response.json()
    
    # 記錄資料日期（用第一筆資料的日期）
    if stock_data:
        first_item = stock_data[0]
        HEALTH_CHECK['data_date'] = first_item.get('Date', '')

    stocks = {}
    for item in stock_data:
        ticker = item.get('Code', '')
        if not (ticker.isdigit() and len(ticker) == 4):
            continue
        if is_excluded_stock(ticker):
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

        # 基本篩選 (v3.2 放寬)
        if not (30 <= close <= 300):  # 價格 30-300 (放寬)
            continue
        if not (-2 <= change_pct <= 5):  # v3.3: 容許小回檔 -2% ~ 5%
            continue
        if volume < 800:  # 日成交量 > 800 張 (新增)
            continue

        stocks[ticker] = {
            'name': item.get('Name', ''),
            'price': close,
            'change_pct': round(change_pct, 2),
            'volume': volume
        }

    HEALTH_CHECK['stock_count'] = len(stocks)
    print(f'   基本篩選後: {len(stocks)} 檔')

    # 2. 抓取本益比 + 第二階段篩選
    print('\n[2/5] 抓取本益比...')
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
        HEALTH_CHECK['pe_count'] = len(pe_data)
        print(f'   取得 {len(pe_data)} 檔 PE 資料')
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
    print('\n[5/6] 抓取財報資料...')
    print('   (暫時跳過財報檢查,避免 API 問題)')
    financial_data = {}  # TODO: 修正 FinMind API 後啟用
    # financial_data = fetch_financial_data()

    # 6. 抓取營收資料（計算 YoY）
    print('\n[6/7] 抓取營收資料...')
    revenue_data = fetch_revenue_data(candidate_tickers)

    # 7. 最終篩選
    print('\n[7/7] 最終篩選...')
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

        # === v3.2 篩選條件 (短波段優化) ===

        # 近 5 日漲幅 < 10% (避免追高)
        if day5_change >= 10:
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

        # 營收 YoY > 0% (v3.2 放寬：不衰退就及格)
        if revenue_yoy <= 0:
            continue

        # 今日量 > 5 日均量 (啟動訊號)
        if stock['volume'] < avg_volume:
            continue

        # === v3.2 新增：MA20 趨勢確認 ===
        prices_list = hist['prices']  # [(date, close, volume), ...] 最新在前
        closes = [p[1] for p in prices_list]
        
        # 計算 MA10 和 MA20
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
            if rsi >= 80:  # RSI >= 80 表示過熱，避免追高
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

        # === v3.4 新增：計算停損/停利 (劇本小卡) ===
        stop_loss, stop_note = calculate_stop_loss(current_price, ma10, ma20)
        take_profit = round(current_price * 1.20, 2)  # +20% 停利目標

        # === 符合所有條件，加入結果 ===
        result = {
            'ticker': ticker,
            'name': stock['name'],
            'price': stock['price'],
            'change_pct': stock['change_pct'],
            'volume': stock['volume'],
            'pe': pe,
            'inst_today': today_inst,
            'inst_5day': inst_5day,  # 5 日累積 (已在上面計算)
            'inst_1month': inst_1month,  # 1 月累積
            'inst_leader': inst_leader,  # 主力
            'buy_days': buy_days,
            '5day_change': round(day5_change, 2),
            'avg_volume': int(avg_volume),
            'revenue_yoy': revenue_yoy,  # 營收 YoY
            'rsi': rsi,  # v3.3: RSI 過熱指標
            'gross_margin': gross_margin,
            'operating_margin': operating_margin,
            # v3.4 劇本小卡
            'ma10': round(ma10, 2) if ma10 else None,
            'ma20': round(ma20, 2) if ma20 else None,
            'stop_loss': stop_loss,
            'stop_note': stop_note,
            'take_profit': take_profit,
        }
        
        # === v4.0 新增：計分制 + 分批停利 ===
        # 計算 v4.0 分數
        stock_data_for_score = {
            'price': stock['price'],
            'volume': stock['volume'],
            'change_pct': stock['change_pct'],
            'avg_volume': int(avg_volume)
        }
        score, reasons = calculate_v4_score(stock_data_for_score, inst, ma20)
        
        # 計算分批停利
        batch_profit = calculate_batch_profit(stock['price'])
        
        # 加入 v4.0 欄位
        result['score'] = score
        result['reasons'] = reasons
        result['batch_profit'] = batch_profit

        results.append(result)

    # 排序 (依法人 5 日累積排序)
    results = sorted(results, key=lambda x: x['inst_5day'], reverse=True)

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

        f.write('=' * 140 + '\n')
        f.write(f'選股條件 v3.4 篩選結果 (含劇本小卡) - {today}\n')
        f.write('=' * 140 + '\n\n')

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
        f.write('\n')

        f.write('[OK] 符合條件 (推薦買入) - 法人剛進場、趨勢向上、還沒噴 (短波段 3-10 天)\n')
        f.write('-' * 140 + '\n')
        f.write(f"{'#':>3} {'代號':<6} {'名稱':<10} {'價格':>7} {'漲幅':>7} {'PE':>6} "
               f"{'法人5日':>10} {'法人1月':>10} {'主力':<6} {'營收YoY':>9} "
               f"{'買天':>5} {'5日漲':>7} {'量/均':>12}\n")
        f.write('-' * 140 + '\n')

        for i, r in enumerate(results[:20], 1):
            volume_ratio = f"{r['volume']}/{r['avg_volume']}"
            yoy_str = f"{r['revenue_yoy']:+.1f}%" if r['revenue_yoy'] != 0 else '-'
            line = (f"{i:>3} {r['ticker']:<6} {r['name']:<10} {r['price']:>7.1f} "
                   f"{r['change_pct']:>+6.2f}% {r['pe']:>6.1f} "
                   f"{r['inst_5day']:>+10,} {r['inst_1month']:>+10,} {r['inst_leader']:<6} {yoy_str:>9} "
                   f"{r['buy_days']:>5} {r['5day_change']:>+6.2f}% {volume_ratio:>12}\n")
            f.write(line)
            print(line.strip())

        f.write(f'\n共 {len(results)} 檔\n')
        
        # === v3.4 新增：劇本小卡 ===
        if results:
            f.write('\n' + '=' * 60 + '\n')
            f.write('📋 【劇本小卡】操作指引\n')
            f.write('=' * 60 + '\n\n')
            
            for i, r in enumerate(results[:10], 1):  # 最多顯示 10 檔
                stop_pct = (r['stop_loss'] - r['price']) / r['price'] * 100
                profit_pct = (r['take_profit'] - r['price']) / r['price'] * 100
                
                # v4.0 評分和分批停利
                score = r.get('score', 0)
                reasons = r.get('reasons', [])
                batch = r.get('batch_profit', {})
                
                # 標題行（加入分數）
                f.write(f"🎯 {r['name']} ({r['ticker']}) ${r['price']:.1f} ({r['change_pct']:+.1f}%) - {score} 分\n")
                
                # 評分理由
                if reasons:
                    f.write(f"   💡 評分理由：{' | '.join(reasons)}\n")
                
                # v4.0 分批停利
                if batch:
                    f.write(f"\n   【分批停利】\n")
                    b1 = batch.get('batch_1', {})
                    b2 = batch.get('batch_2', {})
                    b3 = batch.get('batch_3', {})
                    f.write(f"   第 1 批：${b1.get('price', 0):.1f} (+{b1.get('pct', 0)}% {b1.get('note', '')})\n")
                    f.write(f"   第 2 批：${b2.get('price', 0):.1f} (+{b2.get('pct', 0)}% {b2.get('note', '')})\n")
                    f.write(f"   第 3 批：${b3.get('price', 0):.1f} (+{b3.get('pct', 0)}% {b3.get('note', '')})\n")
                    f.write(f"\n")
                f.write(f"   🛡️ 停損: ${r['stop_loss']:.1f} ({stop_pct:+.1f}%) - {r['stop_note']}\n")

                f.write(f"   📊 主力: {r['inst_leader']} | 法人5日: {r['inst_5day']:+,}張\n")
                f.write('\n')
        
        # 警告摘要
        if warnings:
            f.write('\n⚠️ 警告: ' + ', '.join(warnings) + '\n')
        
        f.write('=' * 140 + '\n')


def save_to_history(results):
    """
    儲存每日掃描結果到歷史檔案 (v3.4 新增)
    用於累積資料做歷史回測
    """
    import json
    import os
    
    today = datetime.now().strftime('%Y-%m-%d')
    history_dir = 'data/history'
    
    # 確保目錄存在
    os.makedirs(history_dir, exist_ok=True)
    
    # 轉換結果為可序列化格式
    history_entry = {
        'date': today,
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
            # 劇本小卡
            'stop_loss': r.get('stop_loss'),
            'take_profit': r.get('take_profit'),
            'stop_note': r.get('stop_note', ''),
            'ma10': r.get('ma10'),
            'ma20': r.get('ma20'),
        }
        history_entry['stocks'].append(stock_data)
    
    # 儲存當日結果
    daily_file = f'{history_dir}/{today}.json'
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
    all_history = [h for h in all_history if h.get('date') != today]
    all_history.append(history_entry)
    
    # 只保留最近 90 天
    all_history = sorted(all_history, key=lambda x: x['date'])[-90:]
    
    with open(all_history_file, 'w', encoding='utf-8') as f:
        json.dump(all_history, f, ensure_ascii=False, indent=2)
    
    print(f'📊 總歷史資料: {len(all_history)} 天')


if __name__ == '__main__':
    main()
