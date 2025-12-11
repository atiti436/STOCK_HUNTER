#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
台股情報獵人 v4.2 - AI 建議版

改進重點:
1. 使用 OpenAPI 一次取得所有股票資料
2. 分兩階段: 快速篩選 + 深度分析 Top 15
3. 升級 Gemini 2.5 Pro 智能分析
4. 新增停利目標 + 風報比計算
5. CDP 價格對齊 tick size
6. 當沖排除金融股
7. 管理員權限控制
"""

print("Starting Stock Hunter...", flush=True)

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
ADMIN_USER_ID = os.getenv('ADMIN_USER_ID', 'U7130f999bd008719fe5058ef31059522')  # 環境變數優先，否則用預設
DISABLE_GEMINI = os.getenv('DISABLE_GEMINI', 'false').lower() == 'true'  # 設為 true 關閉 Gemini

# 初始化
app = Flask(__name__)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
genai.configure(api_key=GEMINI_API_KEY)

# ==================== 設定參數 ====================

CONFIG = {
    # 篩選條件 (v4.4)
    "MIN_PRICE": 10,           # 最低股價
    "MAX_PRICE": 200,          # 最高股價：過濾高價股
    "MIN_TURNOVER": 5_000_000, # 最低成交金額 500萬
    "MIN_VOLUME": 300,         # 最低成交量 300張
    
    # 爆量判斷
    "VOLUME_SPIKE_RATIO": 2.0,
    
    # 漲跌判斷
    "UP_THRESHOLD": 3.0,       # 漲幅 > 3% 視為強勢
    "DOWN_THRESHOLD": -3.0,    # 跌幅 > 3% 視為弱勢
    
    # 位階過濾
    "MAX_5D_GAIN": 10,         # 5日漲幅上限 10%
    "MAX_10D_GAIN": 15,        # 10日漲幅上限 15%
    
    # 推薦數量 (v4.4: 8:00 只推波段)
    "DAY_TRADE_MAX": 3,        # 當沖最多顯示 3 檔（指令觸發）
    "SWING_TRADE_MAX": 5,      # 波段最多顯示 5 檔（8:00 推播）
    
    # 評分門檻 (v4.4: 波段提高到 5 分)
    "DAY_TRADE_SCORE_THRESHOLD": 4,   # 當沖 ≥4 分
    "SWING_TRADE_SCORE_THRESHOLD": 5, # 波段 ≥5 分
    
    # API 設定
    "API_TIMEOUT": 15,
    "API_RETRY": 3,
    "API_DELAY": 1.0,
    
    # Top N 進入深度分析 (v4.4: 8 檔，批次 Gemini)
    "TOP_N_FOR_DEEP_ANALYSIS": 8,
}

# ==================== 快取 ====================

CACHE = {
    'all_stocks': None,           # 所有股票資料
    'all_stocks_time': None,      # 快取時間
    'institutional': {},          # 法人資料
    'institutional_time': None,   # 法人快取時間
    'pe_ratio': {},               # 本益比資料
    'pe_ratio_time': None,
    'margin_trading': {},         # 融資融券資料
    'margin_trading_time': None,
}

CACHE_EXPIRE_MINUTES = 30  # 快取 30 分鐘

# ==================== 查詢次數限制 ====================

USER_QUERY_COUNT = {}  # {user_id: {'date': '2024-12-10', 'count': 3}}
DAILY_QUERY_LIMIT = 3  # 非管理員每日查詢上限

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


def get_pe_ratio_data():
    """取得本益比資料 (P/E Ratio)"""
    # 檢查快取
    if is_cache_valid(CACHE['pe_ratio_time']) and CACHE['pe_ratio']:
        return CACHE['pe_ratio']
    
    try:
        url = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
        response = requests.get(url, timeout=CONFIG['API_TIMEOUT'], verify=False)
        data = response.json()
        
        result = {}
        for item in data:
            ticker = item.get('Code', '').strip()
            if not ticker or not ticker.isdigit():
                continue
            
            try:
                pe_str = item.get('PEratio', '').strip()
                pb_str = item.get('PBratio', '').strip()
                dy_str = item.get('DividendYield', '').strip()
                
                result[ticker] = {
                    'pe': float(pe_str) if pe_str and pe_str != '-' else None,
                    'pb': float(pb_str) if pb_str and pb_str != '-' else None,
                    'dividend_yield': float(dy_str) if dy_str and dy_str != '-' else None
                }
            except:
                continue
        
        if result:
            print(f"✅ 取得 {len(result)} 支股票本益比資料", flush=True)
            CACHE['pe_ratio'] = result
            CACHE['pe_ratio_time'] = datetime.now()
        
        return result
    except Exception as e:
        print(f"⚠️ 本益比資料取得失敗: {e}", flush=True)
        return {}


def get_margin_trading_data():
    """取得融資融券資料"""
    # 檢查快取
    if is_cache_valid(CACHE['margin_trading_time']) and CACHE['margin_trading']:
        return CACHE['margin_trading']
    
    try:
        # 嘗試最近 7 天 (假日沒資料)
        for days_ago in range(7):
            target_date = datetime.now() - timedelta(days=days_ago)
            date_str = target_date.strftime('%Y%m%d')
            
            url = "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN"
            params = {
                'date': date_str,
                'selectType': 'ALL',
                'response': 'json'
            }
            
            try:
                response = requests.get(url, params=params, timeout=CONFIG['API_TIMEOUT'], verify=False)
                data = response.json()
                
                if data.get('stat') != 'OK' or not data.get('tables'):
                    continue
                
                # 找到個股融資融券資料表
                result = {}
                for table in data.get('tables', []):
                    if '融資' in table.get('title', '') or not table.get('data'):
                        # 這個表格可能是個股資料
                        for item in table.get('data', []):
                            try:
                                if len(item) < 12:
                                    continue
                                ticker = item[0].strip()
                                if not ticker.isdigit() or len(ticker) != 4:
                                    continue
                                
                                # 融資餘額 (張)
                                margin_buy = int(item[3].replace(',', '')) if item[3] != '-' else 0
                                # 融券餘額 (張)  
                                short_sell = int(item[9].replace(',', '')) if item[9] != '-' else 0
                                
                                # 券資比
                                ratio = round(short_sell / margin_buy * 100, 1) if margin_buy > 0 else 0
                                
                                result[ticker] = {
                                    'margin_buy': margin_buy,
                                    'short_sell': short_sell,
                                    'ratio': ratio
                                }
                            except:
                                continue
                
                if result:
                    print(f"✅ 取得 {len(result)} 支股票融資融券資料 (日期: {date_str})", flush=True)
                    CACHE['margin_trading'] = result
                    CACHE['margin_trading_time'] = datetime.now()
                    return result
            except:
                continue
        
        print("⚠️ 無法取得融資融券資料", flush=True)
        return {}
    except Exception as e:
        print(f"⚠️ 融資融券資料取得失敗: {e}", flush=True)
        return {}


def get_market_index():
    """取得大盤指數 (加權指數點數)"""
    try:
        # 嘗試最近 7 天
        for days_ago in range(7):
            target_date = datetime.now() - timedelta(days=days_ago)
            date_str = target_date.strftime('%Y%m%d')
            
            url = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
            params = {'date': date_str, 'response': 'json'}
            
            response = requests.get(url, params=params, timeout=CONFIG['API_TIMEOUT'], verify=False)
            data = response.json()
            
            if data.get('stat') == 'OK' and data.get('data1'):
                # data1[0] 是加權指數
                taiex_str = data['data1'][0][1].replace(',', '')
                taiex = float(taiex_str)
                used_date = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:]}"
                print(f"✅ 大盤指數: {int(taiex):,} 點 ({used_date})", flush=True)
                return {
                    'index': int(taiex),
                    'date': used_date,
                    'success': True
                }
        
        return {'index': 0, 'date': '', 'success': False}
    except Exception as e:
        print(f"⚠️ 大盤指數取得失敗: {e}", flush=True)
        return {'index': 0, 'date': '', 'success': False}


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
        
        # 取得大盤指數
        index_data = get_market_index()
        
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
            'total': total,
            'index': index_data.get('index', 0),
            'index_date': index_data.get('date', '')
        }
        
    except Exception as e:
        print(f"⚠️ 大盤狀態取得失敗: {e}", flush=True)
        return {
            'status': 'UNKNOWN',
            'reason': str(e),
            'index': 0
        }


# ==================== 新聞情緒 AI ====================

import xml.etree.ElementTree as ET

# 股票關鍵字對應表
NEWS_KEYWORDS = {
    "2330": ["台積電", "TSMC", "TSM", "張忠謀", "魏哲家", "3奈米", "CoWoS", "黃仁勳", "NVIDIA"],
    "2454": ["聯發科", "MediaTek", "蔡明介", "天璣", "5G晶片"],
    "2317": ["鴻海", "Foxconn", "郭台銘", "劉揚偉", "iPhone", "GB200"],
    "2308": ["台達電", "Delta", "鄭平", "AI電源"],
    "2382": ["廣達", "林百里", "AI伺服器", "GB200"],
    "3231": ["緯創", "林憲銘", "AI伺服器"],
}

MACRO_KEYWORDS = ["川普", "Trump", "關稅", "聯準會", "Fed", "降息", "美股", "台股"]


def get_macro_news():
    """抓取總經新聞 (川普、Fed)"""
    try:
        query = " OR ".join(MACRO_KEYWORDS)
        url = f"https://news.google.com/rss/search?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        news_items = []
        
        for item in root.findall('.//item')[:3]:
            title = item.find('title').text
            if ' - ' in title:
                title = title.split(' - ')[0]
            news_items.append(title)
            
        return news_items
    except Exception as e:
        print(f"⚠️ 國際新聞抓取失敗: {e}", flush=True)
        return []


def get_stock_news(ticker, name):
    """抓取股票相關新聞"""
    try:
        keywords = NEWS_KEYWORDS.get(ticker, [name])
        query = " OR ".join(keywords)
        url = f"https://news.google.com/rss/search?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        news_items = []
        
        for item in root.findall('.//item')[:12]:  # v4.5: 擴大從 3 筆改為 12 筆
            title = item.find('title').text
            if ' - ' in title:
                title = title.split(' - ')[0]
            news_items.append(title)
            
        return news_items
    except Exception as e:
        return []


def analyze_news_sentiment(ticker, name, news_list):
    """使用 Gemini API 分析新聞情緒 (向下相容)"""
    # 向下相容: 如果新版函數失敗,這個函數仍可用
    if not news_list:
        return {'sentiment': 0, 'summary': '無相關新聞'}
    
    try:
        model = genai.GenerativeModel('gemini-2.5-pro')  # 強制使用 2.5 Pro
        
        news_text = "\n".join([f"{i+1}. {news}" for i, news in enumerate(news_list[:5])])
        
        prompt = f"""請分析以下新聞對「{name}（{ticker}）」股價的影響：

