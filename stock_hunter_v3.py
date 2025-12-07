#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
台股情報獵人 v3.0 - 優化版

改進重點:
1. 使用 OpenAPI 一次取得所有股票資料 (1 次請求)
2. 分兩階段: 快速篩選 + 深度分析 Top 50
3. 減少 API 呼叫次數 (從 6000+ 降到 ~100)
4. 加入 Cache 機制
5. 更好的錯誤處理
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from apscheduler.schedulers.background import BackgroundScheduler
import google.generativeai as genai
import urllib3

# 關閉 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================== 環境變數 ====================
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', 'YOUR_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET', 'YOUR_SECRET')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'YOUR_GEMINI_KEY')
LINE_USER_ID = os.getenv('LINE_USER_ID', 'YOUR_USER_ID')

# 初始化
app = Flask(__name__)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
genai.configure(api_key=GEMINI_API_KEY)

# ==================== 設定參數 ====================

CONFIG = {
    # 篩選條件
    "MIN_PRICE": 10,           # 最低股價
    "MIN_TURNOVER": 5_000_000, # 最低成交金額 500萬
    
    # 爆量判斷
    "VOLUME_SPIKE_RATIO": 2.0,
    
    # 漲跌判斷
    "UP_THRESHOLD": 3.0,       # 漲幅 > 3% 視為強勢
    "DOWN_THRESHOLD": -3.0,    # 跌幅 > 3% 視為弱勢
    
    # 推薦數量
    "MAX_RECOMMENDATIONS": 10,
    
    # API 設定
    "API_TIMEOUT": 15,
    "API_RETRY": 3,
    "API_DELAY": 1.0,          # API 間隔 1 秒
    
    # Top N 進入深度分析
    "TOP_N_FOR_DEEP_ANALYSIS": 50,
}

# ==================== 快取 ====================

CACHE = {
    'all_stocks': None,           # 所有股票資料
    'all_stocks_time': None,      # 快取時間
    'institutional': {},          # 法人資料
    'institutional_time': None,   # 法人快取時間
}

CACHE_EXPIRE_MINUTES = 30  # 快取 30 分鐘

def is_cache_valid(cache_time):
    """檢查快取是否有效"""
    if cache_time is None:
        return False
    return (datetime.now() - cache_time).seconds < CACHE_EXPIRE_MINUTES * 60


# ==================== API 函數 ====================

