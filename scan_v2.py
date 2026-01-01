#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
選股條件 v2.0 篩選器
目標：找「法人剛進場、還沒漲」的股票

條件：
- PE < 25
- 成交量 > 500 張
- 股價 50-500 元（排除水餃股）
- 排除金融股 (28xx, 58xx)
- 排除 ETF (00xx)
- 法人今日買超
- 今日漲幅 0-5%
"""

import requests
import urllib3
from datetime import datetime, timedelta
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# FinMind for historical data
try:
    from FinMind.data import DataLoader
    FINMIND_AVAILABLE = True
except ImportError:
    FINMIND_AVAILABLE = False
    print('Warning: FinMind not available, skipping historical checks')

def is_excluded_stock(ticker):
    """判斷是否為排除的股票類型"""
    # 金融股 (28xx, 58xx) - 不適合短波段
    if ticker.startswith('28') or ticker.startswith('58'):
        return True
    # 營建股 (25xx) - 收款週期長，不適合短波段
    if ticker.startswith('25'):
        return True
    return False

def main():
    print('=' * 70)
    print('選股條件 v2.0 - 找法人剛進場、還沒漲的股票')
    print('=' * 70)
    
    # 1. 抓取當日股價
    print('\n[1/4] 抓取當日股價...')
    url_stocks = 'https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL'
    response = requests.get(url_stocks, timeout=15, verify=False)
    stock_data = response.json()
    
    stocks = {}
    for item in stock_data:
        ticker = item.get('Code', '')
        if not (ticker.isdigit() and len(ticker) == 4):
            continue
        if ticker.startswith('00'):  # 排除 ETF
            continue
        if is_excluded_stock(ticker):  # 排除金融股、營建股
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
        
        # 基本篩選（排除水餃股）
        if not (50 <= close <= 500):
            continue
        if volume < 500:
            continue
        if not (0 <= change_pct <= 5):
            continue
        
        stocks[ticker] = {
            'name': item.get('Name', ''),
            'price': close,
            'change_pct': round(change_pct, 2),
            'volume': volume
        }
    
    print(f'   基本篩選後: {len(stocks)} 檔')
    
    # 2. 抓取法人資料
    print('\n[2/4] 抓取法人買賣超...')
    institutional = {}
    inst_date = ''
    
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
                print(f'   法人資料日期: {date_str}')
                break
        except:
            continue
    
    # 3. 抓取本益比
    print('\n[3/4] 抓取本益比...')
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
    
    # 4. 最終篩選
    print('\n[4/4] 最終篩選...')
    results = []
    
    for ticker, stock in stocks.items():
        # 法人條件：今日買超
        inst = institutional.get(ticker, {})
        total_inst = inst.get('total', 0)
        if total_inst <= 0:
            continue
        
        # PE 條件：< 25
        pe = pe_data.get(ticker, 0)
        if pe <= 0 or pe > 25:
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
    
    # 排序：按法人買超張數
    results = sorted(results, key=lambda x: x['total_inst'], reverse=True)
    
    # 輸出
    print('\n' + '=' * 70)
    print(f'篩選結果 ({inst_date}) - 排除金融股，PE<25，法人買超，漲幅0-5%')
    print('=' * 70)
    
    with open('scan_result_v2.txt', 'w', encoding='utf-8') as f:
        header = f"{'#':>3} {'代號':<6} {'名稱':<10} {'價格':>7} {'漲幅':>7} {'外資(張)':>12} {'投信(張)':>12} {'PE':>6}\n"
        f.write('=' * 80 + '\n')
        f.write(f'選股條件 v2.0 篩選結果 - {inst_date}\n')
        f.write('條件：排除金融股、PE<25、法人買超、漲幅0-5%、量>500張\n')
        f.write('=' * 80 + '\n\n')
        f.write(header)
        f.write('-' * 80 + '\n')
        
        for i, r in enumerate(results[:30], 1):
            line = f"{i:>3} {r['ticker']:<6} {r['name']:<10} {r['price']:>7.1f} {r['change_pct']:>+6.2f}% {r['foreign']:>+12,} {r['trust']:>+12,} {r['pe']:>6.1f}\n"
            f.write(line)
            print(line.strip())
        
        f.write('\n' + '=' * 80 + '\n')
        f.write(f'共 {len(results)} 檔符合條件\n')
    
    print('\n' + '=' * 70)
    print(f'共 {len(results)} 檔符合條件')
    print(f'詳細結果已存到 scan_result_v2.txt')

if __name__ == '__main__':
    main()
