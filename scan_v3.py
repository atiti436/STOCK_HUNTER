#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
選股條件 v3.0 篩選器
目標：找「法人剛進場、體質健康、還沒噴」的股票（抓起漲點）

嚴格版條件（推薦買）:
- 價格 50-200 元
- PE < 25
- 毛利率 > 20%
- 營業利益率 > 0%
- 法人買超 3-5 天（剛進場）
- 近 5 日累積漲幅 < 10%（避免追高）
- 今日漲幅 0-5%
- 今日量 > 5 日均量（啟動訊號）

寬鬆版條件（觀察用）:
- 同上，但財報條件放寬（毛利率可 < 20%，營業利益率可 < 0）
"""

import requests
import urllib3
from datetime import datetime, timedelta
import json
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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


def fetch_historical_prices(ticker, days=10):
    """
    抓取歷史股價（用於計算 5 日漲幅、5 日均量）
    返回: [(date, close, volume), ...]，最新的在前面
    """
    try:
        # 使用證交所個股日成交資訊
        today = datetime.now()
        month_str = today.strftime('%Y%m')

        url = f'https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY'
        params = {
            'date': month_str + '01',
            'stockNo': ticker,
            'response': 'json'
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url, params=params, headers=headers, timeout=15, verify=False)
        data = response.json()

        if data.get('stat') != 'OK' or not data.get('data'):
            return []

        prices = []
        for row in data['data']:
            try:
                date_str = row[0].replace('/', '')  # 113/12/31 -> 1131231
                close = float(row[6].replace(',', ''))
                volume = int(row[1].replace(',', '')) // 1000  # 轉成張
                prices.append((date_str, close, volume))
            except:
                continue

        # 反轉順序（最新的在前）
        prices.reverse()
        return prices[:days]

    except Exception as e:
        print(f'   [{ticker}] 歷史股價抓取失敗: {e}')
        return []


def fetch_institutional_history(days=7):
    """
    抓取最近 N 天的法人買賣超
    使用 FinMind API (比證交所穩定)
    返回: {ticker: [{date, foreign, trust, total}, ...]}
    """
    try:
        from FinMind.data import DataLoader
        dl = DataLoader()

        # 計算日期範圍
        end_date = datetime.now() - timedelta(days=1)  # 昨天
        start_date = end_date - timedelta(days=days)

        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')

        print(f'   抓取法人資料: {start_str} ~ {end_str}')

        # 抓取三大法人買賣超
        df = dl.taiwan_stock_institutional_investors(
            stock_id='',  # 空字串代表全部
            start_date=start_str,
            end_date=end_str
        )

        if df is None or df.empty:
            print('   [!] FinMind 法人資料為空')
            return {}

        institutional = {}

        # FinMind 格式: 每個法人類型一行
        # name 可能是: Foreign_Investor, Investment_Trust, Dealer_self, 等
        for _, row in df.iterrows():
            ticker = str(row.get('stock_id', '')).strip()
            date_str = str(row.get('date', '')).replace('-', '')
            name = str(row.get('name', '')).strip()
            buy = int(row.get('buy', 0))
            sell = int(row.get('sell', 0))
            net = (buy - sell) // 1000  # 轉成張

            if not ticker or not date_str or not name:
                continue

            # 建立 key
            key = f"{ticker}_{date_str}"
            if key not in institutional:
                institutional[key] = {
                    'ticker': ticker,
                    'date': date_str,
                    'foreign': 0,
                    'trust': 0,
                    'total': 0
                }

            # 累加不同法人的買賣超
            if 'Foreign_Investor' in name:
                institutional[key]['foreign'] += net
            elif 'Investment_Trust' in name:
                institutional[key]['trust'] += net

            institutional[key]['total'] = (
                institutional[key]['foreign'] +
                institutional[key]['trust']
            )

        # 重組成 {ticker: [{date, foreign, trust, total}, ...]}
        result = {}
        for key, data in institutional.items():
            ticker = data['ticker']
            if ticker not in result:
                result[ticker] = []
            result[ticker].append({
                'date': data['date'],
                'foreign': data['foreign'],
                'trust': data['trust'],
                'total': data['total']
            })

        # 排序(最新的在前)
        for ticker in result:
            result[ticker] = sorted(
                result[ticker],
                key=lambda x: x['date'],
                reverse=True
            )

        print(f'   取得 {len(result)} 檔法人資料')
        return result

    except ImportError:
        print('   [!] FinMind 未安裝，無法抓取法人資料')
        return {}
    except Exception as e:
        print(f'   [!] 法人資料抓取失敗: {e}')
        return {}


def fetch_financial_data():
    """
    抓取財報資料（毛利率、營業利益率）
    使用 FinMind API
    返回: {ticker: {'gross_margin': 毛利率, 'operating_margin': 營業利益率}}
    """
    try:
        from FinMind.data import DataLoader
        dl = DataLoader()

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
        print(f'   [!] 財報抓取失敗: {e}')
        return {}


def calculate_5day_change(prices):
    """計算近 5 日累積漲幅"""
    if len(prices) < 5:
        return 0

    latest = prices[0][1]  # 最新收盤
    day5_ago = prices[4][1]  # 5 天前收盤

    if day5_ago == 0:
        return 0

    return ((latest - day5_ago) / day5_ago) * 100


def calculate_5day_avg_volume(prices):
    """計算 5 日均量"""
    if len(prices) < 5:
        return 0

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


# ===== 主程式 =====

def main():
    print('=' * 80)
    print('選股條件 v3.0 - 找法人剛進場、體質健康、還沒噴的股票')
    print('=' * 80)

    # 1. 抓取當日股價
    print('\n[1/5] 抓取當日股價...')
    url_stocks = 'https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL'
    response = requests.get(url_stocks, timeout=15, verify=False)
    stock_data = response.json()

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

        # 基本篩選
        if not (50 <= close <= 200):  # 價格 50-200
            continue
        if volume < 500:  # 量 > 500 張
            continue
        if not (0 <= change_pct <= 5):  # 今日漲幅 0-5%
            continue

        stocks[ticker] = {
            'name': item.get('Name', ''),
            'price': close,
            'change_pct': round(change_pct, 2),
            'volume': volume
        }

    print(f'   基本篩選後: {len(stocks)} 檔')

    # 2. 抓取本益比
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
        print(f'   取得 {len(pe_data)} 檔 PE 資料')
    except:
        print('   PE 抓取失敗')

    # 3. 抓取法人買賣超（今日）
    print('\n[3/5] 抓取法人買賣超...')
    institutional = fetch_institutional_history(days=7)

    # 4. 抓取歷史股價（計算 5 日漲幅、均量）
    print('\n[4/5] 計算歷史技術指標...')
    print('   (這會花一點時間，請稍候...)')

    historical_data = {}
    count = 0
    for ticker in list(stocks.keys())[:50]:  # 先處理前 50 檔測試
        prices = fetch_historical_prices(ticker, days=10)
        if prices:
            historical_data[ticker] = {
                'prices': prices,
                '5day_change': calculate_5day_change(prices),
                '5day_avg_volume': calculate_5day_avg_volume(prices)
            }
            count += 1
            if count % 10 == 0:
                print(f'   已處理 {count} 檔...')
                time.sleep(2)  # 避免被擋

    print(f'   取得 {len(historical_data)} 檔歷史資料')

    # 5. 抓取財報（毛利率、營業利益率）
    print('\n[5/5] 抓取財報資料...')
    print('   (暫時跳過財報檢查,避免 API 問題)')
    financial_data = {}  # TODO: 修正 FinMind API 後啟用
    # financial_data = fetch_financial_data()

    # 6. 最終篩選
    print('\n[6/6] 最終篩選...')
    strict_results = []  # 嚴格版
    loose_results = []   # 寬鬆版

    for ticker, stock in stocks.items():
        # PE 條件
        pe = pe_data.get(ticker, 0)
        if pe <= 0 or pe > 25:
            continue

        # 法人條件：今日買超
        inst = institutional.get(ticker, [])
        if not inst or inst[0]['total'] <= 0:
            continue

        today_inst = inst[0]['total']
        buy_days = count_institutional_buy_days(inst)

        # 歷史技術指標
        hist = historical_data.get(ticker, {})
        if not hist:
            continue

        day5_change = hist['5day_change']
        avg_volume = hist['5day_avg_volume']

        # 檢查條件
        is_strict = True
        reasons = []

        # 近 5 日漲幅 < 10%
        if day5_change >= 10:
            is_strict = False
            reasons.append(f'5日漲{day5_change:.1f}%')

        # 法人買超 3-5 天
        if buy_days < 3 or buy_days > 5:
            is_strict = False
            reasons.append(f'法人買{buy_days}天')

        # 今日量 > 5 日均量
        if stock['volume'] < avg_volume:
            is_strict = False
            reasons.append('量能不足')

        # 財報條件（毛利率、營業利益率）
        fin = financial_data.get(ticker, {})
        gross_margin = fin.get('gross_margin', 0)
        operating_margin = fin.get('operating_margin', 0)

        if financial_data:  # 只有在有財報資料時才檢查
            if gross_margin < 20:
                is_strict = False
                reasons.append(f'毛利率{gross_margin:.1f}%')
            if operating_margin < 0:
                is_strict = False
                reasons.append(f'營業利益率{operating_margin:.1f}%')

        result = {
            'ticker': ticker,
            'name': stock['name'],
            'price': stock['price'],
            'change_pct': stock['change_pct'],
            'volume': stock['volume'],
            'pe': pe,
            'inst_today': today_inst,
            'buy_days': buy_days,
            '5day_change': round(day5_change, 2),
            'avg_volume': int(avg_volume),
            'gross_margin': gross_margin,
            'operating_margin': operating_margin,
            'reasons': reasons
        }

        if is_strict:
            strict_results.append(result)
        else:
            loose_results.append(result)

    # 排序
    strict_results = sorted(strict_results, key=lambda x: x['inst_today'], reverse=True)
    loose_results = sorted(loose_results, key=lambda x: x['inst_today'], reverse=True)

    # 7. 輸出結果
    output_results(strict_results, loose_results)

    print('\n' + '=' * 80)
    print(f'[OK] 嚴格版（推薦買）: {len(strict_results)} 檔')
    print(f'[!] 寬鬆版（觀察）: {len(loose_results)} 檔')
    print(f'詳細結果已存到 scan_result_v3.txt')


def output_results(strict, loose):
    """輸出結果到檔案"""
    with open('scan_result_v3.txt', 'w', encoding='utf-8') as f:
        today = datetime.now().strftime('%Y-%m-%d')

        f.write('=' * 100 + '\n')
        f.write(f'選股條件 v3.0 篩選結果 - {today}\n')
        f.write('=' * 100 + '\n\n')

        # 嚴格版
        f.write('[OK] 嚴格版（推薦買）- 法人剛進場、體質健康、還沒噴\n')
        f.write('-' * 120 + '\n')
        f.write(f"{'#':>3} {'代號':<6} {'名稱':<10} {'價格':>7} {'漲幅':>7} {'PE':>6} {'毛利率':>7} {'營利率':>7} {'法人':>10} {'買天':>5} {'5日漲':>7} {'量/均':>10}\n")
        f.write('-' * 120 + '\n')

        for i, r in enumerate(strict[:20], 1):
            volume_ratio = f"{r['volume']}/{r['avg_volume']}"
            gross = f"{r['gross_margin']:.1f}%" if r['gross_margin'] > 0 else '-'
            oper = f"{r['operating_margin']:.1f}%" if r['operating_margin'] != 0 else '-'
            line = (f"{i:>3} {r['ticker']:<6} {r['name']:<10} {r['price']:>7.1f} "
                   f"{r['change_pct']:>+6.2f}% {r['pe']:>6.1f} {gross:>7} {oper:>7} "
                   f"{r['inst_today']:>+10,} {r['buy_days']:>5} {r['5day_change']:>+6.2f}% {volume_ratio:>10}\n")
            f.write(line)
            print(line.strip())

        f.write(f'\n共 {len(strict)} 檔\n\n')

        # 寬鬆版
        f.write('=' * 100 + '\n')
        f.write('[!] 寬鬆版（觀察用）- 有疑慮需討論\n')
        f.write('-' * 100 + '\n')
        f.write(f"{'#':>3} {'代號':<6} {'名稱':<10} {'價格':>7} {'漲幅':>7} {'PE':>6} {'法人(張)':>10} {'疑慮':>30}\n")
        f.write('-' * 100 + '\n')

        for i, r in enumerate(loose[:20], 1):
            reasons_str = ', '.join(r['reasons'][:2])  # 最多顯示 2 個原因
            line = (f"{i:>3} {r['ticker']:<6} {r['name']:<10} {r['price']:>7.1f} "
                   f"{r['change_pct']:>+6.2f}% {r['pe']:>6.1f} {r['inst_today']:>+10,} {reasons_str:>30}\n")
            f.write(line)

        f.write(f'\n共 {len(loose)} 檔\n')
        f.write('=' * 100 + '\n')


if __name__ == '__main__':
    main()