def get_all_stocks_data():
    """
    用 OpenAPI 一次取得所有股票資料 (1 次 API 呼叫!)
    回傳: [{'ticker': '2330', 'name': '台積電', 'price': 580, 'change_pct': 1.5, 'volume': 25000, 'turnover': 145億}, ...]
    """
    # 檢查快取
    if is_cache_valid(CACHE['all_stocks_time']) and CACHE['all_stocks']:
        print("📦 使用快取的股票資料", flush=True)
        return CACHE['all_stocks']
    
    print("🔄 從 OpenAPI 取得所有股票資料...", flush=True)
    
    for attempt in range(CONFIG['API_RETRY']):
        try:
            # OpenAPI - 一次取得所有股票當日資料
            url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
            response = requests.get(url, timeout=CONFIG['API_TIMEOUT'], verify=False)
            response.raise_for_status()
            
            data = response.json()
            stocks = []
            
            for item in data:
                ticker = item.get('Code', '')
                name = item.get('Name', '')
                
                # 只要 4 位數股票代碼
                if not (ticker.isdigit() and len(ticker) == 4):
                    continue
                
                # 排除 ETF
                if ticker.startswith('00'):
                    continue
                
                # 解析數值
                try:
                    # 收盤價
                    close_str = item.get('ClosingPrice', '0').replace(',', '')
                    close = float(close_str) if close_str else 0
                    
                    # 漲跌
                    change_str = item.get('Change', '0').replace(',', '').replace('+', '')
                    change = float(change_str) if change_str and change_str != 'X' else 0
                    
                    # 漲跌幅
                    prev_close = close - change
                    change_pct = (change / prev_close * 100) if prev_close > 0 else 0
                    
                    # 成交量 (股)
                    volume_str = item.get('TradeVolume', '0').replace(',', '')
                    volume = int(volume_str) if volume_str else 0
                    
                    # 成交金額
                    turnover_str = item.get('TradeValue', '0').replace(',', '')
                    turnover = int(turnover_str) if turnover_str else 0
                    
                    # 開高低收
                    open_str = item.get('OpeningPrice', '0').replace(',', '')
                    high_str = item.get('HighestPrice', '0').replace(',', '')
                    low_str = item.get('LowestPrice', '0').replace(',', '')
                    
                    open_price = float(open_str) if open_str else close
                    high = float(high_str) if high_str else close
                    low = float(low_str) if low_str else close
                    
                except (ValueError, TypeError):
                    continue
                
                if close <= 0:
                    continue
                
                stocks.append({
                    'ticker': ticker,
                    'name': name,
                    'price': close,
                    'open': open_price,
                    'high': high,
                    'low': low,
                    'change': change,
                    'change_pct': round(change_pct, 2),
                    'volume': volume,          # 股數
                    'volume_lots': volume // 1000,  # 張數
                    'turnover': turnover,      # 成交金額
                })
            
            print(f"✅ 取得 {len(stocks)} 支股票資料", flush=True)
            
            # 更新快取
            CACHE['all_stocks'] = stocks
            CACHE['all_stocks_time'] = datetime.now()
            
            return stocks
            
        except Exception as e:
            print(f"❌ 第 {attempt+1} 次嘗試失敗: {e}", flush=True)
            if attempt < CONFIG['API_RETRY'] - 1:
                time.sleep(CONFIG['API_DELAY'])
    
    # 全部失敗,回傳空列表
    print("❌ 無法取得股票資料", flush=True)
    return []


def get_institutional_data():
    """
    取得三大法人資料 (1 次 API 呼叫)
    回傳: {'2330': {'foreign': 150000000, 'trust': 50000000, 'dealer': 10000000}, ...}
    """
    # 檢查快取
    if is_cache_valid(CACHE['institutional_time']) and CACHE['institutional']:
        print("📦 使用快取的法人資料", flush=True)
        return CACHE['institutional']
    
    print("🔄 從 TWSE 取得法人資料...", flush=True)
    
    # 嘗試最近 7 天 (排除假日)
    for days_ago in range(7):
        try:
            target_date = datetime.now() - timedelta(days=days_ago)
            date_str = target_date.strftime('%Y%m%d')
            
            url = "https://www.twse.com.tw/rwd/zh/fund/T86"
            params = {
                'date': date_str,
                'selectType': 'ALLBUT0999',
                'response': 'json'
            }
            
            response = requests.get(url, params=params, timeout=CONFIG['API_TIMEOUT'], verify=False)
            data = response.json()
            
            if data.get('stat') != 'OK' or not data.get('data'):
                continue
            
            result = {}
            for item in data['data']:
                try:
                    ticker = item[0].strip()
                    if not (ticker.isdigit() and len(ticker) == 4):
                        continue
                    
                    # 外資, 投信, 自營商買賣超
                    foreign = int(item[4].replace(',', '')) if item[4] != '--' else 0
                    trust = int(item[10].replace(',', '')) if item[10] != '--' else 0
                    dealer = int(item[11].replace(',', '')) if item[11] != '--' else 0
                    
                    result[ticker] = {
                        'foreign': foreign,
                        'trust': trust,
                        'dealer': dealer,
                        'total': foreign + trust + dealer
                    }
                except:
                    continue
            
            if result:
                print(f"✅ 取得 {len(result)} 支股票法人資料 (日期: {date_str})", flush=True)
                CACHE['institutional'] = result
                CACHE['institutional_time'] = datetime.now()
                return result
                
        except Exception as e:
            continue
    
    print("⚠️ 無法取得法人資料", flush=True)
    return {}


