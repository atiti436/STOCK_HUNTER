import requests
import urllib3
urllib3.disable_warnings()

# TWSE API 測試
url = 'https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY_ALL'
headers = {'User-Agent': 'Mozilla/5.0'}

print('測試 TWSE API...')
r = requests.get(url, headers=headers, timeout=20, verify=False)
print(f'Status: {r.status_code}')

if r.status_code == 200:
    data = r.json()
    if 'data' in data:
        print(f"股票數: {len(data['data'])}")
        print(f"範例: {data['data'][0][:3]}")
    else:
        print(f"無 data 欄位: {data.get('stat')}")
        print(f"回傳: {r.text[:300]}")
else:
    print(f"失敗: {r.text[:200]}")
