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
        print('[ERROR] candidates.json not found')
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
        print(f'[ERROR] scan_20260106.py not found: {scan_script}')
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
            encoding='utf-8',
            errors='replace'  # Windows cp950 編碼相容
        )
        # 跳過輸出（避免 Windows 編碼問題）
        print('  scan_20260106.py completed successfully')
        print()
    except subprocess.CalledProcessError as e:
        print('[ERROR] scan_20260106.py failed')
        # 不輸出 stderr（可能包含無法編碼的字元）
        # 如需除錯，請直接執行 python scan_20260106.py
        sys.exit(1)

    # 步驟 2: 讀取產生的 candidates.json
    print('[2/2] 讀取候選池資料...')
    raw_dir = Path('d:/claude-project/STOCK_HUNTER/data/raw')

    # 尋找最新的 candidates.json
    candidates_files = sorted(raw_dir.glob('*_candidates.json'), reverse=True)

    if not candidates_files:
        print('[ERROR] candidates.json not found')
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
all_stocks_with_score = []  # 所有股票 + 評分（修復 V7 遺漏問題）

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

    # === 評分系統（對所有候選股票都計算，不限 V5）===
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

    # 儲存所有股票的評分（不限版本）
    s_copy = s.copy()
    s_copy['score'] = score
    s_copy['score_reasons'] = score_reasons
    s_copy['tags'] = tags
    all_stocks_with_score.append(s_copy)

    # V4: 穩健版
    if base and (d5 < 10) and (yoy > 0):
        v4.append(s)

    # V5: 寬鬆版 (90-300, 5日<15%)
    if (90 <= p <= 300) and (d5 < 15) and (bd >= 2) and (i5 > 300):
        v5.append(s)
        # 只保留 >= 3 分的股票
        if score >= 3:
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

