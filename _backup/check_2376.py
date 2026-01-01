#!/usr/bin/env python3
from FinMind.data import DataLoader
from datetime import datetime, timedelta
dl = DataLoader()

end_date = datetime.now() - timedelta(days=1)
start_date = end_date - timedelta(days=30)

df = dl.taiwan_stock_institutional_investors(stock_id='2376', start_date=start_date.strftime('%Y-%m-%d'), end_date=end_date.strftime('%Y-%m-%d'))

ticker_data = {}
for _, row in df.iterrows():
    date_str = str(row.get('date', '')).replace('-', '')
    name = str(row.get('name', '')).strip()
    buy = int(row.get('buy', 0))
    sell = int(row.get('sell', 0))
    net = (buy - sell) // 1000
    if date_str not in ticker_data:
        ticker_data[date_str] = {'date': date_str, 'f': 0, 't': 0, 'total': 0}
    if 'Foreign_Investor' in name:
        ticker_data[date_str]['f'] += net
    elif 'Investment_Trust' in name:
        ticker_data[date_str]['t'] += net
    ticker_data[date_str]['total'] = ticker_data[date_str]['f'] + ticker_data[date_str]['t']

inst = sorted(ticker_data.values(), key=lambda x: x['date'], reverse=True)

print('技嘉 2376 法人歷史 (最近10天):')
for r in inst[:10]:
    status = 'BUY' if r['total'] > 0 else 'SELL'
    print(f"  {r['date']}: 外資{r['f']:+,} 投信{r['t']:+,} 合計{r['total']:+,} [{status}]")

inst_5day = sum(r['total'] for r in inst[:5])
print(f'\n5日累積: {inst_5day:+,} 張')
print(f'5日累積 > 300: {"PASS" if inst_5day > 300 else "FAIL"}')
