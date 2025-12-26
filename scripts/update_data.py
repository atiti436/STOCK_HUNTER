#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stock Hunter 資料更新腳本
每天由 GitHub Actions 執行，抓取資料存成 JSON

策略：
1. 法人資料：從 voidful/tw-institutional-stocker 抓現成 JSON
2. 營收資料：用 FinMind 抓

這樣避免 TWSE API 不穩定的問題
"""

import json
import os
import requests
from datetime import datetime, timedelta

# 確保 data 目錄存在
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# GitHub Repo 的 JSON URL
GITHUB_DATA_BASE = "https://raw.githubusercontent.com/voidful/tw-institutional-stocker/main/docs/data"

def save_json(filename, data):
    """儲存 JSON 檔案"""
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ 已儲存: {filename}")

def fetch_institutional_from_github():
    """
    從 voidful/tw-institutional-stocker 抓取法人排行資料
    他每天自動更新，資料來源也是 TWSE，但他幫我們承擔 API 不穩定的風險
    """
    print("📥 從 GitHub 抓取法人排行資料...")
    
    results = {}
    
    for window in [5, 20, 60, 120]:
        for direction in ['up', 'down']:
            url = f"{GITHUB_DATA_BASE}/top_three_inst_change_{window}_{direction}.json"
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                data = response.json()
                results[f'{window}d_{direction}'] = data
                print(f"  ✅ {window}日 {direction}: {len(data)} 筆")
            except Exception as e:
                print(f"  ❌ {window}日 {direction} 失敗: {e}")
                results[f'{window}d_{direction}'] = []
    
    return results

def fetch_stock_timeseries_sample():
    """
    抓幾檔熱門股的時間序列資料（示範）
    """
    print("📥 抓取熱門股時間序列...")
    
    sample_stocks = ['2330', '2454', '2317', '2382', '3231']  # 台積電、聯發科、鴻海、廣達、緯創
    results = {}
    
    for stock_id in sample_stocks:
        url = f"{GITHUB_DATA_BASE}/timeseries/{stock_id}.json"
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            results[stock_id] = response.json()
            print(f"  ✅ {stock_id}")
        except Exception as e:
            print(f"  ❌ {stock_id}: {e}")
    
    return results

def fetch_revenue_from_finmind():
    """
    從 FinMind 抓取營收資料（熱門股）
    """
    print("📥 從 FinMind 抓取營收資料...")
    
    try:
        from FinMind.data import DataLoader
        api = DataLoader()
    except ImportError:
        print("  ❌ FinMind 未安裝")
        return {}
    
    # 熱門股清單
    sample_stocks = ['2330', '2454', '2317', '2382', '3231', '2408', '3661', '2603']
    start_date = (datetime.now() - timedelta(days=400)).strftime('%Y-%m-%d')
    
    results = {}
    
    for stock_id in sample_stocks:
        try:
            df = api.taiwan_stock_month_revenue(stock_id=stock_id, start_date=start_date)
            
            if df.empty or len(df) < 13:
                continue
            
            df = df.sort_values('date')
            latest = df.iloc[-1]
            
            # 計算 YoY
            latest_month = latest['revenue_month']
            latest_year = latest['revenue_year']
            same_month_last_year = df[
                (df['revenue_month'] == latest_month) & 
                (df['revenue_year'] == latest_year - 1)
            ]
            
            if same_month_last_year.empty:
                yoy = 0
            else:
                last_rev = same_month_last_year.iloc[0]['revenue']
                yoy = ((latest['revenue'] - last_rev) / last_rev * 100) if last_rev > 0 else 0
            
            # 計算連續成長
            streak = 0
            revenues = df['revenue'].tolist()
            for i in range(len(revenues) - 1, 0, -1):
                if revenues[i] > revenues[i-1]:
                    streak += 1
                else:
                    break
            
            results[stock_id] = {
                'latest_month': f"{latest_year}-{latest_month:02d}",
                'revenue': int(latest['revenue']),
                'yoy': round(yoy, 1),
                'streak': streak
            }
            print(f"  ✅ {stock_id}: YoY {yoy:.1f}%")
            
        except Exception as e:
            print(f"  ❌ {stock_id}: {e}")
    
    return results


def main():
    print("=" * 50)
    print(f"📊 Stock Hunter 資料更新")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # 1. 從 GitHub 抓法人排行
    institutional_rankings = fetch_institutional_from_github()
    if institutional_rankings:
        save_json('institutional_rankings.json', institutional_rankings)
    
    # 2. 抓熱門股時間序列
    timeseries = fetch_stock_timeseries_sample()
    if timeseries:
        save_json('timeseries_sample.json', timeseries)
    
    # 3. 從 FinMind 抓營收
    revenue = fetch_revenue_from_finmind()
    if revenue:
        save_json('revenue.json', revenue)
    
    # 4. 記錄更新時間
    save_json('last_update.json', {
        'timestamp': datetime.now().isoformat(),
        'institutional_rankings': bool(institutional_rankings),
        'timeseries_sample': len(timeseries) if timeseries else 0,
        'revenue': len(revenue) if revenue else 0
    })
    
    print("=" * 50)
    print("✅ 資料更新完成！")
    print("=" * 50)


if __name__ == '__main__':
    main()
