import json

d = json.load(open('data/history/2026-01-06_1936.json', encoding='utf-8'))
print(f"日期: {d['date']}")
print(f"數量: {d['count']}")
print()

for s in d['stocks']:
    score = s.get('score', 0)
    tags = ' '.join(s.get('tags', []))
    reasons = ','.join(s.get('score_reasons', []))
    stock_type = s.get('stock_type', '?')
    print(f"{score}分 {s['ticker']} {s['name']}")
    print(f"    ${s['price']} {stock_type} 法人{s['inst_5day']:+,}張")
    print(f"    ATR: ${s.get('atr', 0)} ({s.get('atr_pct', 0)}%)")
    print(f"    停損: ${s.get('stop_loss', 0)} T1: ${s.get('t1', 0)} T2: ${s.get('t2', 0)}")
    print(f"    標籤: {tags or '-'}")
    print(f"    理由: {reasons}")
    print()
