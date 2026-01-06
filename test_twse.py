import requests
import urllib3
urllib3.disable_warnings()

url = 'https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL'
r = requests.get(url, timeout=15, verify=False)
data = r.json()

print(f'Total: {len(data)} stocks')
print(f'Date: {data[0].get("Date", "")}')

# 找 2233
for item in data:
    if item.get('Code') == '2233':
        print(f'2233: Date={item.get("Date")}, Close={item.get("ClosingPrice")}, Change={item.get("Change")}')
        break