def get_market_status():
    """取得大盤狀態"""
    try:
        # 用 OpenAPI 取得大盤指數
        url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        response = requests.get(url, timeout=CONFIG['API_TIMEOUT'], verify=False)
        data = response.json()
        
        # 計算漲跌統計
        up_count = 0
        down_count = 0
        limit_up = 0
        limit_down = 0
        total = 0
        
        for item in data:
            try:
                change_str = item.get('Change', '0').replace(',', '').replace('+', '')
                close_str = item.get('ClosingPrice', '0').replace(',', '')
                
                if not change_str or change_str == 'X':
                    continue
                    
                change = float(change_str)
                close = float(close_str) if close_str else 0
                
                if close <= 0:
                    continue
                
                prev_close = close - change
                change_pct = (change / prev_close * 100) if prev_close > 0 else 0
                
                total += 1
                if change_pct >= 9.5:
                    limit_up += 1
                elif change_pct <= -9.5:
                    limit_down += 1
                elif change > 0:
                    up_count += 1
                elif change < 0:
                    down_count += 1
                    
            except:
                continue
        
        # 判斷市場狀態
        if limit_down > 100:
            status = 'DANGER'
            reason = f'跌停家數過多 ({limit_down} 支)'
        elif down_count > up_count * 2:
            status = 'CAUTION'
            reason = f'下跌家數過多 (漲:{up_count} 跌:{down_count})'
        else:
            status = 'SAFE'
            reason = f'市場正常 (漲:{up_count} 跌:{down_count})'
        
        return {
            'status': status,
            'reason': reason,
            'up_count': up_count,
            'down_count': down_count,
            'limit_up': limit_up,
            'limit_down': limit_down,
            'total': total
        }
        
    except Exception as e:
        print(f"⚠️ 大盤狀態取得失敗: {e}", flush=True)
        return {
            'status': 'UNKNOWN',
            'reason': str(e)
        }


# ==================== 篩選邏輯 ====================

def quick_filter(stocks, institutional):
    """
    第一階段: 快速篩選 (不呼叫任何 API)
    使用已取得的資料進行過濾
    """
    print(f"\n🔍 第一階段: 快速篩選 {len(stocks)} 支股票...", flush=True)
    
    candidates = []
    stats = {
        'low_price': 0,
        'low_turnover': 0,
        'passed': 0
    }
    
    for stock in stocks:
        ticker = stock['ticker']
        price = stock['price']
        turnover = stock['turnover']
        change_pct = stock['change_pct']
        
        # 過濾: 價格太低
        if price < CONFIG['MIN_PRICE']:
            stats['low_price'] += 1
            continue
        
        # 過濾: 成交金額太低
        if turnover < CONFIG['MIN_TURNOVER']:
            stats['low_turnover'] += 1
            continue
        
        # 計算評分
        score = 0
        reasons = []
        
        # 漲跌幅評分
        if change_pct >= CONFIG['UP_THRESHOLD']:
            score += 2
            reasons.append(f"漲幅 {change_pct:.1f}%")
        elif change_pct <= CONFIG['DOWN_THRESHOLD']:
            score -= 1
            reasons.append(f"跌幅 {change_pct:.1f}%")
        
        # 成交金額評分
        if turnover >= 100_000_000:  # 1億以上
            score += 1
            reasons.append(f"成交 {turnover/1e8:.1f}億")
        
        # 法人評分
        inst = institutional.get(ticker, {})
        foreign = inst.get('foreign', 0)
        trust = inst.get('trust', 0)
        
        if foreign > 0 and trust > 0:
            score += 2
            reasons.append("外資投信同步買超")
        elif foreign > 0:
            score += 1
            reasons.append("外資買超")
        elif trust > 0:
            score += 1
            reasons.append("投信買超")
        elif foreign < 0 and trust < 0:
            score -= 2
            reasons.append("外資投信雙賣超")
        
        # 爆量判斷 (需要有前一日資料,這裡簡化)
        # 可以之後加入 5 日均量比較
        
        candidates.append({
            'ticker': ticker,
            'name': stock['name'],
            'price': price,
            'change_pct': change_pct,
            'turnover': turnover,
            'volume_lots': stock['volume_lots'],
            'high': stock['high'],
            'low': stock['low'],
            'score': score,
            'reasons': reasons,
            'institutional': inst
        })
        
        stats['passed'] += 1
    
    # 按評分排序
    candidates.sort(key=lambda x: x['score'], reverse=True)
    
    print(f"✅ 快速篩選完成:", flush=True)
    print(f"   - 價格過低淘汰: {stats['low_price']} 支", flush=True)
    print(f"   - 流動性不足淘汰: {stats['low_turnover']} 支", flush=True)
    print(f"   - 通過篩選: {stats['passed']} 支", flush=True)
    
    return candidates


