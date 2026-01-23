#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多版本選股掃描器 - 整合 BASE + V4/V5/V6/V7/V9
目標：一次掃描產生所有版本結果

架構：
1. BASE 硬門檻 (1700股 → ~65股候選)
2. 同時套用 V4/V5/V6/V6*/V7/V9 篩選邏輯
3. 產生完整報告 + LINE 小卡

使用方式：
  python scan_all_versions.py                    # 完整掃描（呼叫 API）
  python scan_all_versions.py --dry-run          # 乾測試（讀取最新 candidates.json）
  python scan_all_versions.py --date 2026-01-22  # 指定日期的 candidates.json
"""

import os
import json
import sys
import argparse
from datetime import datetime
from pathlib import Path

# 解析命令列參數
parser = argparse.ArgumentParser(description='多版本選股掃描器')
parser.add_argument('--dry-run', action='store_true', help='乾測試模式：讀取最新的 candidates.json 而不呼叫 API')
parser.add_argument('--date', type=str, help='指定日期 (YYYY-MM-DD)，讀取該日期的 candidates.json')
ARGS = parser.parse_args()

# ===== 乾測試模式：讀取 candidates.json =====
if ARGS.dry_run or ARGS.date:
    print('=' * 60)
    print('[DRY RUN] 乾測試模式：讀取現有 candidates.json')
    print('=' * 60)

    # 尋找最新的 candidates.json
    raw_dir = Path('d:/claude-project/STOCK_HUNTER/data/raw')

    if ARGS.date:
        # 指定日期
        pattern = f"{ARGS.date}*candidates.json"
        candidates_files = sorted(raw_dir.glob(pattern), reverse=True)
    else:
        # 最新檔案
        candidates_files = sorted(raw_dir.glob('*_candidates.json'), reverse=True)

    if not candidates_files:
        print('❌ 找不到 candidates.json 檔案')
        sys.exit(1)

    candidates_file = candidates_files[0]
    print(f'[FILE] 讀取檔案: {candidates_file.name}')

    with open(candidates_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    stocks = data['stocks']
    date_str = data.get('date', '?')
    count = len(stocks)

    print(f'[DATA] 日期: {date_str}')
    print(f'[DATA] 候選數: {count} 檔')
    print()

# ===== 如果不是乾測試，則執行完整掃描 =====
else:
    print('=' * 60)
    print('[FULL SCAN] 完整掃描模式（呼叫 API）')
    print('=' * 60)
    print()

    # 步驟 1: 執行 scan_20260106.py 產生 candidates.json
    print('[1/2] 執行 BASE 篩選（產生候選池）...')
    import subprocess

    script_dir = Path(__file__).parent
    scan_script = script_dir / 'scan_20260106.py'

    if not scan_script.exists():
        print(f'❌ 找不到 scan_20260106.py: {scan_script}')
        sys.exit(1)

    # 執行掃描程式（只產生 candidates.json，不做後續篩選）
    # 注意：scan_20260106.py 會執行完整流程，包括 V7/V9 篩選
    # 但我們只需要它產生的 candidates.json
    try:
        result = subprocess.run(
            ['python', str(scan_script)],
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        # 顯示輸出的前幾行（確認有執行）
        output_lines = result.stdout.split('\n')[:20]
        for line in output_lines:
            if line.strip():
                print(f'  {line}')
        print('  ...')
        print()
    except subprocess.CalledProcessError as e:
        print(f'❌ 執行 scan_20260106.py 失敗')
        print(f'錯誤訊息: {e.stderr}')
        sys.exit(1)

    # 步驟 2: 讀取產生的 candidates.json
    print('[2/2] 讀取候選池資料...')
    raw_dir = Path('d:/claude-project/STOCK_HUNTER/data/raw')

    # 尋找最新的 candidates.json
    candidates_files = sorted(raw_dir.glob('*_candidates.json'), reverse=True)

    if not candidates_files:
        print('❌ 找不到 candidates.json 檔案')
        sys.exit(1)

    candidates_file = candidates_files[0]
    print(f'[FILE] 讀取檔案: {candidates_file.name}')

    with open(candidates_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    stocks = data['stocks']
    date_str = data.get('date', '?')
    count = len(stocks)

    print(f'[DATA] 日期: {date_str}')
    print(f'[DATA] 候選數: {count} 檔')
    print()
    print('=' * 60)
    print()

# ===== Part 2: 多版本篩選邏輯 (複製自 compare_versions_v7.py) =====
print('[1/3] 套用多版本篩選邏輯...')

v4, v5, v6, v6s, v7, v8, v7s = [], [], [], [], [], [], []
v5_with_score = []  # V5 + 評分系統

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

    # KD 值
    k9 = s.get('k9', None)
    d9 = s.get('d9', None)

    # 共同條件
    base = (30 <= p <= 300) and (bd >= 2) and (i5 > 300)

    # V4: 穩健版
    if base and (d5 < 10) and (yoy > 0):
        v4.append(s)

    # V5: 寬鬆版 (90-300, 5日<15%) + 評分系統
    if (90 <= p <= 300) and (d5 < 15) and (bd >= 2) and (i5 > 300):
        v5.append(s)

        # === V5 評分系統 (完整版) ===
        score = 0
        score_reasons = []
        tags = []

        avg_vol = s.get('avg_volume', 1000)
        vol = s.get('volume', 0)
        margin_3d = s.get('margin_3day_change', 0)
        short_3d = s.get('short_3day_change', 0)
        is_margin_dec = s.get('is_margin_decrease', False)
        is_short_inc = s.get('is_short_increase', False)

        # 計算 MA20 乖離
        bias_ma20 = ((p - ma20) / ma20 * 100) if ma20 > 0 else 0

        # 標籤判定
        if d5 >= 10:
            tags.append('[已漲]')
        if vol < avg_vol:
            tags.append('[整理]')
        if bias_ma20 > 1 and chg > 0:
            tags.append('[攻擊]')
        if ma5 is not None and ma10 is not None and ma5 > ma10:
            tags.append('[多頭]')

        # 投信數據
        trust_today = s.get('trust_today', 0)
        trust_5day = s.get('trust_5day', 0)
        foreign_5day = s.get('foreign_5day', 0)
        trust_buy_days = s.get('trust_buy_days', 0)

        # 投信標籤
        if trust_today > 0:
            tags.append('[投信]')
        if trust_5day > foreign_5day and trust_5day > 0:
            tags.append('[土洋對作]')

        # 1. 法人買超
        if i5 > 0:
            score += 1
            score_reasons.append("法人買超")
        if bd >= 3:
            score += 1
            score_reasons.append(f"連{bd}天")

        # 2. 攻擊訊號
        if bias_ma20 > 1 and chg > 0:
            score += 1
            score_reasons.append("攻擊")

        # 3. 量增
        if vol > avg_vol:
            score += 1
            score_reasons.append("量增")

        # 4. 穩漲
        if 0 < chg < 5:
            score += 1
            score_reasons.append("穩漲")

        # 5. 資減
        if is_margin_dec and i5 > 0:
            score += 1
            score_reasons.append("資減")
            tags.append('[資減]')

        # 6. 軋空
        if is_short_inc:
            score += 1
            score_reasons.append("軋空")
            tags.append('[軋空]')

        # 7. YoY
        if yoy > 0:
            score += 1
            score_reasons.append(f"YoY+{yoy:.0f}%")

        # 8. 投信買
        if trust_today > 0:
            score += 1
            score_reasons.append("投信買")

        # 9. 投信連買
        if trust_buy_days >= 2:
            score += 1
            score_reasons.append(f"投信連{trust_buy_days}天")

        # 只保留 >= 3 分的股票
        if score >= 3:
            s_copy = s.copy()
            s_copy['score'] = score
            s_copy['score_reasons'] = score_reasons
            s_copy['tags'] = tags
            v5_with_score.append(s_copy)

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

    # V8: 量縮蓄勢版
    # 連續 3 天 Close > MA20 AND 連續 3 天 Volume < MA(Volume,20) * 0.8
    v8_cond = False
    prices_list = s.get('prices', [])
    if len(prices_list) >= 20 and ma20 > 0:
        # prices_list 格式: [(date, close, volume, high, low), ...] 最新在前
        closes = [p[1] for p in prices_list]
        volumes = [p[2] for p in prices_list]

        # 計算 MA20 Volume
        ma20_volume = sum(volumes[:20]) / 20 if len(volumes) >= 20 else 0

        if ma20_volume > 0:
            # 檢查連續 3 天 Close > MA20
            trend_ok = all(closes[i] > ma20 for i in range(min(3, len(closes))))

            # 檢查連續 3 天 Volume < MA20_Volume * 0.8
            squeeze_ok = all(volumes[i] < ma20_volume * 0.8 for i in range(min(3, len(volumes))))

            v8_cond = trend_ok and squeeze_ok

    if v8_cond:
        v8.append(s)

    # V9: V7 + KD 金叉確認
    # V7 通過後，加上 KD 確認止跌訊號
    kd_bullish = False
    if k9 is not None and d9 is not None:
        kd_bullish = k9 > d9  # K 值大於 D 值 = 黃金交叉

    v9_cond = v7_cond and kd_bullish
    if v9_cond:
        v7s.append(s)  # 變數名保持 v7s 向下相容

print(f'   V4 (穩健): {len(v4):2} 檔  | 5日<10%, YoY>0')
print(f'   V5 (寬鬆): {len(v5):2} 檔  | 5日<15%, 無YoY')
print(f'   V6 (嚴格): {len(v6):2} 檔  | 5日<5%, YoY>0')
print(f'   V6*(短線): {len(v6s):2} 檔  | 5日<5%, 無YoY')
print(f'   V7 (狙擊): {len(v7):2} 檔  | 今日跌, 近支撐, 主力在')
print(f'   V8 (量縮): {len(v8):2} 檔  | 連3天站MA20, 量縮')
print(f'   V9 (KD翻): {len(v7s):2} 檔  | V7 + K>D 確認')
print()

# ===== Part 3: 產生輸出 =====
print('[2/3] 產生多版本報告...')

def get_version_label(s, v4_set, v5_set, v6_set, v6s_set, v7_set, v8_set, v9_set):
    """產生版本標籤字串"""
    t = s['ticker']
    versions = []
    if t in v4_set: versions.append('V4')
    if t in v5_set: versions.append('V5')
    if t in v6_set: versions.append('V6')
    if t in v6s_set: versions.append('V6*')
    if t in v7_set: versions.append('V7')
    if t in v8_set: versions.append('V8')
    if t in v9_set: versions.append('V9')

    if len(versions) >= 4:
        return '⟨全過⟩'
    elif len(versions) == 0:
        return ''
    else:
        return '⟨' + ' '.join(versions) + '⟩'

def generate_full_report(v4, v5, v6, v6s, v7, v8, v9, date_str):
    """產生完整多版本報告"""
    lines = []
    lines.append('=' * 60)
    lines.append(f'📊 {date_str} 多版本選股報告')
    lines.append('=' * 60)
    lines.append('')

    lines.append('【選股數量】')
    lines.append(f'V4 (穩健): {len(v4):2} 檔  | 5日<10%, YoY>0')
    lines.append(f'V5 (寬鬆): {len(v5):2} 檔  | 5日<15%, 無YoY')
    lines.append(f'V6 (嚴格): {len(v6):2} 檔  | 5日<5%, YoY>0')
    lines.append(f'V6*(短線): {len(v6s):2} 檔  | 5日<5%, 無YoY')
    lines.append(f'V7 (狙擊): {len(v7):2} 檔  | 今日跌, 近支撐, 主力在')
    lines.append(f'V8 (量縮): {len(v8):2} 檔  | 連3天站MA20, 量縮')
    lines.append(f'V9 (KD翻): {len(v9):2} 檔  | V7 + K>D 確認')
    lines.append('')

    # 建立 ticker set
    v4_set = {s['ticker'] for s in v4}
    v5_set = {s['ticker'] for s in v5}
    v6_set = {s['ticker'] for s in v6}
    v6s_set = {s['ticker'] for s in v6s}
    v7_set = {s['ticker'] for s in v7}
    v8_set = {s['ticker'] for s in v8}
    v9_set = {s['ticker'] for s in v9}

    # 合併所有股票
    all_tickers = {}
    for lst in [v4, v5, v6, v6s, v7, v8, v9]:
        for s in lst:
            t = s['ticker']
            if t not in all_tickers:
                all_tickers[t] = s

    # 計算版本數
    def count_versions(s):
        t = s['ticker']
        cnt = 0
        if t in v4_set: cnt += 1
        if t in v5_set: cnt += 1
        if t in v6_set: cnt += 1
        if t in v6s_set: cnt += 1
        if t in v7_set: cnt += 1
        if t in v8_set: cnt += 1
        if t in v9_set: cnt += 1
        return cnt

    # 排序：版本數 > 法人買超
    sorted_stocks = sorted(all_tickers.values(),
                          key=lambda x: (count_versions(x), x.get('inst_5day', 0)),
                          reverse=True)

    lines.append('━' * 60)
    lines.append('📋 多版本綜合推薦（依版本數排序）')
    lines.append('━' * 60)
    lines.append('')

    for s in sorted_stocks:
        t = s['ticker']
        name = s.get('name', '')[:4]
        price = s['price']
        label = get_version_label(s, v4_set, v5_set, v6_set, v6s_set, v7_set, v8_set, v9_set)

        vcnt = count_versions(s)
        if vcnt >= 4:
            emoji = '🏆'
        elif vcnt >= 2:
            emoji = '⭐'
        else:
            emoji = '📋'

        d5 = s.get('5day_change', 0)
        yoy = s.get('revenue_yoy', 0)
        i5 = s.get('inst_5day', 0)
        bd = s.get('buy_days', 0)

        lines.append(f"{emoji} {name} {t} ${price:.1f} {label}")
        lines.append(f"   5日:{d5:+.1f}% YoY:{yoy:+.1f}% 法人5日:{i5}張 連{bd}買")
        lines.append('')

    return '\n'.join(lines)

def generate_v9_lite_card(v5_with_score, v4_set, v5_set, v6_set, v6s_set, v7_set, v8_set, v9_set, date_str):
    """產生 V9 小卡（LINE 推送用）- 多版本整合 + 完整評分 + 版本標籤"""
    lines = []

    # 開頭框線
    lines.append('━' * 25)
    lines.append(f"📊 {date_str} 選股 (大盤+0.00%)")
    lines.append('━' * 25)
    lines.append('')

    # 分類股票：順勢股 vs 純狙擊股/量縮股
    trend_stocks = []  # 有通過 V4/V5/V6/V6* 任一版本
    sniper_stocks = []  # 只通過 V7/V8/V9

    for s in v5_with_score:
        t = s['ticker']
        has_trend = t in v4_set or t in v5_set or t in v6_set or t in v6s_set
        has_sniper = t in v7_set or t in v8_set or t in v9_set

        if has_trend:
            trend_stocks.append(s)
        elif has_sniper:
            sniper_stocks.append(s)

    # 按評分排序（同分則按法人5日）
    trend_sorted = sorted(trend_stocks, key=lambda x: (x.get('score', 0), x.get('inst_5day', 0)), reverse=True)
    sniper_sorted = sorted(sniper_stocks, key=lambda x: (x.get('score', 0), x.get('inst_5day', 0)), reverse=True)

    # ===== 上半部：順勢股 =====
    for s in trend_sorted[:6]:  # 最多 6 檔
        t = s['ticker']
        name = s.get('name', '')[:4]
        price = s['price']
        bd = s.get('buy_days', 0)
        inst_leader = s.get('inst_leader', '外資')
        stock_type = s.get('stock_type', '普通')
        atr = s.get('atr', price * 0.03)
        score = s.get('score', 0)
        tags = s.get('tags', [])

        # 動物圖示
        type_icon = '🐰' if stock_type == '兔子' else ('🐢' if stock_type == '烏龜' else '🚶')

        # 計算停損停利
        stop = int(price - 2 * atr)
        t1 = int(price + 2 * atr)
        t2 = int(price + 3 * atr)
        entry_low = int(price - 0.5 * atr)
        entry_high = int(price)

        # 評分圖示
        score_icon = '🔥' if score >= 5 else ('⭐' if score >= 4 else '✅')

        # 產生版本標籤（順勢 + 狙擊）
        trend_versions = []
        if t in v4_set: trend_versions.append('V4')
        if t in v5_set: trend_versions.append('V5')
        if t in v6_set: trend_versions.append('V6')
        if t in v6s_set: trend_versions.append('V6*')

        # 基礎標籤
        if len(trend_versions) >= 4:
            version_label = '全過'
        else:
            version_label = '/'.join(trend_versions)

        # 加上狙擊/量縮標籤
        if t in v9_set:
            version_label += '+V9'
        elif t in v8_set:
            version_label += '+V8'
        elif t in v7_set:
            version_label += '+V7'

        # 組合籌碼標籤
        chip_tags = []
        if '[資減]' in tags:
            chip_tags.append('資減')
        if '[軋空]' in tags:
            chip_tags.append('軋空')
        if '[投信]' in tags:
            chip_tags.append('投信')

        yoy = s.get('revenue_yoy', 0)
        if yoy >= 10:
            chip_tags.append(f"YoY+{int(yoy)}%")

        # 組合第二行：版本 | 主力 | 標籤
        chip_line = f"   {version_label} | {inst_leader}連{bd}買"
        if chip_tags:
            chip_line += '｜' + '｜'.join(chip_tags)

        # 輸出格式 (3行精簡)
        lines.append(f"{score_icon} {name} {t} ${price:.1f} ⟨{score}分⟩{type_icon}")
        lines.append(chip_line)
        lines.append(f"   💵{entry_low}~{entry_high}｜🛡️{stop}｜🎯{t1}/{t2}")
        lines.append('')

    # ===== 下半部：純狙擊股/量縮股 (如果有) =====
    if sniper_sorted:
        lines.append('━' * 25)
        lines.append('⚡ V7/V8/V9 特殊股')
        lines.append('━' * 25)
        lines.append('')

        for s in sniper_sorted[:3]:  # 最多 3 檔
            t = s['ticker']
            name = s.get('name', '')[:4]
            price = s['price']
            bd = s.get('buy_days', 0)
            inst_leader = s.get('inst_leader', '外資')
            stock_type = s.get('stock_type', '普通')
            atr = s.get('atr', price * 0.03)
            score = s.get('score', 0)
            tags = s.get('tags', [])

            # 動物圖示
            type_icon = '🐰' if stock_type == '兔子' else ('🐢' if stock_type == '烏龜' else '🚶')

            # 計算停損停利
            stop = int(price - 2 * atr)
            t1 = int(price + 2 * atr)
            t2 = int(price + 3 * atr)
            entry_low = int(price - 0.5 * atr)
            entry_high = int(price)

            # 狙擊股圖示
            score_icon = '⚡'

            # 產生版本標籤（只有 V7/V8/V9）
            if t in v9_set:
                version_label = 'V9'
            elif t in v8_set:
                version_label = 'V8'
            else:
                version_label = 'V7'

            # 組合籌碼標籤
            chip_tags = []
            if '[資減]' in tags:
                chip_tags.append('資減')
            if '[軋空]' in tags:
                chip_tags.append('軋空')
            if '[投信]' in tags:
                chip_tags.append('投信')

            yoy = s.get('revenue_yoy', 0)
            if yoy >= 10:
                chip_tags.append(f"YoY+{int(yoy)}%")

            # 組合第二行：版本 | 主力 | 標籤
            chip_line = f"   {version_label} | {inst_leader}連{bd}買"
            if chip_tags:
                chip_line += '｜' + '｜'.join(chip_tags)

            # 輸出格式 (3行精簡)
            lines.append(f"{score_icon} {name} {t} ${price:.1f} ⟨{score}分⟩{type_icon}")
            lines.append(chip_line)
            lines.append(f"   💵{entry_low}~{entry_high}｜🛡️{stop}｜🎯{t1}/{t2}")
            lines.append('')

    # 結尾框線
    lines.append('━' * 25)

    return '\n'.join(lines)

# 產生報告
v4_set = {s['ticker'] for s in v4}
v5_set = {s['ticker'] for s in v5}
v6_set = {s['ticker'] for s in v6}
v6s_set = {s['ticker'] for s in v6s}
v7_set = {s['ticker'] for s in v7}
v8_set = {s['ticker'] for s in v8}
v9_set = {s['ticker'] for s in v7s}

full_report = generate_full_report(v4, v5, v6, v6s, v7, v8, v7s, date_str)
v9_lite = generate_v9_lite_card(v5_with_score, v4_set, v5_set, v6_set, v6s_set, v7_set, v8_set, v9_set, date_str)

# ===== Part 4: 儲存輸出 =====
print('[3/3] 儲存輸出檔案...')

# 完整報告
output_file = 'd:/claude-project/STOCK_HUNTER/scan_result_all_versions.txt'
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(full_report)
print(f'   [OK] 完整報告: scan_result_all_versions.txt')

# V9 小卡
lite_file = 'd:/claude-project/STOCK_HUNTER/scan_result_v9_lite.txt'
with open(lite_file, 'w', encoding='utf-8') as f:
    f.write(v9_lite)
print(f'   [OK] V9 小卡: scan_result_v9_lite.txt')

print()
print('=' * 60)
print('[DONE] 乾測試完成！')
print('=' * 60)
print()
print('[PREVIEW] 結果預覽:')
print()
print(full_report[:800])
print()
print('...')
print()
print('[V9 CARD] V9 小卡預覽:')
print()
print(v9_lite)
