from FinMind.data import DataLoader

token = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMS0wNSAyMzowODozMSIsInVzZXJfaWQiOiJhdGl0aSIsImVtYWlsIjoiYXRpdGk0MzYxQGdtYWlsLmNvbSIsImlwIjoiMTExLjI0My4xNDIuOTkifQ.MEcPu8FHrrY2ES1j26NRO9Dg9E2ekEhM4B5rlCPidSI'

api = DataLoader()
api.login_by_token(api_token=token)

# 批量抓取 400+ 天前的營收
df = api.taiwan_stock_month_revenue(start_date='2024-10-01')

print(f'Total rows: {len(df)}')
print(f'Years: {sorted(df["revenue_year"].unique())}')

# 測試 3706 YoY
stock = df[df['stock_id'] == '3706'].sort_values(['revenue_year', 'revenue_month'], ascending=False)
print(f'\n3706 data: {len(stock)} rows')
print(stock[['revenue_year', 'revenue_month', 'revenue']].head(15))

# 算 YoY
if len(stock) >= 2:
    latest = stock.iloc[0]
    latest_month = int(latest['revenue_month'])
    latest_year = int(latest['revenue_year'])
    latest_rev = float(latest['revenue'])
    
    # 找去年同月
    year_ago = stock[(stock['revenue_month'] == latest_month) & (stock['revenue_year'] == latest_year - 1)]
    if not year_ago.empty:
        y_rev = float(year_ago.iloc[0]['revenue'])
        yoy = ((latest_rev - y_rev) / y_rev) * 100
        print(f'\nLatest: {latest_year}/{latest_month}, Rev: {latest_rev:,.0f}')
        print(f'Year ago: {latest_year-1}/{latest_month}, Rev: {y_rev:,.0f}')
        print(f'YoY: {yoy:.2f}%')
    else:
        print('Year ago data not found')
