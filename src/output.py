
# 輸出模組
import json
import os
from datetime import datetime

def print_table(results):
    """
    輸出推薦股票表格
    results: 排序後的股票資料 list
    """
    print('=' * 80)
    print('推薦股票 TOP 6 (STOCK_HUNTER v4.1)')
    print('=' * 80)
    
    # Header
    # 排名 代碼 股名 股價 漲幅 PE 法人5日 主力 連買 5日漲 營收YoY RSI 停損
    header = f"{'排名':<4}{'代碼':<6}{'股名':<6}{'股價':<8}{'漲幅':<8}{'PE':<6}{'法人5日':<8}{'主力':<6}{'連買':<6}{'5日漲':<8}{'營收':<8}{'RSI':<6}{'停損':<8}"
    print(header)
    print('-' * 80)
    
    for i, stock in enumerate(results[:6], 1): # 只顯示前 6 名
        try:
            ticker = stock['ticker']
            name = stock['name'] # 需確保只有中文名或適當長度
            price = f"{stock['price']}"
            change = f"{stock['change_pct']:+.1f}%"
            pe = f"{stock['pe']}" if stock['pe'] else "-"
            
            inst_5 = f"{stock['inst_5day']}"
            leader = stock['inst_leader']
            buy_days = f"{stock['buy_days']}天"
            
            chg_5 = f"{stock['5day_change']:+.1f}%" if stock['5day_change'] is not None else "-"
            rev_yoy = f"{stock['revenue_yoy']:+.1f}%" if stock['revenue_yoy'] is not None else "-"
            rsi = f"{stock['rsi']}" if stock['rsi'] else "-"
            stop = f"{stock['stop_loss']}"
            
            # 使用全形空白填充中文對齊問題 (簡單處理)
            # 這裡用標準 format，中文對齊可能不完美，但可用
            line = f"{i:<4}{ticker:<6}{name:<6}{price:<8}{change:<8}{pe:<6}{inst_5:<8}{leader:<6}{buy_days:<6}{chg_5:<8}{rev_yoy:<8}{rsi:<6}{stop:<8}"
            print(line)
        except Exception as e:
            print(f"Error printing row {i}: {e}")
            
    print('=' * 80)

def save_json(results, output_dir='data', date_str=None):
    """儲存結果為 JSON"""
    try:
        timestamp = datetime.now().isoformat()
        if not date_str:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        data = {
            'date': date_str,
            'timestamp': timestamp,
            'count': len(results),
            'stocks': results
        }
        
        # 存到 data/scan_result_v4.json (最新)
        latest_path = os.path.join(output_dir, 'scan_result_v4.json')
        with open(latest_path, 'w', encoding='utf-8') as f:
             json.dump(data, f, ensure_ascii=False, indent=2)
            
        print(f"[OUTPUT] JSON saved to {latest_path}")
        
        # 存到 history (備份)
        history_path = os.path.join(output_dir, 'history', f'{date_str}.json')
        with open(history_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        print(f"[OUTPUT] Save JSON failed: {e}")