{news_text}

請給出：
1. 綜合情緒分數（-1 到 +1，-1=極負面，0=中性，+1=極正面）
2. 一句話摘要（15字內）

請用 JSON 格式回答：
{{
  "sentiment": 0.5,
  "summary": "法人看好，訂單強勁"
}}"""
        
        response = model.generate_content(prompt)
        result_text = response.text.strip()
        
        # 解析 JSON
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()
        
        result = json.loads(result_text)
        
        return {
            'sentiment': float(result.get('sentiment', 0)),
            'summary': result.get('summary', '無摘要')
        }
        
    except Exception as e:
        print(f"⚠️ {ticker} 新聞分析失敗: {e}", flush=True)
        return {'sentiment': 0, 'summary': '分析失敗'}


def analyze_stock_with_gemini(ticker, name, price, change_pct, ma60_status, institutional_data, news_titles):
    """
    v4.5: 使用 Gemini 2.5 Pro 進行綜合操盤建議
    
    Args:
        ticker: 股票代碼
        name: 股票名稱
        price: 現價
        change_pct: 漲跌幅
        ma60_status: 是否站上季線 (True/False)
        institutional_data: 籌碼資訊字串
        news_titles: 新聞標題列表
    
    Returns:
        {'gemini_score': 0.8, 'gemini_comment': '老公G的短評'}
    """
    # 如果 DISABLE_GEMINI 為 true，跳過 API 呼叫
    if DISABLE_GEMINI:
        print(f"⚠️ {ticker} Gemini 已停用 (DISABLE_GEMINI=true)", flush=True)
        return {'gemini_score': 0, 'gemini_comment': '(Gemini 已停用)'}
    
    try:
        model = genai.GenerativeModel('gemini-2.5-pro')  # 強制使用 2.5 Pro！絕不降版！
        
        # 準備新聞文字
        news_text = "\n".join([f"• {news}" for news in news_titles[:10]]) if news_titles else "無近期新聞"
        
        # 技術面狀態
        tech_status = "股價站上生命線(季線)，趨勢偏多 ✅" if ma60_status else "股價跌破生命線(季線)，趨勢偏空 ❌"
        
        prompt = f"""角色：你是一位精明的台股波段交易員「AI_G」，擅長結合技術面與題材面。
任務：分析以下股票，判斷是否值得進場操作。

【股票資訊】
- 代號：{ticker} {name}
- 現價：{price} (漲跌幅: {change_pct:+.1f}%)
- 技術面：{tech_status}
- 籌碼面：{institutional_data}

【近期新聞標題】
{news_text}

【分析邏輯】
1. 過濾雜訊：忽略股東會公告、除息等例行公事。
2. 尋找題材：是否有 AI、矽光子、機器人、營收創高、漲價等關鍵利多？
3. 綜合判斷：
   - 如果技術面站上季線 + 有題材 = 強力推薦 (給高分 0.6~1.0)
   - 如果技術面跌破季線 + 有題材 = 小心誘多 (給低分 -0.3~0.3)
   - 如果沒題材 = 觀望 (給中性分數 0~0.3)

【輸出格式】
請回傳純 JSON 格式，不要有 Markdown 標記：
{{
    "sentiment_score": 0.8,
    "comment": "站上季線且具CPO題材，建議波段操作"
}}

注意：comment 限 25 字以內，要犀利點評！"""

        response = model.generate_content(prompt)
        result_text = response.text.strip()
        
        # 解析 JSON
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()
        
        result = json.loads(result_text)
        
        gemini_score = float(result.get('sentiment_score', 0))
        gemini_comment = result.get('comment', '暫無評論')
        
        print(f"🧠 {ticker} AI_G短評: {gemini_comment} (分數: {gemini_score:.2f})", flush=True)
        
        return {
            'gemini_score': gemini_score,
            'gemini_comment': gemini_comment
        }
        
    except json.JSONDecodeError as e:
        print(f"⚠️ {ticker} Gemini JSON 解析失敗: {e}", flush=True)
        return {'gemini_score': 0, 'gemini_comment': '暫無 AI 分析'}
    except Exception as e:
        print(f"⚠️ {ticker} Gemini 分析失敗: {e}", flush=True)
        return {'gemini_score': 0, 'gemini_comment': '暫無 AI 分析'}


# ==================== v4.4: 批次 Gemini 分析 ====================

def batch_gemini_analysis(stocks_data):
    """
    v4.4: 批次 Gemini 分析 - 一次呼叫分析多檔股票
    取代原本的 1 檔 1 次呼叫
    """
    if not stocks_data:
        return []
    
    try:
        model = genai.GenerativeModel('gemini-2.5-pro')
        
        # 準備股票資訊
        stock_details = []
        for i, stock in enumerate(stocks_data, 1):
            detail = f"""【{i}. {stock['ticker']} {stock['name']}】
價格: ${stock['price']} ({stock['change_pct']:+.1f}%)
MA20距離: {stock.get('ma20_distance', 'N/A')}%
RSI: {stock.get('rsi', 'N/A')}
外資: {stock.get('foreign', 0)}張
投信: {stock.get('trust', 0)}張
新聞: {', '.join(stock.get('news', [])[:2]) or '無'}"""
            stock_details.append(detail)
        
        stocks_text = "\n\n".join(stock_details)
        
        prompt = f"""你是專業台股分析師，請分析以下 {len(stocks_data)} 檔股票。

{stocks_text}

【分析要求】
針對每檔股票評估:
1. 適合波段操作? (✅適合/⚠️觀望/❌不適合)
2. 主要風險? (10字內)
3. 推薦理由? (15字內)
4. 新聞情緒分數? (-1.0到+1.0)

【重要】
- 必須按股票順序回傳
- 如果資訊不足，填"資訊不足"
- sentiment必須是數字

【JSON格式】
[
  {{
    "code": "2330",
    "suitable": "✅適合",
    "risk": "漲多回檔",
    "reason": "站穩MA20+法人買",
    "sentiment": 0.5
  }}
]

