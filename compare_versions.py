#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V4 vs V5 vs V6 vs V6* 版本比較"""

import json

with open('data/raw/2026-01-09_0120_candidates.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

stocks = data['stocks']
print(f'=== 1/9 完整候選: {len(stocks)} 檔 ===\n')

v4, v5, v6, v6s = [], [], [], []

for s in stocks:
    t, p, d5, yoy, bd, i5 = s['ticker'], s['price'], s.get('5day_change',0), s.get('revenue_yoy',0), s.get('buy_days',0), s.get('inst_5day',0)
    base = (30 <= p <= 300) and (bd >= 2) and (i5 > 300)
    
    if base and (d5 < 10) and (yoy > 0): v4.append(s)
    if (90 <= p <= 300) and (d5 < 15) and (bd >= 2) and (i5 > 300): v5.append(s)
    if base and (d5 < 5) and (yoy > 0): v6.append(s)
    if base and (d5 < 5): v6s.append(s)

print('【選股數量】')
print(f'V4 (穩健): {len(v4):2} 檔  | 5日<10%, YoY>0')
print(f'V5 (寬鬆): {len(v5):2} 檔  | 5日<15%, 無YoY')  
print(f'V6 (嚴格): {len(v6):2} 檔  | 5日<5%, YoY>0')
print(f'V6*(短線): {len(v6s):2} 檔  | 5日<5%, 無YoY')
print()

def show(name, lst):
    print(f'\n--- {name}: {len(lst)} 檔 ---')
    for s in sorted(lst, key=lambda x: x.get('inst_5day',0), reverse=True)[:8]:
        print(f"{s['ticker']} {s.get('name','')[:4]:4} {s['price']:6.1f} 5日:{s.get('5day_change',0):+5.1f}% YoY:{s.get('revenue_yoy',0):+5.1f}% 法人:{s.get('inst_5day',0):>5}")

show('V4', v4)
show('V5', v5)
show('V6', v6)
show('V6*', v6s)

# 被 YoY 誤殺
killed = [s for s in v6s if s not in v6]
if killed:
    print(f'\n=== 被YoY誤殺 ({len(killed)}檔) ===')
    for s in killed:
        print(f"{s['ticker']} {s.get('name','')[:4]:4} 5日:{s.get('5day_change',0):+5.1f}% YoY:{s.get('revenue_yoy',0):+5.1f}%")
