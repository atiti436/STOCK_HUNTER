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
    """格式化 Line 訊息（v5.3 極簡行動卡版）"""
    stock_count = parse_stock_count(content)
    today = datetime.now().strftime('%Y-%m-%d')

    if stock_count == 0:
        # 沒有股票時發送簡短訊息
        message = f"""📊 選股 BOT v5.3 - {today}

❌ 今日無符合條件的股票

篩選條件：
✅ 法人連續買超 ≥2天
✅ 體質健康 (PE<35)
✅ 還沒噴 (5日漲<15%, RSI<85)
✅ 有量能 (>800張)"""
    else:
        # 優先找「極簡行動卡」區塊（v5.3 新增）
        lines = content.split('\n')
        card_lines = []
        in_card = False
        card_keyword = '【極簡行動卡】'

        # 如果找不到極簡行動卡，降級找 ATR 劇本小卡
        if card_keyword not in content:
            card_keyword = '【v5.2 ATR 劇本小卡】'
        if card_keyword not in content:
            card_keyword = '【劇本小卡】'

        for line in lines:
            if card_keyword in line:
                in_card = True
                continue
            if in_card:
                # 停止條件：遇到警告或下一個標題區塊
                if line.startswith('⚠️') or '【' in line:
                    break
                # 跳過 === 標題線，但保留 ━━━ 分隔線
                if line.strip() and not line.strip().replace('=', ''):
                    continue
                if line.strip():
                    card_lines.append(line)

        if card_lines:
            # v5.3 極簡行動卡每檔約 10 行，取前 3 檔（30 行內）
            # LINE 訊息限制 5000 字，30 行約 1000 字
            card_text = '\n'.join(card_lines[:35])

            message = f"""📊 選股 BOT v5.3 - {today}

✅ 找到 {stock_count} 檔推薦股票

{card_text}

篩選條件：法人買超≥2天, PE<35, 5日漲<15%"""
        else:
            # 降級：用舊格式
            message = f"""📊 選股 BOT v5.3 - {today}

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