請只回傳 JSON，不要其他文字。"""
        
        response = model.generate_content(prompt)
        result_text = response.text.strip()
        
        # 解析 JSON
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()
        
        results = json.loads(result_text)
        
        # 確保結果數量正確
        if len(results) != len(stocks_data):
            print(f"⚠️ Gemini 回傳數量不符: {len(results)} vs {len(stocks_data)}", flush=True)
        
        # 填補缺失欄位
        for result in results:
            if 'sentiment' not in result:
                result['sentiment'] = 0.0
            if 'suitable' not in result:
                result['suitable'] = '⚠️觀望'
            if 'risk' not in result:
                result['risk'] = '資訊不足'
            if 'reason' not in result:
                result['reason'] = '資訊不足'
        
        print(f"✅ 批次 Gemini 分析完成: {len(results)} 檔", flush=True)
        return results
        
    except json.JSONDecodeError as e:
        print(f"❌ Gemini JSON 解析失敗: {e}", flush=True)
        # 降級: 回傳預設值
        return [{'code': s['ticker'], 'suitable': '⚠️觀望', 'risk': '分析失敗', 'reason': '分析失敗', 'sentiment': 0} for s in stocks_data]
    except Exception as e:
        print(f"❌ 批次 Gemini 分析失敗: {e}", flush=True)
        return [{'code': s['ticker'], 'suitable': '⚠️觀望', 'risk': '分析失敗', 'reason': '分析失敗', 'sentiment': 0} for s in stocks_data]


def analyze_market_and_risk(stocks_list, industry_trend):
    """
    v4.4: 市場趨勢 + 風險檢查 (合併為 1 次 API 呼叫)
    """
    if not stocks_list:
        return {'market_summary': '', 'risk_warning': ''}
    
    try:
        model = genai.GenerativeModel('gemini-2.5-pro')
        
        # 準備推薦股票清單
        stock_names = [f"{s['ticker']} {s['name']}" for s in stocks_list[:5]]
        stock_list_text = "\n".join([f"{i+1}. {name}" for i, name in enumerate(stock_names)])
        
        # 產業趨勢
        strong = ", ".join([f"{i[0]}({i[1]:+.1f}%)" for i in industry_trend.get('strong', [])[:3]])
        weak = ", ".join([f"{i[0]}({i[1]:+.1f}%)" for i in industry_trend.get('weak', [])[:3]])
        
        prompt = f"""你是專業股市分析師，請分析今日市場狀況。

【今日強勢產業】{strong}
【今日弱勢產業】{weak}

【今日推薦股票】
{stock_list_text}

請給出:
1. 今日市場趨勢 (20字內，說明偏好產業和情緒)
2. 風險提示 (檢查推薦清單，20字內)

JSON格式:
{{
  "market_summary": "AI概念股續強，資金偏好電子",
  "risk_warning": "推薦分散良好，無明顯地雷"
}}

