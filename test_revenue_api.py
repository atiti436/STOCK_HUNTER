#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試 FinMind 營收 API
"""

from FinMind.data import DataLoader
from datetime import datetime, timedelta

dl = DataLoader()

print('=' * 80)
print('測試 FinMind 營收 API')
print('=' * 80)

# 測試 1: 抓緯創營收
print('\n[測試 1] 抓取緯創 (3231) 最近 3 個月營收...')
try:
    # 計算日期範圍 (最近 400 天，涵蓋 1 年多，才能比對 YoY)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=400)

    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')

    print(f'   日期範圍: {start_str} ~ {end_str}')

    df = dl.taiwan_stock_month_revenue(
        stock_id='3231',
        start_date=start_str,
        end_date=end_str
    )

    if df is None or df.empty:
        print('   [X] 無資料')
    else:
        print(f'   [OK] 成功! 取得 {len(df)} 筆資料')
        print('\n   欄位:')
        print(f'   {list(df.columns)}')
        print('\n   最新 3 筆:')
        print(df.head(3).to_string())

        # 測試計算 YoY (需要抓更長資料才能比對去年同期)
        if len(df) >= 1:
            latest = df.iloc[-1]  # 最新的一筆
            latest_month = latest.get('revenue_month')
            latest_year = latest.get('revenue_year')
            latest_revenue = float(latest.get('revenue', 0))

            print(f'\n   最新營收: {latest_year} 年 {latest_month} 月 = {latest_revenue / 1000000000:.2f} 億')

            # 找去年同期 (month 相同, year - 1)
            year_ago_data = df[(df['revenue_month'] == latest_month) & (df['revenue_year'] == latest_year - 1)]

            if not year_ago_data.empty:
                year_ago_revenue = float(year_ago_data.iloc[0]['revenue'])
                yoy = ((latest_revenue - year_ago_revenue) / year_ago_revenue) * 100
                print(f'   去年同期: {year_ago_revenue / 1000000000:.2f} 億')
                print(f'   [OK] YoY 成長率: {yoy:+.2f}%')
            else:
                print('   [!] 無去年同期資料 (需抓更長時間)')

except Exception as e:
    print(f'   [!] 失敗: {e}')

# 測試 2: 抓神達營收
print('\n[測試 2] 抓取神達 (3706) 營收...')
try:
    df = dl.taiwan_stock_month_revenue(
        stock_id='3706',
        start_date=start_str,
        end_date=end_str
    )

    if df is None or df.empty:
        print('   [X] 無資料')
    else:
        print(f'   [OK] 成功! 取得 {len(df)} 筆資料')

        latest = df.iloc[-1]
        latest_month = latest.get('revenue_month')
        latest_year = latest.get('revenue_year')
        latest_revenue = float(latest.get('revenue', 0))

        print(f'   最新營收: {latest_year} 年 {latest_month} 月 = {latest_revenue / 1000000000:.2f} 億')

        # 找去年同期
        year_ago_data = df[(df['revenue_month'] == latest_month) & (df['revenue_year'] == latest_year - 1)]

        if not year_ago_data.empty:
            year_ago_revenue = float(year_ago_data.iloc[0]['revenue'])
            yoy = ((latest_revenue - year_ago_revenue) / year_ago_revenue) * 100
            print(f'   去年同期: {year_ago_revenue / 1000000000:.2f} 億')
            print(f'   [OK] YoY 成長率: {yoy:+.2f}%')
        else:
            print('   [!] 無去年同期資料')

except Exception as e:
    print(f'   [!] 失敗: {e}')

print('\n' + '=' * 80)
print('測試完成')
print('=' * 80)
