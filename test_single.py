#!/usr/bin/env python3
"""測試單股分析 v5.0"""

from stock_hunter_v3 import analyze_single_stock, format_single_stock_message

print("Testing single stock analysis for 2548 (華固)...")
result = analyze_single_stock('2548')

if 'error' in result:
    print(f"Error: {result['error']}")
else:
    print(f"\n確信度: {result.get('confidence_score', 0)}分")
    print(f"模式: {result.get('mode', 'N/A')}")
    print(f"RS: {result.get('rs', 0)}%")
    
    msg = format_single_stock_message(result)
    print("\n=== LINE 訊息預覽 ===")
    print(msg)
