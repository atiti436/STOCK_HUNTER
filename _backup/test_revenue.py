#!/usr/bin/env python3
# 深入診斷營收抓取問題

from FinMind.data import DataLoader
from datetime import datetime, timedelta

token = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMS0wNSAyMzowODozMSIsInVzZXJfaWQiOiJhdGl0aSIsImVtYWlsIjoiYXRpdGk0MzYxQGdtYWlsLmNvbSIsImlwIjoiMTExLjI0My4xNDIuOTkifQ.MEcPu8FHrrY2ES1j26NRO9Dg9E2ekEhM4B5rlCPidSI'

dl = DataLoader()
dl.login_by_token(api_token=token)

# 測試 420 天範圍
end = datetime.now()
start = end - timedelta(days=420)
print(f'Testing: {start.strftime("%Y-%m-%d")} to now')

df = dl.taiwan_stock_month_revenue(start_date=start.strftime('%Y-%m-%d'))
print(f'Total rows: {len(df) if df is not None else 0}')

if df is not None and not df.empty:
    # 統計資料
    print(f'\nRevenue years in data: {sorted(df["revenue_year"].unique())}')
    print(f'Revenue months coverage:')
    for year in sorted(df['revenue_year'].unique()):
        months = sorted(df[df['revenue_year'] == year]['revenue_month'].unique())
        print(f'  {year}: {months}')
    
    # 測試 2330 YoY 計算
    print('\n--- Testing YoY calculation for 2330 ---')
    stock = df[df['stock_id'] == '2330'].sort_values(['revenue_year', 'revenue_month'], ascending=False)
    print(stock[['stock_id', 'revenue_year', 'revenue_month', 'revenue']])
    
    if len(stock) >= 2:
        latest = stock.iloc[0]
        latest_month = int(latest['revenue_month'])
        latest_year = int(latest['revenue_year'])
        latest_rev = float(latest['revenue'])
        
        print(f'\nLatest: {latest_year}/{latest_month}, Revenue: {latest_rev:,.0f}')
        
        # 找去年同月
        year_ago = stock[(stock['revenue_month'] == latest_month) & (stock['revenue_year'] == latest_year - 1)]
        if not year_ago.empty:
            y_rev = float(year_ago.iloc[0]['revenue'])
            yoy = ((latest_rev - y_rev) / y_rev) * 100
            print(f'Year ago: {latest_year-1}/{latest_month}, Revenue: {y_rev:,.0f}')
            print(f'YoY: {yoy:.2f}%')
        else:
            print('ERROR: Year ago data not found!')
else:
    print('No data returned')
