
# STOCK_HUNTER 主程式 v4.1

import argparse
from datetime import datetime
import pandas as pd
from src.config import CACHE_DIR, REVENUE_CACHE_PATH
from src.fetcher import FinMindFetcher
from src.cache import DataCache, RevenueCache
from src.filter import StockFilter
from src.analysis import (
    calculate_ma, calculate_rsi, calculate_5day_stats,
    calculate_stop_loss, calculate_batch_profit
)
from src.scorer import calculate_score, determine_inst_leader
from src.output import print_table, save_json
import os

def main():
    parser = argparse.ArgumentParser(description='STOCK_HUNTER v4.1')
    parser.add_argument('--offline', action='store_true', help='Use local daily cache')
    parser.add_argument('--date', type=str, help='Target date (YYYY-MM-DD)', default=None)
    args = parser.parse_args()
    
    target_date = args.date if args.date else datetime.now().strftime('%Y-%m-%d')
    print(f"STOCK_HUNTER v4.1 (Rebuild) - Target: {target_date}")
    
    fetcher = FinMindFetcher()
    daily_cache_path = os.path.join(CACHE_DIR, f"daily_{target_date.replace('-','')}.pkl")
    
    # === 1. Prepare Data ===
    
    if args.offline:
        print("[MODE] Offline - Loading Cache...")
        cache_data = DataCache.load(daily_cache_path)
        if not cache_data:
            print(f"[ERROR] No daily cache found for {target_date}. Please run online first.")
            return
        df_daily = cache_data['daily']
        pe_map = cache_data['pe']
        hist_map = cache_data['history']
        inst_map = cache_data['inst']
        rev_map = cache_data['revenue'] # Load snapshot from daily cache
    else:
        print("[MODE] Online - Fetching Data...")
        
        # 1.1 Snapshot
        print(f"   1. Fetching Daily Snapshot ({target_date})...")
        df_daily = fetcher.get_daily_snapshot(date_str=target_date)
        if df_daily is None or df_daily.empty:
            print(f"[ERROR] Failed to fetch daily snapshot for {target_date}")
            return
        print(f"   [INFO] Daily Snapshot Size: {len(df_daily)}")
            
        # 1.2 PE & Revenue (Cache)
        print("   2. Fetching PE & Revenue Cache...")
        pe_map = fetcher.get_pe_data()
        
        rev_cache = RevenueCache(REVENUE_CACHE_PATH)
        rev_map = rev_cache.load()
        if not rev_map:
            print("[WARN] No Revenue Cache found. Run scripts/update_revenue.py first.")
            rev_map = {}
            
        # 1.3 Batch History & Inst
        print("   3. Batch Fetching History (25d) & Inst (10d)...")
        df_hist = fetcher.get_history_batch(days=25)
        df_inst = fetcher.get_institutional_data(days=10)
        
        # Convert DataFrame to Dict for fast access
        # History: {ticker: [(date, close, vol), ...]} (Newest first)
        hist_map = {}
        if df_hist is not None:
            if 'stock_id' not in df_hist.columns:
                print(f"[WARN] df_hist missing stock_id. Columns: {df_hist.columns}")
            else:
                # Sort by date desc
                df_hist = df_hist.sort_values(['stock_id', 'date'], ascending=[True, False])
                # Group by stock_id
                for ticker, group in df_hist.groupby('stock_id'):
                    # Extract list of tuples
                    hist_map[ticker] = list(zip(
                        group['date'], group['close'], group['Trading_Volume']
                    ))
                
        # Inst: {ticker: [{date, foreign, trust, total}, ...]} (Newest first)
        inst_map = {}
        if df_inst is not None:
            if 'stock_id' not in df_inst.columns:
                 print(f"[WARN] df_inst missing stock_id. Columns: {df_inst.columns}")
            else:
                # 轉成 {ticker: {date: {foreign, trust, total}}}
                inst_temp = {}
                for _, row in df_inst.iterrows():
                    tid = row['stock_id']
                    date = row['date']
                    name = row.get('name', '')
                    buy = row.get('buy', 0)
                    sell = row.get('sell', 0)
                    net = (buy - sell) // 1000
                    
                    if tid not in inst_temp: inst_temp[tid] = {}
                    if date not in inst_temp[tid]: inst_temp[tid][date] = {'foreign':0, 'trust':0, 'total':0, 'date': date}
                    
                    if 'Foreign' in name:
                        inst_temp[tid][date]['foreign'] += net
                    elif 'Trust' in name:
                        inst_temp[tid][date]['trust'] += net
                    
                    inst_temp[tid][date]['total'] = inst_temp[tid][date]['foreign'] + inst_temp[tid][date]['trust']
                    
                # Flatten to list
                for tid, dates in inst_temp.items():
                    # Sort by date desc
                    sorted_dates = sorted(dates.values(), key=lambda x: x['date'], reverse=True)
                    inst_map[tid] = sorted_dates
                

            
        # Save Cache
        DataCache.save({
            'daily': df_daily,
            'pe': pe_map,
            'history': hist_map,
            'inst': inst_map,
            'revenue': rev_map
        }, daily_cache_path)
        print(f"   [CACHE] Saved to {daily_cache_path}")

    # === 2. Processing & Screening ===
    print("   4. Screening...")
    
    candidates = []
    
    for _, row in df_daily.iterrows():
        ticker = row['stock_id']
        price = row['close']
        vol = row['Trading_Volume'] // 1000 # 張數
        
        # 0. Basic Filter
        passed, reason = StockFilter.check_basic_criteria(
            ticker, price, vol, pe_map.get(ticker)
        )
        if not passed: 
            # if ticker == '2330': print(f"2330 Failed Basic: {reason}")
            continue
        
        # Prepare Info Object
        stock_info = {
            'ticker': ticker,
            'name': row.get('name', ticker), # FinMind daily 可能沒 name
            'price': price,
            'change_pct': 0, # Calc later
            'volume': vol,
            'pe': pe_map.get(ticker),
        }
        
        # 1. Tech Analysis
        hist_data = hist_map.get(ticker, [])
        if not hist_data: 
            # print(f"{ticker} No Hist Data")
            continue
        
        # hist_data is [(date, close, vol), ...]
        closes = [x[1] for x in hist_data]
        
        # Calc indicators
        ma10 = calculate_ma(closes, 10)
        ma20 = calculate_ma(closes, 20)
        rsi = calculate_rsi(closes)
        chg_5, avg_vol_5 = calculate_5day_stats(hist_data)
        
        # 今日漲幅 (需確保 hist_data[0] 是今日? 或是昨天?)
        # 假設 get_daily_snapshot 抓的是今日
        # 若 hist_data 是到昨天，則需把今日併入
        # 這裡簡化：如果有 daily snapshot，計算相對於昨日的漲跌
        # 但 df_daily 應該有 spread 或 change
        # FinMind: spread (漲跌額), open, high, low, close...
        # change_pct = spread / (close - spread) * 100
        spread = row.get('spread', 0)
        # 若是跌，spread 可能是正值但 row 有 min/max 等? 
        # FinMind spread 總是正值? 不，spread 是漲跌價差
        # 最好自己算：今日收盤 / 昨日收盤
        # 最好自己算：今日收盤 / 昨日收盤
        if len(closes) > 0:
            if hist_data[0][0] == row['date']: # Batch 已經含今日
                if len(closes) > 1:
                    prev_close = closes[1] 
                else:
                    prev_close = price # 只有一天資料，無法算漲跌
            else:
                prev_close = closes[0]
                
            if prev_close == 0:
                change_pct = 0
            else:
                change_pct = ((price - prev_close) / prev_close) * 100
        else:
            change_pct = 0
            
        stock_info['change_pct'] = round(change_pct, 2)
        stock_info['avg_volume'] = avg_vol_5
        stock_info['5day_change'] = chg_5
        stock_info['rsi'] = rsi
        stock_info['ma10'] = ma10
        stock_info['ma20'] = ma20
        
        # Tech Filter
        passed, reason = StockFilter.check_technical_criteria(
            price, change_pct, ma20, rsi, avg_vol_5, vol
        )
        if not passed: 
            # print(f"{ticker} Failed Tech: {reason}")
            continue
        
        # 2. Chip Filter
        inst_data = inst_map.get(ticker, [])
        passed, reason = StockFilter.check_chip_criteria(inst_data)
        if not passed: 
            # print(f"{ticker} Failed Chip: {reason}")
            continue
        
        # 3. Revenue Filter
        rev_data = rev_map.get(ticker, {})
        passed, reason = StockFilter.check_revenue_criteria(rev_data)
        if not passed: 
            # print(f"{ticker} Failed Revenue: {reason}")
            continue
        stock_info['revenue_yoy'] = rev_data.get('yoy')
        
        print(f"[CANDIDATE] {ticker} Passed All Filters!")
        
        # === All Passed ===
        # Calculate Score & Extra Info
        score, reasons = calculate_score(stock_info, inst_data, ma20)
        stop_loss, stop_note = calculate_stop_loss(price, ma10, ma20)
        profit_targets = calculate_batch_profit(price)
        
        stock_info['score'] = score
        stock_info['reasons'] = reasons
        stock_info['stop_loss'] = stop_loss
        stock_info['stop_note'] = stop_note
        stock_info['take_profit'] = profit_targets['batch_2']['price'] # 主目標
        
        # Chip Info
        stock_info['inst_5day'] = sum(d['total'] for d in inst_data[:5])
        stock_info['inst_leader'] = determine_inst_leader(inst_data)
        stock_info['buy_days'] = sum(1 for d in inst_data[:5] if d['total'] > 0)
        
        candidates.append(stock_info)

    # Sort by Score desc
    candidates.sort(key=lambda x: x['score'], reverse=True)
    
    # Output
    print_table(candidates)
    save_json(candidates, date_str=target_date)

if __name__ == "__main__":
    main()