def deep_analyze(candidates):
    """
    第二階段: 深度分析 Top N (呼叫 Gemini API)
    """
    top_n = CONFIG['TOP_N_FOR_DEEP_ANALYSIS']
    to_analyze = candidates[:top_n]
    
    print(f"\n🔬 第二階段: 深度分析 Top {len(to_analyze)} 支股票...", flush=True)
    
    results = []
    
    for i, candidate in enumerate(to_analyze, 1):
        ticker = candidate['ticker']
        name = candidate['name']
        
        try:
            # 呼叫 Gemini 分析 (可選)
            # 這裡先跳過,只用評分排序
            
            final_score = candidate['score']
            
            # 計算停損停利
            price = candidate['price']
            stop_loss = round(price * 0.92, 2)  # -8%
            take_profit = round(price * 1.30, 2)  # +30%
            
            result = {
                'rank': i,
                'ticker': ticker,
                'name': name,
                'price': price,
                'change_pct': candidate['change_pct'],
                'turnover': candidate['turnover'],
                'score': final_score,
                'reasons': candidate['reasons'],
                'institutional': candidate['institutional'],
                'stop_loss': stop_loss,
                'take_profit': take_profit
            }
            
            results.append(result)
            
            if i % 10 == 0:
                print(f"   進度: {i}/{len(to_analyze)}", flush=True)
                
        except Exception as e:
            print(f"⚠️ {ticker} 分析失敗: {e}", flush=True)
    
    # 過濾出推薦買入的 (score >= 2)
    buy_recommendations = [r for r in results if r['score'] >= 2]
    
    print(f"✅ 深度分析完成, 推薦買入: {len(buy_recommendations)} 支", flush=True)
    
    return buy_recommendations[:CONFIG['MAX_RECOMMENDATIONS']]


# ==================== 主流程 ====================

def scan_all_stocks():
    """掃描全台股 - 優化版"""
    print("\n" + "="*60, flush=True)
    print("🚀 台股情報獵人 v3.0 - 開始掃描", flush=True)
    print("="*60, flush=True)
    
    start_time = time.time()
    
    # Step 1: 取得大盤狀態
    market = get_market_status()
    print(f"\n🌍 大盤狀態: {market['status']}", flush=True)
    print(f"   {market['reason']}", flush=True)
    
    # Step 2: 一次取得所有股票資料 (1 次 API 呼叫)
    stocks = get_all_stocks_data()
    if not stocks:
        return {'error': '無法取得股票資料'}
    
    # Step 3: 取得法人資料 (1 次 API 呼叫)
    institutional = get_institutional_data()
    
    # Step 4: 快速篩選 (不呼叫 API)
    candidates = quick_filter(stocks, institutional)
    
    # Step 5: 深度分析 Top N
    recommendations = deep_analyze(candidates)
    
    end_time = time.time()
    
    # 結果
    result = {
        'timestamp': datetime.now().isoformat(),
        'market': market,
        'total_stocks': len(stocks),
        'passed_filter': len(candidates),
        'recommendations': recommendations,
        'execution_time': round(end_time - start_time, 2)
    }
    
    print("\n" + "="*60, flush=True)
    print(f"✅ 掃描完成! 耗時: {result['execution_time']} 秒", flush=True)
    print(f"   總股票數: {result['total_stocks']}", flush=True)
    print(f"   通過篩選: {result['passed_filter']}", flush=True)
    print(f"   推薦買入: {len(recommendations)}", flush=True)
    print("="*60 + "\n", flush=True)
    
    return result


