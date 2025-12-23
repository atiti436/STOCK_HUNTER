import requests
import warnings
warnings.filterwarnings('ignore')

r = requests.get('https://openapi.twse.com.tw/v1/opendata/t187ap03_L', verify=False)
data = r.json()

# 統計所有產業別
industries = {}
for x in data:
    ind = x.get('產業別', '')
    if ind not in industries:
        industries[ind] = []
    industries[ind].append(x.get('公司代號', '') + ' ' + x.get('公司簡稱', ''))

print("=== 所有產業代碼 ===")
for ind in sorted(industries.keys()):
    samples = industries[ind][:3]
    print(f"  產業別 '{ind}': {samples}")
