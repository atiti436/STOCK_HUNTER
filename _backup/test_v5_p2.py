#!/usr/bin/env python3
"""本地測試 v5.0 Phase 2 (含營收)"""

from stock_hunter_v3 import scan_all_stocks, format_line_messages

print("Running v5.0 with revenue module...")
result = scan_all_stocks()

recs = result.get('recommendations', {}).get('swing_trade', [])
print(f"\n=== 推薦 {len(recs)} 支 ===")
for r in recs[:10]:
    breakdown = ' | '.join(r.get('confidence_breakdown', []))
    print(f"{r['ticker']} {r['name']}: {r['confidence_score']}分 ({breakdown})")

print("\n=== LINE 訊息預覽 ===")
messages = format_line_messages(result)
for msg in messages[:3]:
    print(msg)
    print("=" * 40)