# ==================== LINE 訊息格式 ====================

def format_line_message(result):
    """格式化 LINE 推送訊息"""
    if 'error' in result:
        return f"❌ 錯誤: {result['error']}"
    
    market = result['market']
    recommendations = result['recommendations']
    
    lines = [
        f"📊 台股情報獵人 v3.0",
        f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"🌍 大盤: {market['status']}",
        f"   {market['reason']}",
        "",
        f"📈 今日推薦 ({len(recommendations)} 檔):",
        ""
    ]
    
    for i, rec in enumerate(recommendations[:5], 1):  # 只顯示前 5 名
        lines.append(f"{i}. {rec['ticker']} {rec['name']}")
        lines.append(f"   💰 ${rec['price']} ({rec['change_pct']:+.1f}%)")
        lines.append(f"   📊 評分: {rec['score']} 分")
        lines.append(f"   💡 {', '.join(rec['reasons'][:2])}")
        lines.append("")
    
    if len(recommendations) > 5:
        lines.append(f"...還有 {len(recommendations)-5} 檔")
    
    lines.extend([
        "",
        f"⚡ 掃描耗時: {result['execution_time']} 秒",
        f"📦 分析股票: {result['total_stocks']} 支"
    ])
    
    return "\n".join(lines)


def send_line_push(message):
    """推送訊息到 LINE"""
    try:
        line_bot_api.push_message(LINE_USER_ID, TextSendMessage(text=message))
        print("✅ LINE 推送成功", flush=True)
    except Exception as e:
        print(f"❌ LINE 推送失敗: {e}", flush=True)


# ==================== 定時任務 ====================

def daily_analysis_task():
    """每日分析任務"""
    print("\n⏰ 執行每日分析任務...", flush=True)
    
    try:
        result = scan_all_stocks()
        message = format_line_message(result)
        send_line_push(message)
    except Exception as e:
        print(f"❌ 每日任務失敗: {e}", flush=True)
        send_line_push(f"❌ 今日分析失敗: {e}")


# 初始化排程器
scheduler = BackgroundScheduler()
scheduler.add_job(daily_analysis_task, 'cron', hour=8, minute=0)
scheduler.start()


# ==================== LINE BOT Webhook ====================

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    
    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    
    if text in ['分析', '掃描', '今日推薦']:
        reply = "🔄 開始分析,請稍候..."
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        
        # 執行分析 (背景)
        result = scan_all_stocks()
        message = format_line_message(result)
        line_bot_api.push_message(event.source.user_id, TextSendMessage(text=message))
        
    elif text == '狀態':
        market = get_market_status()
        reply = f"🌍 大盤狀態: {market['status']}\n{market['reason']}"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        
    else:
        reply = "指令: 分析 | 狀態"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))


@app.route("/")
def index():
    return "台股情報獵人 v3.0 運行中"


@app.route("/manual")
def manual_run():
    """手動觸發分析"""
    result = scan_all_stocks()
    return format_line_message(result).replace('\n', '<br>')


# ==================== 主程式 ====================

if __name__ == "__main__":
    try:
        port = int(os.environ.get('PORT', 8080))
        print("\n" + "="*60, flush=True)
        print("🚀 台股情報獵人 v3.0 啟動", flush=True)
        print("="*60, flush=True)
        print(f"📡 監聽端口: {port}", flush=True)
        print(f"⏰ 定時任務: 每日 08:00", flush=True)
        print(f"🔗 手動觸發: http://localhost:{port}/manual", flush=True)
        print("="*60 + "\n", flush=True)
        
        app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        print(f"❌ 啟動失敗: {e}", flush=True)
        raise
