#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V4 vs V5 vs V6 vs V6* vs V7 版本比較"""

import json
import sys

# 允許指定日期檔案
date_file = sys.argv[1] if len(sys.argv) > 1 else 'data/raw/2026-01-16_2125_candidates.json'

with open(date_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

stocks = data['stocks']
print(f'=== {data.get("date", "?")} 完整候選: {len(stocks)} 檔 ===\n')

v4, v5, v6, v6s, v7 = [], [], [], [], []

for s in stocks:
    t = s['ticker']
    p = s['price']
    d5 = s.get('5day_change', 0)
    yoy = s.get('revenue_yoy', 0)
    bd = s.get('buy_days', 0)
    i5 = s.get('inst_5day', 0)
    chg = s.get('change_pct', 0)
    rsi = s.get('rsi', 50)
    ma5 = s.get('ma5', 0)
    ma10 = s.get('ma10', 0)
    ma20 = s.get('ma20', 0)
    
    # 共同條件
    base = (30 <= p <= 300) and (bd >= 2) and (i5 > 300)
    
    # V4: 穩健版
    if base and (d5 < 10) and (yoy > 0):
        v4.append(s)
    
    # V5: 寬鬆版 (90-300, 5日<15%)
    if (90 <= p <= 300) and (d5 < 15) and (bd >= 2) and (i5 > 300):
        v5.append(s)
    
    # V6: 嚴格版 (5日<5%, YoY>0)
    if base and (d5 < 5) and (yoy > 0):
        v6.append(s)
    
    # V6*: 短線版 (5日<5%, 不管YoY)
    if base and (d5 < 5):
        v6s.append(s)
    
    # V7: 狙擊手版 (Daily Dip)
    # 今日跌 -4%~0%, 法人5日>500, RSI<70, 5日 -5%~5%
    # 均線多頭 MA10>MA20, 接近支撐 (乖離<2%)
    bias_ma10 = ((p - ma10) / ma10 * 100) if ma10 > 0 else 999
    bias_ma20 = ((p - ma20) / ma20 * 100) if ma20 > 0 else 999
    near_support = abs(bias_ma10) < 2 or abs(bias_ma20) < 2
    ma_bullish = ma10 > ma20 if (ma10 > 0 and ma20 > 0) else False
    
    v7_cond = (
        (30 <= p <= 300) and
        (-4 <= chg <= 0) and           # 今日跌
        (i5 > 500) and                  # 法人5日加強
        (rsi < 70) and                  # 不過熱
        (-5 <= d5 <= 5) and             # 橫盤或小回檔
        near_support and                # 接近支撐
        ma_bullish                      # 均線多頭
    )
    if v7_cond:
        v7.append(s)

print('【選股數量】')
print(f'V4 (穩健): {len(v4):2} 檔  | 5日<10%, YoY>0')
print(f'V5 (寬鬆): {len(v5):2} 檔  | 5日<15%, 無YoY')  
print(f'V6 (嚴格): {len(v6):2} 檔  | 5日<5%, YoY>0')
print(f'V6*(短線): {len(v6s):2} 檔  | 5日<5%, 無YoY')
print(f'V7 (狙擊): {len(v7):2} 檔  | 今日跌, 近支撐, 主力在')
print()

def show(name, lst, max_show=8):
    print(f'\n--- {name}: {len(lst)} 檔 ---')
    for s in sorted(lst, key=lambda x: x.get('inst_5day',0), reverse=True)[:max_show]:
        print(f"{s['ticker']} {s.get('name','')[:4]:4} {s['price']:6.1f} "
              f"今日:{s.get('change_pct',0):+5.2f}% 5日:{s.get('5day_change',0):+5.1f}% "
              f"YoY:{s.get('revenue_yoy',0):+5.1f}% 法人:{s.get('inst_5day',0):>5}")

def show_v7(lst, max_show=8):
    """V7 專用顯示：包含支撐價位"""
    print(f'\n--- V7 (狙擊手): {len(lst)} 檔 ---')
    for s in sorted(lst, key=lambda x: x.get('inst_5day',0), reverse=True)[:max_show]:
        p = s['price']
        ma10, ma20 = s.get('ma10', 0), s.get('ma20', 0)
        rsi = s.get('rsi', 50)
        # 計算建議買入區間：MA20 ~ 現價
        buy_low = min(ma10, ma20) if ma10 > 0 and ma20 > 0 else p * 0.97
        buy_high = p
        print(f"{s['ticker']} {s.get('name','')[:4]:4} {p:6.1f} "
              f"今日:{s.get('change_pct',0):+5.2f}% RSI:{rsi:.0f} "
              f"MA10:{ma10:.1f} MA20:{ma20:.1f} 📍買入:{buy_low:.0f}-{buy_high:.0f}")

show('V4', v4)
show('V5', v5)
show('V6', v6)
show('V6*', v6s)
show_v7(v7)

# V7 獨有 (其他版本沒選)
v7_only = [s for s in v7 if s not in v6 and s not in v6s and s not in v4]
if v7_only:
    print(f'\n=== 🎯 V7 Only ({len(v7_only)}檔) - 其他版本沒選 ===')
    for s in v7_only:
        p = s['price']
        ma10, ma20 = s.get('ma10', 0), s.get('ma20', 0)
        rsi = s.get('rsi', 50)
        buy_low = min(ma10, ma20) if ma10 > 0 and ma20 > 0 else p * 0.97
        print(f"{s['ticker']} {s.get('name','')[:4]:4} {p:6.1f} "
              f"今日:{s.get('change_pct',0):+5.2f}% RSI:{rsi:.0f} "
              f"MA10:{ma10:.1f} MA20:{ma20:.1f} 📍買入:{buy_low:.0f}-{p:.0f}")

# 被 YoY 誤殺
killed = [s for s in v6s if s not in v6]
if killed:
    print(f'\n=== 被YoY誤殺 ({len(killed)}檔) ===')
    for s in killed:
        print(f"{s['ticker']} {s.get('name','')[:4]:4} 5日:{s.get('5day_change',0):+5.1f}% YoY:{s.get('revenue_yoy',0):+5.1f}%")

# ===== B 格式輸出 (LINE 推送用) =====
def get_version_label(s, v4_set, v5_set, v6_set, v6s_set, v7_set):
    """產生版本標籤字串"""
    t = s['ticker']
    versions = []
    if t in v4_set: versions.append('V4')
    if t in v5_set: versions.append('V5')
    if t in v6_set: versions.append('V6')
    if t in v6s_set: versions.append('V6*')
    if t in v7_set: versions.append('V7')
    
    if len(versions) >= 4:
        return '⟨全過⟩'
    elif len(versions) == 0:
        return ''
    else:
        return '⟨' + ' '.join(versions) + '⟩'

def generate_lite_output(v4, v5, v6, v6s, v7, date_str):
    """產生 B 格式清單式輸出 (LINE 推送用)"""
    # 建立 ticker set 方便查詢
    v4_set = {s['ticker'] for s in v4}
    v5_set = {s['ticker'] for s in v5}
    v6_set = {s['ticker'] for s in v6}
    v6s_set = {s['ticker'] for s in v6s}
    v7_set = {s['ticker'] for s in v7}
    
    # 合併所有股票，按版本數量排序
    all_tickers = {}
    for lst in [v4, v5, v6, v6s, v7]:
        for s in lst:
            t = s['ticker']
            if t not in all_tickers:
                all_tickers[t] = s
    
    # 計算每檔股票通過幾個版本
    def count_versions(s):
        t = s['ticker']
        cnt = 0
        if t in v4_set: cnt += 1
        if t in v5_set: cnt += 1
        if t in v6_set: cnt += 1
        if t in v6s_set: cnt += 1
        if t in v7_set: cnt += 1
        return cnt
    
    # 排序：版本數 > 法人買超
    sorted_stocks = sorted(all_tickers.values(), 
                          key=lambda x: (count_versions(x), x.get('inst_5day', 0)), 
                          reverse=True)
    
    lines = []
    lines.append(f"📊 {date_str} 選股")
    lines.append("")
    
    for s in sorted_stocks:
        t = s['ticker']
        
        # 如果只有 V7 通過，跳過（會在底下狙擊區顯示）
        is_v7_only = (t in v7_set and t not in v4_set and t not in v5_set and t not in v6_set and t not in v6s_set)
        if is_v7_only:
            continue
        
        name = s.get('name', '')[:4]
        price = s['price']
        label = get_version_label(s, v4_set, v5_set, v6_set, v6s_set, v7_set)
        
        # 法人資訊
        buy_days = s.get('buy_days', 0)
        inst_5day = s.get('inst_5day', 0)
        
        # ATR 計算停損停利 (簡化版)
        atr = s.get('atr', price * 0.03)  # 預設 3%
        stop = round(price - 2 * atr)
        target = round(price + 2 * atr)
        entry_low = round(price - 0.5 * atr)
        
        # 版本數決定 emoji
        vcnt = count_versions(s)
        if vcnt >= 4:
            emoji = '🏆'
        elif vcnt >= 2:
            emoji = '⭐'
        elif t in v7_set:
            emoji = '🎯'
        else:
            emoji = '📋'
        
        # 新聞行 (需要手動補充，這裡用 YoY 或標籤代替)
        yoy = s.get('revenue_yoy', 0)
        if yoy > 10:
            news = f"YoY+{yoy:.0f}%"
        elif yoy > 0:
            news = f"YoY+{yoy:.1f}%"
        else:
            news = ""
        
        # 輸出格式
        lines.append(f"{emoji} {name} {t} ${price:.0f} {label}")
        inst_info = f"外資連{buy_days}買" if buy_days >= 2 else f"法人+{inst_5day}張"
        if news:
            lines.append(f"   {inst_info}｜{news}")
        else:
            lines.append(f"   {inst_info}")
        lines.append(f"   💵{entry_low}~{price:.0f}｜🛡️{stop}｜🎯{target}")
        lines.append("")
    
    # V7 狙擊區塊 (只顯示 V7 獨有的)
    v7_only = [s for s in v7 if s['ticker'] not in v4_set and s['ticker'] not in v6_set and s['ticker'] not in v6s_set]
    if v7_only:
        lines.append("─── V7 狙擊 ───")
        lines.append("")
        for s in v7_only:
            t = s['ticker']
            name = s.get('name', '')[:4]
            price = s['price']
            rsi = s.get('rsi', 50)
            ma10, ma20 = s.get('ma10', 0), s.get('ma20', 0)
            buy_low = min(ma10, ma20) if ma10 > 0 and ma20 > 0 else price * 0.97
            lines.append(f"🎯 {name} {t} ${price:.0f} ⟨V7⟩RSI{rsi:.0f}")
            lines.append(f"   💵{buy_low:.0f}~{price:.0f}")
            lines.append("")
    
    return '\n'.join(lines)

# 產生並儲存 B 格式
date_str = data.get('date', '?')
lite_output = generate_lite_output(v4, v5, v6, v6s, v7, date_str)
print('\n' + '='*50)
print('📱 極簡行動卡 (B格式)')
print('='*50)
print(lite_output)

# 儲存到檔案
with open('scan_result_lite.txt', 'w', encoding='utf-8') as f:
    f.write(lite_output)
print(f'\n✅ 已儲存到 scan_result_lite.txt')