請只回傳 JSON。"""
        
        response = model.generate_content(prompt)
        result_text = response.text.strip()
        
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()
        
        result = json.loads(result_text)
        
        print(f"✅ 市場趨勢分析完成", flush=True)
        return {
            'market_summary': result.get('market_summary', ''),
            'risk_warning': result.get('risk_warning', '')
        }
        
    except Exception as e:
        print(f"⚠️ 市場趨勢分析失敗: {e}", flush=True)
        return {'market_summary': '', 'risk_warning': ''}


# ==================== 產業趨勢 ====================

def get_industry_mapping():
    """取得股票產業分類"""
    try:
        url = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
        response = requests.get(url, timeout=10, verify=False)
        data = response.json()
        
        mapping = {}
        for item in data:
            code = item.get('公司代號', '')
            industry = item.get('產業別', '')
            if code and industry:
                mapping[code] = industry
        
        print(f"✅ 取得產業分類: {len(mapping)} 筆", flush=True)
        return mapping
    except Exception as e:
        print(f"⚠️ 產業分類抓取失敗: {e}", flush=True)
        return {}


def analyze_industry_trend(stocks, industry_mapping):
    """分析產業趨勢"""
    industry_stats = {}
    
    for stock in stocks:
        ticker = stock['ticker']
        change_pct = stock['change_pct']
        industry = industry_mapping.get(ticker, '其他')
        
        if industry not in industry_stats:
            industry_stats[industry] = {'total_change': 0, 'count': 0}
        
        industry_stats[industry]['total_change'] += change_pct
        industry_stats[industry]['count'] += 1
    
    # 計算平均漲跌幅
    industry_avg = {}
    for industry, stats in industry_stats.items():
        if stats['count'] >= 3:  # 至少 3 支股票才統計
            industry_avg[industry] = round(stats['total_change'] / stats['count'], 2)
    
    # 排序
    sorted_industries = sorted(industry_avg.items(), key=lambda x: x[1], reverse=True)
    
    return {
        'strong': sorted_industries[:3],  # 前 3 強
        'weak': sorted_industries[-3:] if len(sorted_industries) >= 3 else []  # 後 3 弱
    }


# ==================== 歷史資料&技術指標 ====================

def get_stock_history(ticker, days=30):
    """取得單支股票歷史資料 (最近 N 天)"""
    try:
        all_data = []
        
        # v4.5: 改抓 4 個月資料 (約 80 交易日，確保夠算 MA60)
        for i in range(4):
            target_date = datetime.now() - timedelta(days=30*i)
            date_str = target_date.strftime('%Y%m01')
            
            url = f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
            params = {
                'date': date_str,
                'stockNo': ticker,
                'response': 'json'
            }
            
            response = requests.get(url, params=params, timeout=10, verify=False)
            data = response.json()
            
            if data.get('stat') == 'OK' and data.get('data'):
                for row in data['data']:
                    try:
                        # 日期, 成交股數, 成交金額, 開盤, 最高, 最低, 收盤, 漲跌, 成交筆數
                        close = float(row[6].replace(',', ''))
                        high = float(row[4].replace(',', ''))
                        low = float(row[5].replace(',', ''))
                        volume = int(row[1].replace(',', ''))
                        
                        all_data.append({
                            'date': row[0],
                            'close': close,
                            'high': high,
                            'low': low,
                            'volume': volume
                        })
                    except:
                        continue
            
            time.sleep(0.15)  # 縮短 API 間隔 (0.3->0.15)
        
        # 按日期排序 (舊到新)
        all_data.sort(key=lambda x: x['date'])
        
        # 回傳最近 N 天
        return all_data[-days:] if len(all_data) >= days else all_data
        
    except Exception as e:
        return []


def check_ma60_with_twse(ticker, history):
    """
    v4.5: 用證交所歷史資料計算 MA60/MA120
    不再依賴 yfinance，使用已抓取的歷史資料
    
    Args:
        ticker: 股票代碼
        history: 已抓取的歷史資料 (from get_stock_history)
    
    Returns:
        成功且站上 MA60: {'ma60': 150.0, 'bonus': 2或3}
        失敗或跌破 MA60: None
        資料不足: 回傳預設值
    """
    try:
        # 檢查 history 是否有效
        if not history or len(history) == 0:
            print(f"⚠️ {ticker} 無歷史資料，跳過 MA60", flush=True)
            return {
                'ma60': None,
                'ma120': None,
                'bonus': 0,
                'skipped': True
            }
        
        # 取得收盤價列表
        closes = [h['close'] for h in history if h.get('close') is not None]
        
        # 檢查資料是否足夠 (至少需要 60 天)
        if len(closes) < 60:
            print(f"⚠️ {ticker} 歷史資料不足 ({len(closes)} 天)，跳過 MA60", flush=True)
            return {
                'ma60': None,
                'ma120': None,
                'bonus': 0,
                'skipped': True
            }
        
        current_price = closes[-1]
        
        # 計算 MA60 (季線)
        ma60 = sum(closes[-60:]) / 60
        
        # 計算 MA120 (半年線) - 可能資料不足
        ma120 = None
        if len(closes) >= 120:
            ma120 = sum(closes[-120:]) / 120
        
        # 檢查是否站上 MA60 (一票否決)
        if ma60 is None or current_price is None:
            print(f"⚠️ {ticker} MA60 或價格為 None，跳過", flush=True)
            return {
                'ma60': None,
                'ma120': None,
                'bonus': 0,
                'skipped': True
            }
        
        if current_price < ma60:
            print(f"❌ {ticker} 跌破季線 (現價 {current_price:.2f} < MA60 {ma60:.2f})，排除", flush=True)
            return None
        
        # 計算加分
        bonus = 2  # 站上 MA60 基本 +2 分
        above_ma120 = False
        
        if ma120 and current_price > ma120:
            bonus += 1  # 站上 MA120 額外 +1 分
            above_ma120 = True
        
        ma120_str = f"{ma120:.2f}" if ma120 else "N/A"
        print(f"✅ {ticker} 站穩季線 (MA60={ma60:.2f}, MA120={ma120_str}) +{bonus}分", flush=True)
        
        return {
            'ma60': round(ma60, 2),
            'ma120': round(ma120, 2) if ma120 else None,
            'current_price': round(current_price, 2),
            'above_ma60': True,
            'above_ma120': above_ma120,
            'bonus': bonus,
            'skipped': False
        }
        
    except Exception as e:
        print(f"⚠️ {ticker} MA60 計算失敗: {e}", flush=True)
        return {
            'ma60': None,
            'ma120': None,
            'bonus': 0,
            'skipped': True
        }


def calculate_ma(closes, period):
    """計算移動平均線"""
    if len(closes) < period:
        return None
    return round(sum(closes[-period:]) / period, 2)


def calculate_rsi(closes, period=14):
    """計算 RSI"""
    if len(closes) < period + 1:
        return None
    
    gains = []
    losses = []
    
    for i in range(1, len(closes)):
        change = closes[i] - closes[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    # 取最近 period 天
    recent_gains = gains[-period:]
    recent_losses = losses[-period:]
    
    avg_gain = sum(recent_gains) / period
    avg_loss = sum(recent_losses) / period
    
    if avg_loss == 0:
        return 100
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return round(rsi, 1)


def calculate_kd(highs, lows, closes, period=9):
    """計算 KD 指標"""
    if len(closes) < period:
        return None, None
    
    # 最近 period 天的最高最低
    highest = max(highs[-period:])
    lowest = min(lows[-period:])
    
    if highest == lowest:
        return 50, 50
    
    # RSV
    rsv = (closes[-1] - lowest) / (highest - lowest) * 100
    
    # K = 前日K * 2/3 + 今日RSV * 1/3 (簡化版用 RSV)
    k = round(rsv, 1)
    d = round(rsv * 0.67, 1)  # 簡化版
    
    return k, d


def calculate_volume_ratio(volumes):
    """計算量比 (今日成交量 / 5日均量)"""
    if len(volumes) < 5:
        return 1.0
    
    avg_5d = sum(volumes[-6:-1]) / 5  # 不含今日
    if avg_5d == 0:
        return 1.0
    
    return round(volumes[-1] / avg_5d, 2)


def round_to_tick(price):
    """依股價對齊到正確的跳動單位 (台股規則)"""
    if price < 10:
        return round(price, 2)  # 0.01
    elif price < 50:
        return round(price * 20) / 20  # 0.05
    elif price < 100:
        return round(price * 10) / 10  # 0.1
    elif price < 500:
        return round(price * 2) / 2  # 0.5
    elif price < 1000:
        return round(price)  # 1
    else:
        return round(price / 5) * 5  # 5

# 當沖排除的產業 (TWSE 產業代碼: 17 = 金融保險業)
EXCLUDE_DAY_TRADE_INDUSTRIES = ['17', '金融保險業', '金融業', '銀行業', '保險業', '金控業']


# ==================== v4.3 新增函數 ====================

def get_chip_threshold(volume_lots):
    """根據成交量動態調整籌碼門檻（張數）"""
    if volume_lots < 500:
        return {'foreign': 50, 'trust': 30}
    elif volume_lots < 2000:
        return {'foreign': 150, 'trust': 80}
    elif volume_lots < 5000:
        return {'foreign': 300, 'trust': 150}
    else:
        return {'foreign': 500, 'trust': 200}


def pe_score(pe):
    """PE 評分"""
    if pe is None or pe <= 0:
        return -1, "⚠️虧損公司"
    if pe > 50:
        return -1, f"⚠️PE={pe:.0f}過高"
    elif pe > 30:
        return 0, f"PE={pe:.0f}偏高"
    elif pe > 15:
        return 1, f"PE={pe:.0f}合理"
    else:
        return 1, f"PE={pe:.0f}便宜"


def calculate_n_day_gain(closes, n):
    """計算 N 日漲幅百分比"""
    if len(closes) < n + 1:
        return 0
    return round((closes[-1] - closes[-(n+1)]) / closes[-(n+1)] * 100, 1)



def calculate_cdp(high, low, close):
    """計算 CDP (當沖價位) - 已對齊 tick size"""
    pt = high - low
    cdp = (high + low + 2 * close) / 4
    
    return {
        'ah': round_to_tick(cdp + pt),        # 最高價
        'nh': round_to_tick(cdp + 0.5 * pt),  # 近高 (賣點)
        'cdp': round_to_tick(cdp),            # 中軸
        'nl': round_to_tick(cdp - 0.5 * pt),  # 近低 (買點)
        'al': round_to_tick(cdp - pt)         # 最低價
    }


# ==================== 當沖&波段分析 ====================

def analyze_day_trade(stock, history=None, industry=None):
    """
    當沖分析
    條件: 強勢 + 爆量 + 人氣旺
    排除: 金融股
    """
    result = {
        'suitable': False,
        'score': 0,
        'reasons': [],
        'cdp': None,
        'excluded': False,
        'exclude_reason': ''
    }
    
    # 排除金融股
    if industry and industry in EXCLUDE_DAY_TRADE_INDUSTRIES:
        result['excluded'] = True
        result['exclude_reason'] = f'金融股({industry})不適合當沖'
        return result
    
    # 條件1: 強勢 (漲幅 > 3%)
    if stock['change_pct'] >= 3:
        result['score'] += 2
        result['reasons'].append(f"強勢漲{stock['change_pct']:.1f}%")
    
    # 條件2: 成交金額 > 5億
    if stock['turnover'] >= 500_000_000:
        result['score'] += 1
        result['reasons'].append(f"成交{stock['turnover']/1e8:.1f}億")
    
    # 條件3: 量比 (需要歷史資料)
    if history and len(history) >= 5:
        volumes = [d['volume'] for d in history]
        volumes.append(stock['volume'])
        vol_ratio = calculate_volume_ratio(volumes)
        
        if vol_ratio >= 2:
            result['score'] += 2
            result['reasons'].append(f"爆量{vol_ratio:.1f}x")
    
    # 計算 CDP
    result['cdp'] = calculate_cdp(stock['high'], stock['low'], stock['price'])
    
    # 判斷是否適合當沖
    if result['score'] >= 3:
        result['suitable'] = True
    
    return result


def analyze_swing_trade(stock, history=None):
    """
    波段分析 (右側交易) - v4.3 優化版
    
    改進重點:
    1. 距離 MA20 越近越加分，太遠則扣分（避免追高）
    2. 停損採用「MA20 與 -7% 兩者較窄者」
    3. 前日漲幅 > 5% 加入追漲警示
    """
    result = {
        'suitable': False,
        'score': 0,
        'reasons': [],
        'warnings': [],           # 新增: 警示訊息
        'ma5': None,
        'ma20': None,
        'rsi': None,
        'k': None,
        'd': None,
        'ma20_distance': None,    # 新增: 距離 MA20 百分比
        'stop_loss': None,
        'take_profit': None,
        'risk_reward': None
    }
    
    if not history or len(history) < 20:
        # 無歷史資料,用簡化版
        if stock['change_pct'] > 0:
            result['score'] += 1
            result['reasons'].append("今日上漲")
        return result
    
    # 取得收盤價序列
    closes = [d['close'] for d in history]
    closes.append(stock['price'])  # 加入今日
    
    highs = [d['high'] for d in history]
    lows = [d['low'] for d in history]
    
    # 計算技術指標
    ma5 = calculate_ma(closes, 5)
    ma20 = calculate_ma(closes, 20)
    rsi = calculate_rsi(closes)
    k, d = calculate_kd(highs, lows, closes)
    
    result['ma5'] = ma5
    result['ma20'] = ma20
    result['rsi'] = rsi
    result['k'] = k
    result['d'] = d
    
    # ===== 新增: 追漲警示 =====
    # 如果今日漲幅 > 5%，加入警示（可能是追高）
    if stock['change_pct'] >= 5:
        result['warnings'].append(f"⚠️今日漲{stock['change_pct']:.1f}%，留意追高風險")
        result['score'] -= 1  # 扣分
    
    # ===== 核心改進: MA20 距離評分 =====
    if ma20 and stock['price'] > ma20:
        distance_pct = (stock['price'] - ma20) / ma20 * 100
        result['ma20_distance'] = round(distance_pct, 1)
        
        if distance_pct <= 5:
            # 距離 MA20 在 5% 以內 = 理想買點 ⭐
            result['score'] += 3
            result['reasons'].append(f"✅靠近MA20(+{distance_pct:.1f}%)")
        elif distance_pct <= 10:
            # 距離 MA20 在 5-10% = 中等買點
            result['score'] += 1
            result['reasons'].append(f"站上MA20(+{distance_pct:.1f}%)")
        else:
            # 距離 MA20 超過 10% = 追高風險，扣分！
            result['score'] -= 1
            result['warnings'].append(f"⚠️已遠離MA20(+{distance_pct:.1f}%)")
    elif ma20:
        # 跌破 MA20
        result['score'] -= 1
        result['reasons'].append(f"跌破MA20")
    
    # ===== 改進: 停損邏輯 =====
    # 使用「MA20 與 -7% 兩者較窄者」
    price = stock['price']
    stop_loss_pct = round(price * 0.93, 2)  # -7%
    stop_loss_ma20 = ma20 if ma20 else stop_loss_pct
    
    # 取較窄的停損（較高的價格 = 較窄的停損）
    result['stop_loss'] = round(max(stop_loss_pct, stop_loss_ma20), 2)
    
    # 條件: 站上 MA5 (短線)
    if ma5 and stock['price'] > ma5:
        result['score'] += 1
        result['reasons'].append(f"站上MA5")
    
    # 條件: RSI 在合理區間
    if rsi:
        if rsi >= 80:
            result['score'] -= 1
            result['warnings'].append(f"⚠️RSI={rsi}過熱")
        elif rsi >= 70:
            result['warnings'].append(f"RSI={rsi}偏高")
        elif 30 < rsi < 70:
            result['score'] += 1
            result['reasons'].append(f"RSI={rsi}")
        elif rsi <= 30:
            result['score'] += 1
            result['reasons'].append(f"RSI={rsi}超賣")
    
    # 條件: KD (v4.3 修正：>80 視為高檔鈍化，扣分)
    if k and d:
        if k > d and k < 80:
            result['score'] += 1
            result['reasons'].append(f"KD多方")
        elif k >= 80:
            result['score'] -= 1
            result['warnings'].append(f"⚠️KD={k:.0f}高檔鈍化")
    
    # 條件: 法人買超 (v4.3 改進：使用動態門檻)
    inst = stock.get('institutional', {})
    volume_lots = stock.get('volume_lots', 0)
    threshold = get_chip_threshold(volume_lots)
    
    if inst:
        foreign = inst.get('foreign', 0)
        trust = inst.get('trust', 0)
        
        foreign_meaningful = abs(foreign) >= threshold['foreign']
        trust_meaningful = abs(trust) >= threshold['trust']
        
        if foreign_meaningful and trust_meaningful and foreign > 0 and trust > 0:
            result['score'] += 2
            result['reasons'].append(f"外資投信雙買(+{foreign//1000}K/+{trust//1000}K)")
        elif foreign_meaningful and foreign > 0:
            result['score'] += 1
            result['reasons'].append(f"外資買{foreign//1000}K")
        elif trust_meaningful and trust > 0:
            result['score'] += 1
            result['reasons'].append(f"投信買{trust//1000}K")
        elif foreign_meaningful and foreign < 0:
            result['score'] -= 1
            result['warnings'].append(f"⚠️外資賣{abs(foreign)//1000}K")
    
    # ===== v4.3 新增: 5日/10日漲幅過濾 =====
    gain_5d = calculate_n_day_gain(closes, 5)
    gain_10d = calculate_n_day_gain(closes, 10)
    result['gain_5d'] = gain_5d
    result['gain_10d'] = gain_10d
    
    if gain_5d > CONFIG['MAX_5D_GAIN'] or gain_10d > CONFIG['MAX_10D_GAIN']:
        result['score'] -= 2  # 大扣分
        result['warnings'].append(f"⚠️已漲一段(5日{gain_5d:+.1f}%/10日{gain_10d:+.1f}%)")
    elif gain_5d > 6:
        result['score'] -= 1  # 小扣分
        result['warnings'].append(f"⚠️近期已漲(5日{gain_5d:+.1f}%)")
    
    # ===== v4.3 新增: PE 評分 =====
    pe_data = stock.get('pe_ratio', {})
    pe_value = pe_data.get('pe') if isinstance(pe_data, dict) else None
    if pe_value is not None:
        pe_pts, pe_reason = pe_score(pe_value)
        result['score'] += pe_pts
        if pe_pts > 0:
            result['reasons'].append(pe_reason)
        elif pe_pts < 0:
            result['warnings'].append(pe_reason)
        result['pe'] = pe_value
    
    # ===== v4.3 新增: 新聞情緒評分 =====
    # 新聞情緒從 deep_analyze 傳入
    sentiment = stock.get('news_sentiment', 0)
    news_summary = stock.get('news_summary', '')
    if sentiment > 0.3:
        result['score'] += 1
        if news_summary:
            result['reasons'].append(f"📰{news_summary}")
    elif sentiment < -0.3:
        result['score'] -= 1
        if news_summary:
            result['warnings'].append(f"⚠️{news_summary}")
    
    # 判斷是否適合波段（v4.4: 門檻提高到 5 分）
    if result['score'] >= CONFIG.get('SWING_TRADE_SCORE_THRESHOLD', 5):
        result['suitable'] = True
    
    # 計算停利目標和風報比 (1:2 風報比)
    if result['stop_loss'] and result['stop_loss'] > 0:
        stop_loss = result['stop_loss']
        risk = price - stop_loss  # 風險 (可能虧損)
        
        if risk > 0:
            # 停利目標 = 現價 + 2倍風險 (1:2 風報比)
            take_profit = round_to_tick(price + risk * 2)
            result['take_profit'] = take_profit
            
            # 風報比 = 潛在報酬 / 風險
            reward = take_profit - price
            result['risk_reward'] = round(reward / risk, 1)
    
    return result




def quick_filter(stocks, institutional):
    """
    第一階段: 快速篩選 (不呼叫任何 API)
    使用已取得的資料進行過濾
    """
    print(f"\n🔍 第一階段: 快速篩選 {len(stocks)} 支股票...", flush=True)
    
    candidates = []
    stats = {
        'low_price': 0,
        'high_price': 0,      # v4.3 新增
        'low_turnover': 0,
        'low_volume': 0,      # v4.3 新增
        'passed': 0
    }
    
    for stock in stocks:
        ticker = stock['ticker']
        price = stock['price']
        turnover = stock['turnover']
        volume_lots = stock.get('volume_lots', 0)
        change_pct = stock['change_pct']
        
        # 過濾: 價格太低
        if price < CONFIG['MIN_PRICE']:
            stats['low_price'] += 1
            continue
        
        # v4.3 新增: 過濾價格太高（避免雞蛋股）
        if price > CONFIG.get('MAX_PRICE', 200):
            stats['high_price'] += 1
            continue
        
        # 過濾: 成交金額太低
        if turnover < CONFIG['MIN_TURNOVER']:
            stats['low_turnover'] += 1
            continue
        
        # v4.3 新增: 過濾成交量太低（流動性不足）
        if volume_lots < CONFIG.get('MIN_VOLUME', 300):
            stats['low_volume'] += 1
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
            'volume': stock['volume'],           # 成交股數
            'volume_lots': stock['volume_lots'], # 成交張數
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


def deep_analyze(candidates, industry_mapping=None):
    """
    第二階段: 深度分析 Top N
    包含: 歷史資料、技術指標、當沖/波段分析、Gemini 新聞分析
    """
    top_n = CONFIG['TOP_N_FOR_DEEP_ANALYSIS']
    to_analyze = candidates[:top_n]
    
    print(f"\n🔬 第二階段: 深度分析 Top {len(to_analyze)} 支股票...", flush=True)
    print(f"   (含技術指標 + Gemini 2.5 Pro 新聞分析)", flush=True)
    
    day_trade_list = []   # 當沖標的
    swing_trade_list = [] # 波段標的
    
    if industry_mapping is None:
        industry_mapping = {}
    
    for i, candidate in enumerate(to_analyze, 1):
        ticker = candidate['ticker']
        name = candidate['name']
        industry = industry_mapping.get(ticker, '')
        
        try:
            # 1. 抓取歷史資料 (60天 - 支援 MA60 計算)
            history = get_stock_history(ticker, 60)
            
            # ===== v4.5: MA60 季線檢查 (改用證交所資料) =====
            ma60_result = check_ma60_with_twse(ticker, history)
            
            # 跌破季線時 ma60_result 是 None，直接排除
            if ma60_result is None:
                continue
            
            # 資料不足時 skipped=True，繼續分析但不加分
            ma60_bonus = ma60_result.get('bonus', 0)
            candidate['ma60_info'] = ma60_result
            ma60_status = ma60_result.get('above_ma60', None)
            # ==========================================
            
            # 2. 當沖分析 (傳入產業以排除金融股)
            day_trade = analyze_day_trade(candidate, history, industry)
            
            # 3. 抓取新聞 + Gemini 綜合分析 (v4.5: 升級為操盤建議)
            news_list = get_stock_news(ticker, name)
            
            # 準備籌碼資訊字串
            inst = candidate['institutional']
            foreign = inst.get('foreign', 0)
            trust = inst.get('trust', 0)
            inst_str = f"外資{'買超' if foreign > 0 else '賣超'}{abs(foreign)}張, 投信{'買超' if trust > 0 else '賣超'}{abs(trust)}張"
            
            # v4.5: 使用新版 Gemini 綜合分析
            gemini_result = analyze_stock_with_gemini(
                ticker=ticker,
                name=name,
                price=candidate['price'],
                change_pct=candidate['change_pct'],
                ma60_status=ma60_status if ma60_status is not None else True,
                institutional_data=inst_str,
                news_titles=news_list
            )
            gemini_score = gemini_result.get('gemini_score', 0)
            gemini_comment = gemini_result.get('gemini_comment', '')
            
            # 向下相容: 轉換為舊版 sentiment 格式
            sentiment = gemini_score
            news_summary = gemini_comment
            
            # 4. 取得 PE 資料
            pe_data = get_pe_ratio_data()
            stock_pe = pe_data.get(ticker, {})
            
            # 5. 波段分析 (v4.3: 傳入 PE 和新聞資料)
            candidate_with_extra = candidate.copy()
            candidate_with_extra['pe_ratio'] = stock_pe
            candidate_with_extra['news_sentiment'] = sentiment
            candidate_with_extra['news_summary'] = news_summary
            swing_trade = analyze_swing_trade(candidate_with_extra, history)
            
            # v4.5: 將 MA60 加分加到 swing_trade 的評分中
            swing_trade['score'] += ma60_bonus
            # 重新判斷是否適合波段（因為加了 MA60 分數）
            if swing_trade['score'] >= CONFIG.get('SWING_TRADE_SCORE_THRESHOLD', 5):
                swing_trade['suitable'] = True
            
            # 基礎評分 (快速篩選的分數)
            base_score = candidate['score']
            # 波段評分 = swing_trade 的評分 (已包含 MA60 加分)
            final_score = swing_trade['score']
            
            # 組合結果
            result = {
                'rank': i,
                'ticker': ticker,
                'name': name,
                'price': candidate['price'],
                'change_pct': candidate['change_pct'],
                'turnover': candidate['turnover'],
                'high': candidate['high'],
                'low': candidate['low'],
                'score': final_score,
                'base_score': base_score,
                'reasons': candidate['reasons'],
                'institutional': candidate['institutional'],
                'news_summary': news_summary,
                'news_sentiment': sentiment,
                # v4.5: AI_G 短評
                'gemini_comment': gemini_comment,
                # 當沖資訊
                'day_trade': day_trade,
                # 波段資訊
                'swing_trade': swing_trade,
                # v4.5: MA60 資訊
                'ma60_info': ma60_result
            }
            
            # 分類
            if day_trade['suitable']:
                day_trade_list.append(result)
            
            if swing_trade['suitable']:
                swing_trade_list.append(result)
            
            if i % 10 == 0:
                print(f"   進度: {i}/{len(to_analyze)}", flush=True)
                
        except Exception as e:
            print(f"⚠️ {ticker} 分析失敗: {e}", flush=True)
    
    # 按評分排序
    day_trade_list.sort(key=lambda x: x['day_trade']['score'], reverse=True)
    swing_trade_list.sort(key=lambda x: x['swing_trade']['score'], reverse=True)
    
    print(f"✅ 深度分析完成:", flush=True)
    print(f"   🔥 當沖標的: {len(day_trade_list)} 支", flush=True)
    print(f"   📈 波段標的: {len(swing_trade_list)} 支", flush=True)
    
    return {
        'day_trade': day_trade_list[:CONFIG.get('DAY_TRADE_MAX', 3)],      # 當沖 Top 3
        'swing_trade': swing_trade_list[:CONFIG.get('SWING_TRADE_MAX', 5)]  # 波段 Top 5
    }


# ==================== 查詢次數控制 ====================

def check_query_limit(user_id):
    """檢查用戶是否超過每日查詢限制"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    if user_id not in USER_QUERY_COUNT:
        USER_QUERY_COUNT[user_id] = {'date': today, 'count': 0}
    
    user_data = USER_QUERY_COUNT[user_id]
    
    # 日期不同，重置計數
    if user_data['date'] != today:
        USER_QUERY_COUNT[user_id] = {'date': today, 'count': 0}
        return True, 0
    
    return user_data['count'] < DAILY_QUERY_LIMIT, user_data['count']


