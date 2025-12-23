#!/usr/bin/env python3
"""測試達明流動性警示"""

from stock_hunter_v3 import get_stock_history

h = get_stock_history('4585', 10)
print('達明最近成交量:')
for d in h[-5:]:
    print(f"{d['date']}: {d['volume']}張")
