"""測試 v3 版本的 scan_all_stocks"""
import sys
sys.path.insert(0, '.')

# 只導入需要的函數
from stock_hunter_v3 import get_all_stocks_data, get_institutional_data, get_market_status, quick_filter, deep_analyze

print("測試 v3 版本...")

# 1. 大盤狀態
market = get_market_status()
print(f"\n大盤: {market}")

# 2. 所有股票
stocks = get_all_stocks_data()
print(f"\n股票數: {len(stocks)}")

# 3. 法人
institutional = get_institutional_data()
print(f"\n法人資料: {len(institutional)} 筆")

# 4. 快速篩選
candidates = quick_filter(stocks, institutional)
print(f"\n通過篩選: {len(candidates)}")
print(f"Top 5: {[(c['ticker'], c['name'], c['score']) for c in candidates[:5]]}")

# 5. 深度分析
recommendations = deep_analyze(candidates)
print(f"\n推薦: {len(recommendations)}")
for rec in recommendations[:3]:
    print(f"  {rec['ticker']} {rec['name']}: {rec['score']}分, {rec['reasons']}")

print("\n✅ 測試完成!")