def increment_query_count(user_id):
    """增加用戶查詢次數"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    if user_id not in USER_QUERY_COUNT:
        USER_QUERY_COUNT[user_id] = {'date': today, 'count': 0}
    
    if USER_QUERY_COUNT[user_id]['date'] != today:
        USER_QUERY_COUNT[user_id] = {'date': today, 'count': 0}
    
    USER_QUERY_COUNT[user_id]['count'] += 1
    return USER_QUERY_COUNT[user_id]['count']


# ==================== 單股分析 ====================

def analyze_single_stock(ticker):
    """分析單一股票，回傳完整報告"""
    print(f"\n🔍 開始分析 {ticker}...", flush=True)
    
    try:
        # 1. 取得今日所有股票資料
        all_stocks = get_all_stocks_data()
        stock_data = None
        for s in all_stocks:
            if s['ticker'] == ticker:
                stock_data = s
                break
        
        if not stock_data:
            return {'error': f'找不到股票 {ticker}'}
        
        # 2. 取得法人資料
        institutional = get_institutional_data()
        stock_data['institutional'] = institutional.get(ticker, {})
        
        # 3. 取得本益比資料
        pe_data = get_pe_ratio_data()
        stock_pe = pe_data.get(ticker, {})
        
        # 4. 取得融資融券資料
        margin_data = get_margin_trading_data()
        stock_margin = margin_data.get(ticker, {})
        
        # 5. 取得歷史資料
        history = get_stock_history(ticker, 30)
        
        # 6. 技術指標分析
        swing_trade = analyze_swing_trade(stock_data, history)
        
        # 7. 取得產業分類
        industry_mapping = get_industry_mapping()
        industry = industry_mapping.get(ticker, '')
        
        # 8. 當沖分析
        day_trade = analyze_day_trade(stock_data, history, industry)
        
        # 9. 新聞分析
        news_list = get_stock_news(ticker, stock_data['name'])
        news_result = analyze_news_sentiment(ticker, stock_data['name'], news_list)
        
        # 組合結果
        result = {
            'ticker': ticker,
            'name': stock_data['name'],
            'price': stock_data['price'],
            'change_pct': stock_data['change_pct'],
            'volume': stock_data['volume'],
            'turnover': stock_data['turnover'],
            'institutional': stock_data.get('institutional', {}),
            'pe_ratio': stock_pe,
            'margin_trading': stock_margin,
            'swing_trade': swing_trade,
            'day_trade': day_trade,
            'news_summary': news_result.get('summary', ''),
            'news_sentiment': news_result.get('sentiment', 0),
        }
        
        print(f"✅ {ticker} {stock_data['name']} 分析完成", flush=True)
        return result
        
    except Exception as e:
        print(f"❌ {ticker} 分析失敗: {e}", flush=True)
        return {'error': str(e)}


def format_single_stock_message(result):
    """格式化單股分析訊息 - 精簡版含 AI 建議"""
    if 'error' in result:
        return f"❌ 分析失敗: {result['error']}"
    
    ticker = result['ticker']
    name = result['name']
    price = result['price']
    change_pct = result['change_pct']
    volume = result['volume']
    
    sw = result.get('swing_trade', {})
    dt = result.get('day_trade', {})
    inst = result.get('institutional', {})
    pe_info = result.get('pe_ratio', {})
    margin_info = result.get('margin_trading', {})
    
    # ===== 趨勢判斷 =====
    trend_signals = []
    trend_warnings = []
    
    ma5 = sw.get('ma5')
    ma20 = sw.get('ma20')
    rsi = sw.get('rsi')
    
    if ma20 and price > ma20:
        trend_signals.append("站穩MA20 ✅")
    elif ma20:
        trend_warnings.append("跌破MA20 ⚠️")
    
    if ma5 and price > ma5:
        trend_signals.append("站上MA5 ✅")
    
    if rsi:
        if rsi >= 80:
            trend_warnings.append(f"RSI {rsi} 過熱 ⚠️")
        elif rsi >= 70:
            trend_warnings.append(f"RSI {rsi} 偏高")
        elif rsi <= 30:
            trend_signals.append(f"RSI {rsi} 超賣 💡")
        else:
            trend_signals.append(f"RSI {rsi} 正常")
    
    # 趨勢總結
    if len(trend_signals) >= 2 and len(trend_warnings) == 0:
        trend_summary = "多方健康"
    elif len(trend_signals) >= 2:
        trend_summary = "多方偏熱"
    elif len(trend_warnings) >= 2:
        trend_summary = "偏空或過熱"
    else:
        trend_summary = "中性整理"
    
    # ===== 籌碼判斷 =====
    foreign = inst.get('foreign', 0)
    trust = inst.get('trust', 0)
    
    chip_signals = []
    if foreign > 0:
        chip_signals.append(f"外資買{foreign//1000:+}K ✅")
    elif foreign < 0:
        chip_signals.append(f"外資賣{foreign//1000:+}K ⚠️")
    
    if trust > 0:
        chip_signals.append(f"投信買{trust//1000:+}K ✅")
    elif trust < 0:
        chip_signals.append(f"投信賣{trust//1000:+}K ⚠️")
    
    if foreign > 0 and trust > 0:
        chip_summary = "法人買進中"
    elif foreign < 0 and trust < 0:
        chip_summary = "法人賣出中"
    else:
        chip_summary = "法人分歧"
    
    # ===== 估值判斷 =====
    pe = pe_info.get('pe')
    pe_judgment = ""
    if pe:
        if pe > 30:
            pe_judgment = f"PE {pe:.0f} ⚠️ 偏高"
        elif pe > 20:
            pe_judgment = f"PE {pe:.0f} 中等"
        elif pe > 0:
            pe_judgment = f"PE {pe:.0f} ✅ 合理"
    
    # ===== 關鍵價位 =====
    stop_loss = sw.get('stop_loss')
    take_profit = sw.get('take_profit')
    
    # ===== AI 總結 =====
    # 綜合判斷
    bullish_count = len([s for s in trend_signals if '✅' in s]) + (1 if foreign > 0 else 0) + (1 if trust > 0 else 0)
    warning_count = len(trend_warnings) + (1 if foreign < 0 else 0) + (1 if pe and pe > 25 else 0)
    
    if bullish_count >= 4 and warning_count <= 1:
        ai_summary = "趨勢健康，法人買進"
        hold_advice = "✅ 續抱"
        buy_advice = "✅ 可進場"
    elif bullish_count >= 3 and warning_count >= 2:
        ai_summary = "多方但有風險訊號"
        hold_advice = "✅ 續抱，留意回檔"
        buy_advice = "⚠️ 小量試單"
    elif bullish_count >= 2:
        ai_summary = "趨勢中性，觀望為主"
        hold_advice = "⚠️ 設好停損"
        buy_advice = "⚠️ 等拉回再接"
    else:
        ai_summary = "訊號偏空，謹慎操作"
        hold_advice = "⚠️ 考慮減碼"
        buy_advice = "❌ 不建議"
    
    # ===== 組合訊息 =====
    msg = [
        f"📊 {ticker} {name}",
        "══════════════════",
        "",
        f"💰 ${price} ({change_pct:+.1f}%) | {volume//1000}K張",
        "",
        f"📈 趨勢: {trend_summary}",
    ]
    
    # 趨勢細節 (選前2個)
    trend_details = (trend_signals + trend_warnings)[:2]
    if trend_details:
        msg.append(f"   {' | '.join(trend_details)}")
    
    msg.append("")
    msg.append(f"🏦 籌碼: {chip_summary}")
    if chip_signals:
        msg.append(f"   {' | '.join(chip_signals[:2])}")
    
    # 融資融券
    if margin_info:
        ratio = margin_info.get('ratio', 0)
        if ratio > 10:
            msg.append(f"   💳 券資比 {ratio}% ⚠️ 軋空機會")
        elif ratio > 0:
            msg.append(f"   💳 券資比 {ratio}%")
    
    msg.append("")
    if pe_judgment:
        msg.append(f"📊 估值: {pe_judgment}")
    
    # 關鍵價位
    if stop_loss or take_profit:
        msg.append("")
        msg.append("🎯 關鍵價:")
        if take_profit:
            msg.append(f"   壓力 ${take_profit}")
        if stop_loss:
            msg.append(f"   支撐 ${stop_loss}")
    
    # AI 分隔線
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    msg.append(f"🤖 AI: {ai_summary}")
    msg.append("")
    msg.append("💡 建議:")
    if stop_loss:
        stop_pct = abs((stop_loss - price) / price * 100)
        msg.append(f"   持有: {hold_advice}，${stop_loss}停損")
    else:
        msg.append(f"   持有: {hold_advice}")
    msg.append(f"   想買: {buy_advice}")
    
    # 新聞
    news = result.get('news_summary', '')
    if news and news not in ['無相關新聞', '分析失敗', '']:
        msg.append("")
        msg.append(f"📰 {news}")
    
    return "\n".join(msg)


# ==================== 主流程 ====================

def scan_all_stocks():
    """掃描全台股 - 完整版 (含當沖/波段策略)"""
    print("\n" + "="*60, flush=True)
    print("🚀 台股情報獵人 v4.0 - 開始掃描", flush=True)
    print("   (含當沖/波段雙策略 + Gemini 2.5 Pro)", flush=True)
    print("="*60, flush=True)
    
    start_time = time.time()
    
    # Step 1: 取得大盤狀態 (含指數)
    market = get_market_status()
    if market.get('index', 0) > 0:
        print(f"\n📊 大盤指數: {market['index']:,} 點", flush=True)
    print(f"🌍 市場狀態: {market['status']}", flush=True)
    print(f"   {market.get('reason', '')}", flush=True)
    
    # Step 2: 取得國際新聞
    print("\n📰 抓取國際新聞...", flush=True)
    macro_news = get_macro_news()
    for news in macro_news[:3]:
        print(f"   • {news[:40]}...", flush=True)
    
    # Step 3: 一次取得所有股票資料
    stocks = get_all_stocks_data()
    if not stocks:
        return {'error': '無法取得股票資料'}
    
    # Step 4: 取得法人資料
    institutional = get_institutional_data()
    
    # Step 5: 取得產業分類並分析趨勢
    industry_mapping = get_industry_mapping()
    industry_trend = analyze_industry_trend(stocks, industry_mapping)
    
    print("\n🏭 產業趨勢:", flush=True)
    print(f"   🔥 強勢: {', '.join([f'{i[0]}({i[1]:+.1f}%)' for i in industry_trend['strong'][:3]])}", flush=True)
    print(f"   ❄️ 弱勢: {', '.join([f'{i[0]}({i[1]:+.1f}%)' for i in industry_trend['weak'][:3]])}", flush=True)
    
    # Step 6: 快速篩選
    candidates = quick_filter(stocks, institutional)
    
    # Step 7: 深度分析 (含 Gemini 2.5 Pro 新聞 AI)
    recommendations = deep_analyze(candidates, industry_mapping)
    
    end_time = time.time()
    
    # 結果
    result = {
        'timestamp': datetime.now().isoformat(),
        'market': market,
        'macro_news': macro_news,
        'industry_trend': industry_trend,
        'total_stocks': len(stocks),
        'passed_filter': len(candidates),
        'recommendations': recommendations,
        'execution_time': round(end_time - start_time, 2)
    }
    
    print("\n" + "="*60, flush=True)
    print(f"✅ 掃描完成! 耗時: {result['execution_time']} 秒", flush=True)
    print(f"   總股票數: {result['total_stocks']}", flush=True)
    print(f"   通過篩選: {result['passed_filter']}", flush=True)
    print(f"   🔥 當沖標的: {len(recommendations.get('day_trade', []))} 支", flush=True)
    print(f"   📈 波段標的: {len(recommendations.get('swing_trade', []))} 支", flush=True)
    print("="*60 + "\n", flush=True)
    
    return result


# ==================== LINE 訊息格式 ====================

def format_line_messages(result):
    """格式化 LINE 推送訊息 (分段發送) - v4.4: 8:00 只推波段"""
    if 'error' in result:
        return [f"❌ 錯誤: {result['error']}"]
    
    market = result['market']
    recommendations = result.get('recommendations', {})
    day_trade_list = recommendations.get('day_trade', [])
    swing_trade_list = recommendations.get('swing_trade', [])
    
    messages = []
    
    # 第一段: 大盤 + 國際新聞 + 產業趨勢
    msg1 = [
        f"📊 台股情報獵人 v4.4",
        f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        ""
    ]
    
    # 大盤指數
    if market.get('index', 0) > 0:
        msg1.append(f"📈 大盤: {market['index']:,} 點")
    msg1.append(f"🌍 市場: {market['status']} ({market.get('reason', '')})")
    msg1.append("")
    
    # 國際新聞
    macro_news = result.get('macro_news', [])
    if macro_news:
        msg1.append("📰 國際焦點:")
        for news in macro_news[:3]:
            msg1.append(f"• {news[:35]}...")
        msg1.append("")
    
    # 產業趨勢
    industry = result.get('industry_trend', {})
    if industry.get('strong'):
        strong = ', '.join([f"{i[0]}({i[1]:+.1f}%)" for i in industry['strong'][:3]])
        weak = ', '.join([f"{i[0]}({i[1]:+.1f}%)" for i in industry.get('weak', [])[:3]])
        msg1.append("🏭 產業趨勢:")
        msg1.append(f"🔥 強: {strong}")
        msg1.append(f"❄️ 弱: {weak}")
        msg1.append("")
    
    # v4.4: 8:00 推播不顯示當沖，改為提示可用指令
    msg1.append(f"📈 波段標的: {len(swing_trade_list)} 支")
    if day_trade_list:
        msg1.append(f"💡 輸入「當沖」可查看當沖觀察名單")
    msg1.append(f"⚡ 耗時: {result['execution_time']} 秒")
    
    messages.append("\n".join(msg1))
    
    # v4.4: 移除當沖自動推播（改為指令觸發）
    # 原本的當沖推播區塊已移除

    
    # 第三段起: 波段標的
    if swing_trade_list:
        for batch_start in range(0, len(swing_trade_list), 5):
            batch = swing_trade_list[batch_start:batch_start+5]
            
            msg = [f"📈 波段推薦 ({batch_start+1}-{batch_start+len(batch)}):", ""]
            
            for i, rec in enumerate(batch, batch_start + 1):
                sw = rec.get('swing_trade', {})
                
                msg.append(f"{rec['ticker']} {rec['name']}")
                msg.append(f"💰 ${rec['price']} ({rec['change_pct']:+.1f}%)")
                # v4.5: 加入季線標示
                ma60_flag = " (季線✅)" if rec.get('ma60_info') else ""
                msg.append(f"📊 評分: {rec['score']} 分{ma60_flag}")
                
                # 技術指標 + MA20 距離
                if sw.get('ma20'):
                    ma20_dist = sw.get('ma20_distance', '')
                    dist_str = f" (+{ma20_dist}%)" if ma20_dist else ""
                    msg.append(f"   📐 MA20: ${sw['ma20']}{dist_str} | RSI: {sw.get('rsi', '-')}")
                
                # 警示訊息
                warnings = sw.get('warnings', [])
                if warnings:
                    msg.append(f"   {' | '.join(warnings[:2])}")
                
                # 停損 + 停利 + 風報比
                if sw.get('stop_loss'):
                    stop_loss_pct = (sw['stop_loss'] - rec['price']) / rec['price'] * 100
                    msg.append(f"   🛑 停損: ${sw['stop_loss']} ({stop_loss_pct:.1f}%)")
                
                if sw.get('take_profit') and sw.get('risk_reward'):
                    take_profit_pct = (sw['take_profit'] - rec['price']) / rec['price'] * 100
                    msg.append(f"   🎯 停利: ${sw['take_profit']} (+{take_profit_pct:.1f}%) | 風報比 1:{sw['risk_reward']}")
                
                # 籌碼
                inst = rec.get('institutional', {})
                if inst:
                    foreign = inst.get('foreign', 0)
                    trust = inst.get('trust', 0)
                    if foreign != 0 or trust != 0:
                        msg.append(f"   🏦 外資:{foreign//1000:+}張 投信:{trust//1000:+}張")
                
                # v4.5: AI_G 短評
                gemini_comment = rec.get('gemini_comment', '')
                if gemini_comment and gemini_comment not in ['暫無 AI 分析', '暫無評論', '', '(Gemini 已停用)']:
                    msg.append(f"🧠 AI_G: {gemini_comment}")
                
                msg.append("")
            
            messages.append("\n".join(msg))
    
    return messages


def send_line_push(message):
    """推送訊息到 LINE (廣播給所有追蹤者)"""
    try:
        if isinstance(message, list):
            # 分段發送 - 廣播給所有追蹤者
            for msg in message:
                line_bot_api.broadcast(TextSendMessage(text=msg))
                time.sleep(0.5)  # 避免太快
            print(f"✅ LINE 廣播成功 ({len(message)} 段)", flush=True)
        else:
            line_bot_api.broadcast(TextSendMessage(text=message))
            print("✅ LINE 廣播成功", flush=True)
    except Exception as e:
        print(f"❌ LINE 廣播失敗: {e}", flush=True)


# ==================== 定時任務 ====================

def daily_analysis_task():
    """每日分析任務"""
    print("\n⏰ 執行每日分析任務...", flush=True)
    
    try:
        result = scan_all_stocks()
        messages = format_line_messages(result)
        send_line_push(messages)
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
    user_id = event.source.user_id
    
    # 查詢自己的 User ID
    if text in ['我的ID', 'myid', 'ID']:
        reply = f"📱 您的 User ID:\n{user_id}"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return
    
    # 分析指令 (管理員限定)
    if text in ['分析', '掃描', '今日推薦']:
        # 檢查管理員權限
        if ADMIN_USER_ID and user_id != ADMIN_USER_ID:
            reply = "⚠️ 此功能僅限管理員使用\n📢 請等待每日 8:00 自動推播"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return
        
        reply = "🔄 開始分析,請稍候...(約 1-2 分鐘)"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        
        try:
            # 執行分析
            result = scan_all_stocks()
            messages = format_line_messages(result)
            # 分段發送
            for msg in messages:
                line_bot_api.push_message(user_id, TextSendMessage(text=msg))
                time.sleep(0.5)
        except Exception as e:
            error_msg = f"❌ 分析失敗: {str(e)[:100]}"
            line_bot_api.push_message(user_id, TextSendMessage(text=error_msg))
        return
    
    # v4.4: 當沖觀察指令 (管理員限定)
    if text in ['當沖', '當沖觀察']:
        # 檢查管理員權限
        if ADMIN_USER_ID and user_id != ADMIN_USER_ID:
            reply = "⚠️ 此功能僅限管理員使用"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return
        
        reply = "🔄 分析當沖標的中,請稍候..."
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        
        try:
            result = scan_all_stocks()
            day_trade_list = result.get('recommendations', {}).get('day_trade', [])
            
            if not day_trade_list:
                msg = "📭 今日無符合條件的當沖標的"
            else:
                msg_lines = ["🔥 當沖觀察名單:", ""]
                
                for i, rec in enumerate(day_trade_list[:CONFIG.get('DAY_TRADE_MAX', 3)], 1):
                    dt = rec.get('day_trade', {})
                    cdp = dt.get('cdp', {})
                    
                    msg_lines.append(f"{i}. {rec['ticker']} {rec['name']}")
                    msg_lines.append(f"   💰 ${rec['price']} ({rec['change_pct']:+.1f}%)")
                    msg_lines.append(f"   💡 {', '.join(dt.get('reasons', [])[:2])}")
                    
                    if cdp:
                        msg_lines.append(f"   📍 CDP 買: ${cdp.get('nl', '')} / 賣: ${cdp.get('nh', '')}")
                    msg_lines.append("")
                
                msg_lines.append("⚠️ 當沖風險高,請謹慎操作")
                msg = "\n".join(msg_lines)
            
            line_bot_api.push_message(user_id, TextSendMessage(text=msg))
        except Exception as e:
            error_msg = f"❌ 分析失敗: {str(e)[:100]}"
            line_bot_api.push_message(user_id, TextSendMessage(text=error_msg))
        return
    
    # 單股分析 (輸入 4 碼數字)
    if text.isdigit() and len(text) == 4:
        ticker = text
        
        # 管理員無限制，其他人檢查次數
        if ADMIN_USER_ID and user_id != ADMIN_USER_ID:
            can_query, current_count = check_query_limit(user_id)
            if not can_query:
                reply = f"⚠️ 今日查詢已達上限 ({DAILY_QUERY_LIMIT}/{DAILY_QUERY_LIMIT})\n📢 請等待明日重置\n💡 或等待每日 8:00 推播"
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
                return
        
        reply = f"🔍 分析 {ticker} 中,請稍候..."
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        
        try:
            # 執行單股分析
            result = analyze_single_stock(ticker)
            msg = format_single_stock_message(result)
            
            # 增加查詢次數 (管理員不計算)
            if not (ADMIN_USER_ID and user_id == ADMIN_USER_ID):
                new_count = increment_query_count(user_id)
                remaining = DAILY_QUERY_LIMIT - new_count
                msg += f"\n\n📊 今日剩餘查詢次數: {remaining}/{DAILY_QUERY_LIMIT}"
            
            line_bot_api.push_message(user_id, TextSendMessage(text=msg))
        except Exception as e:
            error_msg = f"❌ 分析失敗: {str(e)[:100]}"
            line_bot_api.push_message(user_id, TextSendMessage(text=error_msg))
        return
        
    # 大盤狀態 (所有人可用)
    if text == '狀態':
        market = get_market_status()
        reply = f"🌍 大盤狀態: {market['status']}\n{market['reason']}"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return
    
    # 顯示指令說明
    if ADMIN_USER_ID and user_id == ADMIN_USER_ID:
        reply = "📋 管理員指令:\n• 分析 - 執行完整分析\n• 股票代碼 - 單股分析 (如 2330)\n• 狀態 - 查看大盤\n• 我的ID - 查看 User ID"
    else:
        reply = f"📋 指令:\n• 股票代碼 - 單股分析 (如 2330)\n• 狀態 - 查看大盤\n• 我的ID - 查看 User ID\n\n📊 每日可查詢 {DAILY_QUERY_LIMIT} 次\n📢 每日 8:00 自動推播分析結果"
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))


@app.route("/")
def index():
    return "台股情報獵人 v4.0 運行中"


@app.route("/manual")
def manual_run():
    """手動觸發分析"""
    result = scan_all_stocks()
    messages = format_line_messages(result)
    return '<hr>'.join([m.replace('\n', '<br>') for m in messages])


# ==================== 主程式 ====================

if __name__ == "__main__":
    try:
        port = int(os.environ.get('PORT', 8080))
        print("\n" + "="*60, flush=True)
        print("🚀 台股情報獵人 v4.0 啟動", flush=True)
        print("="*60, flush=True)
        print(f"📡 監聯端口: {port}", flush=True)
        print(f"⏰ 定時任務: 每日 08:00", flush=True)
        print(f"🔗 手動觸發: http://localhost:{port}/manual", flush=True)
        print("="*60 + "\n", flush=True)
        
        app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        print(f"❌ 啟動失敗: {e}", flush=True)
        raise
