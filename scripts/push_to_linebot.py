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


def format_line_message(content):
    """格式化 Line 訊息（精簡版，避免超過 5000 字元）"""
    stock_count = parse_stock_count(content)
    today = datetime.now().strftime('%Y-%m-%d')

    if stock_count == 0:
        # 沒有股票時發送簡短訊息
        message = f"""📊 選股 BOT v3.1 - {today}

❌ 今日無符合條件的股票

篩選條件：
✅ 法人剛進場 (3-5天)
✅ 體質健康 (PE<25, 營收YoY>10%)
✅ 還沒噴 (5日漲<10%)
✅ 有量能 (今日量>5日均)"""
    else:
        # 有股票時提取關鍵資訊（只取前 5 檔避免訊息過長）
        lines = content.split('\n')

        # 找到表格開始位置
        start_idx = -1
        for i, line in enumerate(lines):
            if '代號' in line and '名稱' in line:
                start_idx = i
                break

        stocks_info = []
        if start_idx != -1:
            # 跳過表頭和分隔線，讀取資料
            for i in range(start_idx + 2, len(lines)):
                line = lines[i].strip()
                if not line or line.startswith('共 ') or line.startswith('='):
                    break

                # 解析欄位（簡化版）
                parts = line.split()
                if len(parts) >= 8:
                    try:
                        num = parts[0]
                        ticker = parts[1]
                        name = parts[2]
                        price = parts[3]
                        change = parts[4]
                        pe = parts[5]
                        inst_5d = parts[6]

                        stocks_info.append(
                            f"{num}. {ticker} {name}\n"
                            f"   價格: {price}元 ({change}) PE:{pe}\n"
                            f"   法人5日: {inst_5d}張"
                        )

                        # 只取前 5 檔
                        if len(stocks_info) >= 5:
                            break
                    except:
                        continue

        if stocks_info:
            stocks_text = '\n\n'.join(stocks_info)
            more_text = f"\n\n...還有 {stock_count - len(stocks_info)} 檔" if stock_count > 5 else ""

            message = f"""📊 選股 BOT v3.1 - {today}

✅ 找到 {stock_count} 檔推薦股票

{stocks_text}{more_text}

篩選條件：
✅ 法人剛進場 (3-5天)
✅ 體質健康 (PE<25, 營收YoY>10%)
✅ 還沒噴 (5日漲<10%)
✅ 有量能 (今日量>5日均)"""
        else:
            message = f"""📊 選股 BOT v3.1 - {today}

找到 {stock_count} 檔符合條件的股票
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
