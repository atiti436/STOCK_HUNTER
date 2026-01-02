#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
推送選股結果到 Line BOT
由 GitHub Actions 呼叫，讀取 scan_result_v3.txt 並透過 ZEABUR Line BOT 推送
"""

import os
import sys
import requests
from datetime import datetime

def read_scan_result():
    """讀取選股結果檔案"""
    # 優先讀 v4，沒有再讀 v3
    for result_file in ['scan_result_v4.txt', 'scan_result_v3.txt']:
        if os.path.exists(result_file):
            print(f'[*] 讀取: {result_file}')
            with open(result_file, 'r', encoding='utf-8') as f:
                return f.read()
    
    print('[!] 找不到結果檔案')
    return None


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


def format_line_message(content):
    """格式化 Line 訊息（v3.4 劇本小卡版）"""
    stock_count = parse_stock_count(content)
    today = datetime.now().strftime('%Y-%m-%d')

    if stock_count == 0:
        # 沒有股票時發送簡短訊息
        message = f"""📊 選股 BOT v3.4 - {today}

❌ 今日無符合條件的股票

篩選條件：
✅ 法人連續買超 ≥2天
✅ 體質健康 (PE<35, 營收YoY>0%)
✅ 還沒噴 (5日漲<10%, RSI<80)
✅ 有量能 (今日量>5日均)"""
    else:
        # 找劇本小卡區塊
        lines = content.split('\n')
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
            # 只取前 5 檔的劇本小卡（避免訊息過長）
            # 每檔約 4 行，所以取 20 行
            script_text = '\n'.join(script_card_lines[:20])
            
            message = f"""📊 選股 BOT v3.4 - {today}

✅ 找到 {stock_count} 檔推薦股票

{script_text}
篩選條件：
✅ 法人連續買超 ≥2天
✅ 體質健康 (PE<35, 營收YoY>0%)
✅ 還沒噴 (5日漲<10%, RSI<80)"""
        else:
            # 降級：用舊格式
            message = f"""📊 選股 BOT v3.4 - {today}

✅ 找到 {stock_count} 檔推薦股票
請查看完整結果檔案"""

    return message.strip()


def push_to_linebot(message, linebot_url):
    """推送訊息到 Line BOT"""
    url = f"{linebot_url}/push_scan_result"

    headers = {
        'Content-Type': 'application/json'
    }

    data = {
        'message': message
    }

    try:
        response = requests.post(url, json=data, headers=headers, timeout=10)

        if response.status_code == 200:
            print('[OK] Line 訊息推送成功')
            return True
        else:
            print(f'[!] Line 訊息推送失敗: {response.status_code}')
            print(f'    回應: {response.text}')
            return False
    except Exception as e:
        print(f'[!] Line 訊息推送異常: {e}')
        return False


def main():
    # 從環境變數取得 Line BOT URL
    linebot_url = os.environ.get('LINEBOT_URL')

    if not linebot_url:
        print('[!] 錯誤: 未設定 LINEBOT_URL 環境變數')
        print('    請在 GitHub Secrets 中設定 LINEBOT_URL (例如: https://your-app.zeabur.app)')
        sys.exit(1)

    # 移除結尾的 /
    linebot_url = linebot_url.rstrip('/')

    # 讀取選股結果
    print('讀取選股結果...')
    content = read_scan_result()

    if content is None:
        sys.exit(1)

    # 格式化訊息
    message = format_line_message(content)
    print('\n準備推送的訊息:')
    print('=' * 60)
    print(message)
    print('=' * 60)

    # 推送到 Line BOT
    print(f'\n推送到 Line BOT: {linebot_url}')
    success = push_to_linebot(message, linebot_url)

    if success:
        print('[OK] 完成')
        sys.exit(0)
    else:
        print('[!] 失敗')
        sys.exit(1)


if __name__ == '__main__':
    main()
