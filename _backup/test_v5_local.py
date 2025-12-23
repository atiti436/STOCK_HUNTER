#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
STOCK_HUNTER v5.0 本地測試腳本 (Dry Run)
不需要 LINE webhook，直接測試核心功能
"""

import sys
import os

# 確保可以 import 主程式
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("🧪 STOCK_HUNTER v5.0 本地測試 (Dry Run)")
print("=" * 60)

# 測試 1: 檢查依賴
print("\n📦 [測試 1] 檢查依賴...")
try:
    import pandas as pd
    print("   ✅ pandas 已安裝")
except ImportError:
    print("   ❌ pandas 未安裝，請執行: pip install pandas")
    sys.exit(1)

try:
    from FinMind.data import DataLoader
    print("   ✅ FinMind 已安裝")
    FINMIND_OK = True
except ImportError:
    print("   ⚠️ FinMind 未安裝，大盤濾網將使用備援")
    FINMIND_OK = False

# 測試 2: 導入主程式
print("\n🔧 [測試 2] 導入主程式...")
try:
    from stock_hunter_v3 import (
        get_market_trend,
        calculate_confidence_score,
        get_strategy_mode,
        get_strategy_params,
        get_all_stocks_data,
        CONFIG
    )
    print("   ✅ 主程式導入成功")
except Exception as e:
    print(f"   ❌ 導入失敗: {e}")
    sys.exit(1)

# 測試 3: 大盤濾網
print("\n📊 [測試 3] 大盤濾網 (FinMind)...")
if FINMIND_OK:
    try:
        market = get_market_trend()
        print(f"   趨勢: {market['trend']}")
        print(f"   年線: {market.get('ma240', 'N/A')}")
        print(f"   20日漲幅: {market.get('return_20d', 'N/A')}%")
        print("   ✅ 大盤濾網正常")
    except Exception as e:
        print(f"   ❌ 失敗: {e}")
else:
    market = {'trend': 'BULL', 'return_20d': 0, 'ma240': 0}
    print("   ⚠️ 跳過 (FinMind 未安裝)")

# 測試 4: 確信度評分
print("\n🎯 [測試 4] 確信度評分...")
try:
    test_stock = {
        'ticker': '2330',
        'name': '台積電',
        'price': 1050,
        'change_pct': 2.5,
        'return_20d': 5.0,  # 假設 20 日漲 5%
        'above_ma60': True,
        'ma60': 1000,
        'ma60_slope': 1
    }
    
    result = calculate_confidence_score(test_stock, market, revenue_data=None)
    print(f"   確信度分數: {result['score']} 分")
    print(f"   評分細項: {result['breakdown']}")
    
    mode = get_strategy_mode(result['score'], market['trend'])
    print(f"   策略模式: {mode}")
    
    params = get_strategy_params(mode)
    print(f"   停損: {params['stop_loss']}")
    print(f"   停利: +{params['take_profit_deviation']}%")
    print("   ✅ 確信度評分正常")
except Exception as e:
    print(f"   ❌ 失敗: {e}")

# 測試 5: 股票資料 API
print("\n📈 [測試 5] 股票資料 API (TWSE)...")
try:
    stocks = get_all_stocks_data()
    if stocks:
        print(f"   取得 {len(stocks)} 支股票")
        sample = stocks[0]
        print(f"   範例: {sample['ticker']} {sample['name']} ${sample['price']}")
        print("   ✅ 股票 API 正常")
    else:
        print("   ⚠️ 無資料 (可能非交易時間)")
except Exception as e:
    print(f"   ❌ 失敗: {e}")

# 測試 6: CONFIG 設定
print("\n⚙️ [測試 6] CONFIG 設定...")
print(f"   確信度門檻 INSIDER: ≥{CONFIG['CONFIDENCE_INSIDER']}")
print(f"   確信度門檻 RETAIL: ≥{CONFIG['CONFIDENCE_RETAIL']}")
print(f"   當沖開關: {'🔴 關閉' if not CONFIG.get('ENABLE_DAY_TRADE', False) else '🟢 開啟'}")
print("   ✅ CONFIG 正常")

# 完成
print("\n" + "=" * 60)
print("🎉 本地測試完成！")
print("=" * 60)

if FINMIND_OK:
    print("\n👉 下一步: 部署到 Zeabur 並測試 LINE webhook")
else:
    print("\n⚠️ 建議先安裝 FinMind: pip install FinMind")
