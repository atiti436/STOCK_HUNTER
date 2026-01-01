#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
持股每日檢查腳本
目的：晚上開電腦時執行一次，快速掌握所有持股狀況

執行方式：
cd d:\\claude-project\\STOCK_HUNTER
python check_holdings.py
"""

import sys
import io
import requests
import urllib3
from datetime import datetime, timedelta
from FinMind.data import DataLoader

# Windows 終端機 UTF-8 設定
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
dl = DataLoader()

# ========== 設定區 ==========
HOLDINGS = [
    {
        'ticker': '3231',
        'name': '緯創',
        'entry_price': 151.0,
        'stop_loss': 145.0,
        'targets': [157.0, 166.0, 181.0],
        'shares': 1  # 張數，請手動更新
    }
    # 新增持股時，在這裡加入
]

# ========== 主程式 ==========

def get_latest_price(ticker):
    """抓取最新股價 (從 FinMind)"""
    try:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

        df = dl.taiwan_stock_daily(
            stock_id=ticker,
            start_date=start_date,
            end_date=end_date
        )

        if df.empty:
            return None

        latest = df.iloc[-1]
        return {
            'date': latest['date'],
            'close': float(latest['close']),
            'change_pct': ((float(latest['close']) - float(latest['open'])) / float(latest['open']) * 100)
        }
    except Exception as e:
        print(f'   [!] {ticker} 股價抓取失敗: {e}')
        return None


def get_institutional_data(ticker, days=5):
    """抓取法人買賣超 (逐日累積)"""
    try:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days+7)).strftime('%Y-%m-%d')

        df = dl.taiwan_stock_institutional_investors(
            stock_id=ticker,
            start_date=start_date,
            end_date=end_date
        )

        if df.empty:
            return None

        # 計算累積 (最近 N 日)
        # FinMind API 回傳的是股數，需要除以 1000 轉成張數
        recent = df.tail(days)
        total = int((recent['buy'].sum() - recent['sell'].sum()) / 1000)

        # 最新單日
        latest = df.iloc[-1]
        latest_total = int((latest['buy'] - latest['sell']) / 1000)

        return {
            'cumulative': total,
            'latest_day': latest_total,
            'date': latest['date']
        }
    except Exception as e:
        print(f'   [!] {ticker} 法人資料抓取失敗: {e}')
        return None


def calculate_signals(holding, price_data, inst_data):
    """計算進出場訊號"""
    current_price = price_data['close']
    entry_price = holding['entry_price']
    stop_loss = holding['stop_loss']
    targets = holding['targets']

    # 計算距離
    profit_pct = (current_price - entry_price) / entry_price * 100
    stop_loss_distance = (current_price - stop_loss) / current_price * 100

    # 訊號判斷
    signals = []

    # 停損檢查
    if current_price <= stop_loss:
        signals.append('[!!!] 已觸及停損! 立即賣出')
    elif stop_loss_distance < 2:
        signals.append(f'[!] 接近停損 (剩 {stop_loss_distance:.1f}%)')

    # 停利檢查
    for i, target in enumerate(targets, 1):
        if current_price >= target:
            signals.append(f'[OK] 已達目標 {i} ({target}元)，可賣 1/3')

    # 法人檢查
    if inst_data:
        if inst_data['cumulative'] < -3000:
            signals.append(f'[!] 法人 5 日累積轉負 ({inst_data["cumulative"]:+,} 張)')
        elif inst_data['latest_day'] < -1000:
            signals.append(f'[!] 法人今日大賣 ({inst_data["latest_day"]:+,} 張)')

    return {
        'profit_pct': profit_pct,
        'stop_loss_distance': stop_loss_distance,
        'signals': signals
    }


def main():
    print('=' * 100)
    print('持股每日檢查報告')
    print('=' * 100)
    print(f'檢查時間: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print()

    if not HOLDINGS:
        print('目前無持股')
        return

    for holding in HOLDINGS:
        ticker = holding['ticker']
        name = holding['name']

        print(f'【{ticker} {name}】')
        print('-' * 100)

        # 抓取資料
        print(f'   抓取最新股價...')
        price_data = get_latest_price(ticker)

        print(f'   抓取法人資料...')
        inst_data = get_institutional_data(ticker, days=5)

        if not price_data:
            print(f'   [X] 無法取得資料\n')
            continue

        # 計算訊號
        result = calculate_signals(holding, price_data, inst_data)

        # 顯示結果
        print()
        print(f'   最新股價: {price_data["close"]:.1f} 元 ({price_data["change_pct"]:+.2f}%)')
        print(f'   目前損益: {result["profit_pct"]:+.2f}% ({price_data["close"] - holding["entry_price"]:+.1f} 元)')
        print(f'   距停損: {result["stop_loss_distance"]:.1f}% ({holding["stop_loss"]} 元)')

        if inst_data:
            print(f'   法人 5 日: {inst_data["cumulative"]:+,} 張 | 今日: {inst_data["latest_day"]:+,} 張')

        # 訊號提示
        if result['signals']:
            print()
            print('   [!] 重要訊號:')
            for signal in result['signals']:
                print(f'      {signal}')
        else:
            print()
            print('   [OK] 持股正常，無需操作')

        print()

    print('=' * 100)
    print('檢查完成')
    print()
    print('操作提醒:')
    print('   - 停損訊號 -> 立即賣出')
    print('   - 停利訊號 -> 分批賣出 (1/3)')
    print('   - 法人轉負 -> 考慮提早出場')
    print('=' * 100)


if __name__ == '__main__':
    main()
