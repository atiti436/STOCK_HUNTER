"""
Line Notify 推送腳本
讀取 scan_result_v3.txt 並推送到 Line
"""

import os
import sys
import requests
from datetime import datetime

def read_scan_result():
    """讀取選股結果檔案"""
    result_file = 'scan_result_v3.txt'

    if not os.path.exists(result_file):
        print(f'[!] 找不到結果檔案: {result_file}')
        return None

    with open(result_file, 'r', encoding='utf-8') as f:
        content = f.read()

    return content

def parse_stock_count(content):
    """解析股票數量"""
    for line in content.split('\n'):
        if line.startswith('共 '):
            try:
                count = int(line.split(' ')[1])
                return count
            except:
                pass
    return 0

def parse_warnings(content):
    """解析健康檢查警告"""
    warnings = []
    for line in content.split('\n'):
        if line.strip().startswith('- ') and '異常' in line or '過低' in line:
            warnings.append(line.strip()[2:])  # 移除 "- " 前綴
        if line.strip().startswith('⚠️ 警告:'):
            # 解析最後的摘要行
            msg = line.replace('⚠️ 警告:', '').strip()
            if msg and msg not in warnings:
                warnings = [msg]  # 使用摘要代替
    return warnings

def format_line_message(content):
    """格式化 Line 訊息（含健康檢查警告）"""
    stock_count = parse_stock_count(content)
    warnings = parse_warnings(content)
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 警告訊息
    warning_text = ""
    if warnings:
        warning_text = "\n⚠️ 資料警告: " + ", ".join(warnings) + "\n"

    if stock_count == 0:
        # 沒有股票時發送簡短訊息
        message = f"""
📊 選股 BOT v3.4 - {today}
{warning_text}
❌ 今日無符合條件的股票

篩選條件：
✅ 法人連續買超 ≥2天
✅ 體質健康 (PE<35, 營收YoY>0%)
✅ 還沒噴 (5日漲<10%, RSI<80)
✅ 有量能 (今日量>5日均)
"""
    else:
        # 有股票時發送卡片式結果 (v3.4)
        lines = content.split('\n')

        # 找到劇本小卡區塊
        script_card_lines = []
        in_script_card = False
        for line in lines:
            if '【劇本小卡】' in line:
                in_script_card = True
                continue
            if in_script_card:
                if line.startswith('===') or line.startswith('⚠️'):
                    break
                if line.strip():
                    script_card_lines.append(line)

        if script_card_lines:
            # 使用劇本小卡格式
            script_text = '\n'.join(script_card_lines[:20])  # 限制長度
            message = f"""
📊 選股 BOT v3.4 - {today}
{warning_text}
✅ 找到 {stock_count} 檔推薦股票

{script_text}
篩選條件：
✅ 法人連續買超 ≥2天
✅ 體質健康 (PE<35, 營收YoY>0%)
✅ 還沒噴 (5日漲<10%, RSI<80)
"""
        else:
            # 降級：用簡短提示
            message = f"""
📊 選股 BOT v3.4 - {today}
{warning_text}
✅ 找到 {stock_count} 檔推薦股票
請查看完整結果檔案
"""

    return message.strip()

def send_line_notify(message, token):
    """發送 Line Notify 訊息"""
    url = 'https://notify-api.line.me/api/notify'
    headers = {
        'Authorization': f'Bearer {token}'
    }
    data = {
        'message': message
    }

    try:
        response = requests.post(url, headers=headers, data=data)

        if response.status_code == 200:
            print('[OK] Line 訊息發送成功')
            return True
        else:
            print(f'[!] Line 訊息發送失敗: {response.status_code}')
            print(f'    回應: {response.text}')
            return False
    except Exception as e:
        print(f'[!] Line 訊息發送異常: {e}')
        return False

def main():
    # 從環境變數取得 Line Notify Token
    line_token = os.environ.get('LINE_NOTIFY_TOKEN')

    if not line_token:
        print('[!] 錯誤: 未設定 LINE_NOTIFY_TOKEN 環境變數')
        print('    請在 GitHub Secrets 中設定 LINE_NOTIFY_TOKEN')
        sys.exit(1)

    # 讀取選股結果
    print('讀取選股結果...')
    content = read_scan_result()

    if content is None:
        sys.exit(1)

    # 格式化訊息
    message = format_line_message(content)
    print('\n準備發送的訊息:')
    print('=' * 60)
    print(message)
    print('=' * 60)

    # 發送 Line Notify
    print('\n發送 Line Notify...')
    success = send_line_notify(message, line_token)

    if success:
        print('[OK] 完成')
        sys.exit(0)
    else:
        print('[!] 失敗')
        sys.exit(1)

if __name__ == '__main__':
    main()
