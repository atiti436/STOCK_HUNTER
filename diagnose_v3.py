#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
診斷腳本：找出 scan_v3.py 到底卡在哪個條件
"""

import requests
import urllib3
from datetime import datetime, timedelta
from FinMind.data import DataLoader
import time

urllib3.disable_warnings()

def main():
    print('=' * 60)
    print('選股條件 v3.2 診斷')
    print('=' * 60)
    
    dl = DataLoader()
    
    # 1. 抓取當日股價
    print('\n[1] 抓取當日股價...')
    url = 'https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL'
    r = requests.get(url, timeout=15, verify=False)
    data = r.json()
    
    stocks = {}
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
        
        if close <= 0:
            continue
        
        stocks[ticker] = {
            'name': item.get('Name', ''),
            'price': close,
            'change_pct': pct,
            'volume': volume
        }
    
    print(f'   總股票: {len(stocks)}')
    
    # 2. 價格篩選
    step1 = [t for t, s in stocks.items() if 30 <= s['price'] <= 300]
    print(f'\n[2] 價格 30-300: {len(step1)} 檔')
    
    # 3. 漲幅篩選
    step2 = [t for t in step1 if 0 <= stocks[t]['change_pct'] <= 5]
    print(f'[3] + 漲幅 0-5%: {len(step2)} 檔')
    
    # 4. 成交量篩選
    step3 = [t for t in step2 if stocks[t]['volume'] >= 800]
    print(f'[4] + 成交量 > 800: {len(step3)} 檔')
    
    # 5. PE 篩選
    print('\n[5] 抓取 PE...')
    url_pe = 'https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL'
    r = requests.get(url_pe, timeout=15, verify=False)
    pe_data = {}
    for item in r.json():
        ticker = item.get('Code', '')
        pe_str = item.get('PEratio', '')
        if ticker and pe_str:
            try:
                pe_data[ticker] = float(pe_str)
            except:
                pass
    
    step4 = [t for t in step3 if 0 < pe_data.get(t, 0) < 35]
    print(f'   + PE < 35: {len(step4)} 檔')
    
    # 6. 法人篩選 (只測試前 10 檔)
    print(f'\n[6] 抓取法人 (只測 10 檔)...')
    test_tickers = step4[:10]
    
    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=30)
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')
    
    passed = []
    for ticker in test_tickers:
        try:
            df = dl.taiwan_stock_institutional_investors(
                stock_id=ticker,
                start_date=start_str,
                end_date=end_str
            )
            
            if df is None or df.empty:
                print(f'   {ticker}: 無法人資料')
                continue
            
            # 整理每日買賣超
            daily = {}
            for _, row in df.iterrows():
                date = str(row.get('date', ''))
                name = str(row.get('name', ''))
                buy = int(row.get('buy', 0))
                sell = int(row.get('sell', 0))
                net = (buy - sell) // 1000
                
                if date not in daily:
                    daily[date] = 0
                if 'Foreign' in name or 'Trust' in name:
                    daily[date] += net
            
            sorted_dates = sorted(daily.keys(), reverse=True)
            
            # 計算連續買超天數
            buy_streak = 0
            for d in sorted_dates:
                if daily[d] > 0:
                    buy_streak += 1
                else:
                    break
            
            # 計算 5 日累積
            inst_5d = sum(daily.get(d, 0) for d in sorted_dates[:5])
            
            # 判斷
            reason = []
            if buy_streak < 2:
                reason.append(f'連買{buy_streak}天<2')
            if buy_streak > 7:
                reason.append(f'連買{buy_streak}天>7')
            if inst_5d < 300:
                reason.append(f'5日{inst_5d}張<300')
            
            if reason:
                print(f'   {ticker}: ❌ {", ".join(reason)}')
            else:
                print(f'   {ticker}: ✅ 連買{buy_streak}天, 5日{inst_5d}張')
                passed.append(ticker)
            
            time.sleep(0.3)
            
        except Exception as e:
            print(f'   {ticker}: 錯誤 {e}')
    
    print(f'\n[結果] {len(passed)}/{len(test_tickers)} 檔通過法人篩選')
    if passed:
        print(f'   通過: {passed}')

if __name__ == '__main__':
    main()