def generate_v9_lite_card(all_stocks_with_score, v4_set, v5_set, v6_set, v6s_set, v7_set, v8_set, v9_set, date_str):
    """產生 V9 小卡（LINE 推送用）- 版本標籤格式"""

    # 建立版本標籤函數（主列表用，只含 V4/V5/V6/V6*/V8）
    def get_version_label(ticker):
        versions = []
        if ticker in v4_set: versions.append('V4')
        if ticker in v5_set: versions.append('V5')
        if ticker in v6_set: versions.append('V6')
        if ticker in v6s_set: versions.append('V6*')
        if ticker in v8_set: versions.append('V8')

        if len(versions) >= 4:
            return '⟨全過⟩'
        elif len(versions) > 0:
            return '⟨' + ' '.join(versions) + '⟩'
        else:
            return ''

    # 計算版本數（用於排序和 emoji）
    def count_versions(s):
        ticker = s['ticker']
        count = 0
        if ticker in v4_set: count += 1
        if ticker in v5_set: count += 1
        if ticker in v6_set: count += 1
        if ticker in v6s_set: count += 1
        if ticker in v7_set: count += 1
        if ticker in v8_set: count += 1
        # V9 不單獨計算（V9 ⊂ V7）
        return count

    # 合併所有通過版本的股票
    all_tickers = {}
    for s in all_stocks_with_score:
        ticker = s['ticker']
        # 只要通過任一版本就加入（不管評分！）
        if ticker in v4_set or ticker in v5_set or ticker in v6_set or ticker in v6s_set or ticker in v7_set or ticker in v8_set or ticker in v9_set:
            all_tickers[ticker] = s

    # 排序：版本數 > 評分 > 法人買超
    sorted_stocks = sorted(
        all_tickers.values(),
        key=lambda x: (count_versions(x), x.get('score', 0), x.get('inst_5day', 0)),
        reverse=True
    )

    lines = []
    lines.append(f"📊 {date_str} 選股")
    lines.append("")

    # 主列表：順勢股（通過 V4/V5/V6/V6* 或 V8）
    for s in sorted_stocks:
        ticker = s['ticker']

        # V7 only 跳過，稍後在 V7 區塊顯示
        is_v7_only = (ticker in v7_set and
                      ticker not in v4_set and
                      ticker not in v5_set and
                      ticker not in v6_set and
                      ticker not in v6s_set and
                      ticker not in v8_set)
        if is_v7_only:
            continue

        # V8 only 也跳過，稍後在 V8 區塊顯示
        is_v8_only = (ticker in v8_set and
                      ticker not in v4_set and
                      ticker not in v5_set and
                      ticker not in v6_set and
                      ticker not in v6s_set and
                      ticker not in v7_set)
        if is_v8_only:
            continue

        # 格式化輸出
        name = s.get('name', '')[:4]
        price = s['price']
        label = get_version_label(ticker)

        # emoji（依版本數）
        vcnt = count_versions(s)
        emoji = '🏆' if vcnt >= 4 else ('⭐' if vcnt >= 2 else '📋')

        # 法人資訊
        buy_days = s.get('buy_days', 0)
        foreign_5day = s.get('foreign_5day', 0)
        trust_5day = s.get('trust_5day', 0)
        inst_leader = '外資' if foreign_5day > trust_5day else '投信'
        inst_info = f"{inst_leader}連{buy_days}買" if buy_days >= 2 else f"法人+{s.get('inst_5day', 0)}張"

        # 題材（YoY）
        yoy = s.get('revenue_yoy', 0)
        news = f"YoY+{yoy:.0f}%" if yoy > 10 else (f"YoY+{yoy:.1f}%" if yoy > 0 else "")

        # ATR 計算
        atr = s.get('atr', price * 0.03)
        entry_low = round(price - 0.5 * atr)
        stop = round(price - 2 * atr)
        target = round(price + 2 * atr)

        # 股性標籤（🐰兔子=活潑, 🐢烏龜=穩健）
        atr_pct = (atr / price * 100) if price > 0 else 0
        personality = '🐰' if atr_pct > 3 else '🐢'

        # RVol 計算與警示 (v5.4)
        volume = s.get('volume', 0)
        avg_volume = s.get('avg_volume', 1)
        rvol = volume / avg_volume if avg_volume > 0 else 0
        change_pct = s.get('change_pct', 0)

        # 量能警示：漲時量縮=警示，漲時量增=加分
        if change_pct > 0 and rvol < 0.8:
            rvol_tag = f" ⚠️量弱{rvol:.1f}x"
        elif change_pct > 0 and rvol > 1.3:
            rvol_tag = f" ✅量強{rvol:.1f}x"
        elif rvol > 0:
            rvol_tag = f" 量{rvol:.1f}x"
        else:
            rvol_tag = ""

        # 輸出
        lines.append(f"{emoji} {name} {ticker} ${price:.0f} {label}{personality}{rvol_tag}")
        if news:
            lines.append(f"   {inst_info}｜{news}")
        else:
            lines.append(f"   {inst_info}")
        lines.append(f"   💵{entry_low}~{price:.0f}｜🛡️{stop}｜🎯{target}")
        lines.append("")

    # V7 狙擊區塊（含 V9 標示）
    v7_only_stocks = [s for s in all_stocks_with_score
                      if s['ticker'] in v7_set and
                      s['ticker'] not in v4_set and
                      s['ticker'] not in v5_set and
                      s['ticker'] not in v6_set and
                      s['ticker'] not in v6s_set and
                      s['ticker'] not in v8_set]

    if v7_only_stocks:
        lines.append("─── V7 狙擊 ───")
        lines.append("")

        for s in v7_only_stocks:
            name = s.get('name', '')[:4]
            ticker = s['ticker']
            price = s['price']
            rsi = s.get('rsi', 50)
            ma10 = s.get('ma10', 0)
            ma20 = s.get('ma20', 0)
            support = min(ma10, ma20) if ma10 > 0 and ma20 > 0 else price * 0.97

            # V9 標示：V9 = V7 + KD 金叉，所以 V9 一定也是 V7
            if ticker in v9_set:
                label = "⟨V7 V9⟩"
                kd_mark = " KD✓"
            else:
                label = "⟨V7⟩"
                kd_mark = ""

            # RVol 警示 (v5.4) - V7 是回檔股，跌時量縮=好
            volume = s.get('volume', 0)
            avg_volume = s.get('avg_volume', 1)
            rvol = volume / avg_volume if avg_volume > 0 else 0
            change_pct = s.get('change_pct', 0)

            # V7 特有邏輯：跌時量縮=健康回檔，跌時量增=可能破線
            if change_pct < 0 and rvol < 0.8:
                rvol_tag = f" ✅跌縮{rvol:.1f}x"
            elif change_pct < 0 and rvol > 1.3:
                rvol_tag = f" ⚠️跌量{rvol:.1f}x"
            elif rvol > 0:
                rvol_tag = f" 量{rvol:.1f}x"
            else:
                rvol_tag = ""

            lines.append(f"🎯 {name} {ticker} ${price:.0f} {label}RSI{rsi:.0f}{kd_mark}{rvol_tag}")
            lines.append(f"   💵{support:.0f}~{price:.0f}")
            lines.append("")

    # V8 量縮區塊（獨立維度）
    v8_only_stocks = [s for s in all_stocks_with_score
                      if s['ticker'] in v8_set and
                      s['ticker'] not in v4_set and
                      s['ticker'] not in v5_set and
                      s['ticker'] not in v6_set and
                      s['ticker'] not in v6s_set and
                      s['ticker'] not in v7_set]

    if v8_only_stocks:
        lines.append("─── V8 量縮 ───")
        lines.append("")

        for s in v8_only_stocks:
            name = s.get('name', '')[:4]
            ticker = s['ticker']
            price = s['price']
            # V8 特有資訊：連續幾天站穩 MA20 且量縮
            volume_shrink_days = s.get('volume_shrink_days', 3)

            lines.append(f"🔋 {name} {ticker} ${price:.0f} ⟨V8⟩")
            lines.append(f"   連{volume_shrink_days}天量縮｜站穩MA20")
            lines.append("")

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
v9_lite = generate_v9_lite_card(all_stocks_with_score, v4_set, v5_set, v6_set, v6s_set, v7_set, v8_set, v9_set, date_str)

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
print('[INFO] Result files generated successfully!')
print('       - scan_result_all_versions.txt (full report)')
print('       - scan_result_v9_lite.txt (V9 card)')
print()
print('[TIP] Use "type scan_result_v9_lite.txt" to view the V9 card')
