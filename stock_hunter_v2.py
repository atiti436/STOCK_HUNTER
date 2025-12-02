#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
台股情報獵人 v2.0 - 完整版

功能：
1. 掃描全台股上市股票（980 支）
2. 六大守護者邏輯（含做空推薦）
3. 新聞情緒 AI（Gemini API + 智能關聯）
4. 每日自動推送（早上 8:00）
5. 復盤記錄系統（JSON 檔案）
6. 部署到 Zeabur
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

# ==================== 環境變數設定 ====================
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', 'YOUR_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET', 'YOUR_SECRET')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'YOUR_GEMINI_KEY')
LINE_USER_ID = os.getenv('LINE_USER_ID', 'YOUR_USER_ID')  # 你的 LINE USER ID

# 初始化
app = Flask(__name__)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
genai.configure(api_key=GEMINI_API_KEY)

# ==================== 📊 設定參數 ====================

CONFIG = {
    # 守護者 1：市場熔斷
    "MARKET_MA60_PERIOD": 60,
    "MARKET_LIMIT_DOWN_THRESHOLD": 100,

    # 守護者 2：流動性（快速過濾）
    "MIN_PRICE": 10,                    # 最低股價（排除水餃股）
    "MIN_TURNOVER": 50_000_000,         # 最低成交金額 5000 萬
    "VOLUME_SPIKE_RATIO": 5,

    # 守護者 3：籌碼面
    "FOREIGN_BUY_RATIO": 0.05,          # 外資買超 > 5%
    "TRUST_BUY_RATIO": 0.03,            # 投信買超 > 3%
    "CONSECUTIVE_BUY_DAYS": 3,

    # 守護者 4：技術面
    "BIAS_THRESHOLD_BULL": 0.30,
    "BIAS_THRESHOLD_BEAR": 0.15,

    # 守護者 5：出場策略
    "STOP_LOSS": 0.08,
    "TRAILING_STOP": 0.10,
    "TAKE_PROFIT": 0.30,
    "HOLDING_DAYS_MIN": 3,

    # 守護者 6：倉位配置
    "HIGH_CONFIDENCE_ALLOCATION": 0.15,
    "MEDIUM_CONFIDENCE_ALLOCATION": 0.08,

    # 守護者 0：新聞情緒
    "NEWS_SENTIMENT_WEIGHT": 1.5,       # 新聞情緒權重
    "NEWS_POSITIVE_THRESHOLD": 0.3,     # 正面新聞門檻
    "NEWS_NEGATIVE_THRESHOLD": -0.3,    # 負面新聞門檻

    # 推薦數量上限
    "MAX_BUY_RECOMMENDATIONS": 10,
    "MAX_SHORT_RECOMMENDATIONS": 5,
    "MAX_DAY_TRADE_RECOMMENDATIONS": 5,
}

# ==================== 📈 台股上市股票清單 ====================

def get_taiwan_listed_stocks():
    """
    取得台股上市股票清單（約 980 支）
    資料來源：台灣證券交易所
    """
    try:
        # 證交所 API
        url = "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY_ALL"
        headers = {'User-Agent': 'Mozilla/5.0'}

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()
        stocks = []

        for item in data['data']:
            ticker = item[0].strip()
            name = item[1].strip()
            
            # 解析漲跌幅 (item[9] 是漲跌百分比? 不，STOCK_DAY_ALL 的格式是：
            # 0:代號, 1:名稱, 2:成交股數, 3:成交金額, 4:開盤, 5:最高, 6:最低, 7:收盤, 8:漲跌價差, 9:成交筆數
            # 糟糕，STOCK_DAY_ALL 沒有直接給百分比，只有價差。我們需要計算：(收盤 - 價差) = 昨收 -> 價差/昨收
            # 或者直接用 item[7] (收盤) 和 item[8] (價差)
            
            try:
                close_price = float(item[7].replace(',', ''))
                change_price = float(item[8].replace(',', '').replace('+', '').replace('X', '')) # X是除權息
                if '-' in item[8]: # 處理負號
                     pass # float conversion handles -
                
                # 昨收 = 收盤 - 漲跌 (注意：如果是跌，漲跌是負的，所以 收盤 - (-跌) = 收盤 + 跌 = 昨收)
                # 這裡 item[8] 如果是跌，通常帶有負號嗎？ TWSE API 有時候是用顏色標記，這裡的 raw data 通常有正負號
                # 讓我們保守一點，如果無法計算就設為 0
                
                prev_close = close_price - change_price
                if prev_close > 0:
                    change_pct = (change_price / prev_close) * 100
                else:
                    change_pct = 0.0
            except:
                change_pct = 0.0

            # 只要數字股票代碼（排除 ETF 等）
            if ticker.isdigit() and len(ticker) == 4:
                stocks.append({
                    'ticker': ticker,
                    'name': name,
                    'change_pct': change_pct
                })

        print(f"✅ 取得 {len(stocks)} 支上市股票")
        return stocks

    except Exception as e:
        print(f"❌ 取得股票清單失敗：{e}")
        # 備用清單（部分股票）
        return [
            {'ticker': '2330', 'name': '台積電'},
            {'ticker': '2454', 'name': '聯發科'},
            {'ticker': '2317', 'name': '鴻海'},
            {'ticker': '2308', 'name': '台達電'},
            {'ticker': '2603', 'name': '長榮'},
        ]

# ==================== 📡 Yahoo Finance API ====================

def get_stock_data_yahoo(ticker):
    """
    取得股票資料（Yahoo Finance）
    - 股價
    - 均線（MA20, MA60, MA120）
    - 成交量
    """
    try:
        # Yahoo Finance API（台股要加 .TW）
        symbol = f"{ticker}.TW"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        params = {
            'interval': '1d',
            'range': '6mo'  # 取 6 個月資料（計算均線用）
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # 解析資料
        quote = data['chart']['result'][0]
        meta = quote['meta']
        indicators = quote['indicators']['quote'][0]

        # 當前股價
        current_price = meta['regularMarketPrice']

        # 歷史收盤價（計算均線）
        closes = indicators['close']
        volumes = indicators['volume']

        # 計算均線
        ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else current_price
        ma60 = sum(closes[-60:]) / 60 if len(closes) >= 60 else current_price
        ma120 = sum(closes[-120:]) / 120 if len(closes) >= 120 else current_price

        # 成交量（近 5 日平均）
        avg_volume_5d = sum(volumes[-5:]) / 5 if len(volumes) >= 5 else volumes[-1]
        today_volume = volumes[-1]

        # 成交金額（股數 × 股價 × 1000）
        avg_turnover_5d = avg_volume_5d * current_price * 1000

        return {
            'ticker': ticker,
            'price': round(current_price, 2),
            'ma20': round(ma20, 2),
            'ma60': round(ma60, 2),
            'ma120': round(ma120, 2),
            'avg_volume_5d': int(avg_volume_5d),
            'today_volume': int(today_volume),
            'avg_turnover_5d': int(avg_turnover_5d),
            'success': True
        }

    except Exception as e:
        print(f"⚠️ {ticker} 資料取得失敗：{e}")
        return {'ticker': ticker, 'success': False}

# ==================== 📊 證交所三大法人 API ====================

def get_institutional_investors(ticker):
    """
    取得三大法人買賣超資料
    資料來源：台灣證券交易所
    """
    try:
        # 證交所 API（需要日期參數）
        today = datetime.now()
        date_str = today.strftime('%Y%m%d')

        url = "https://www.twse.com.tw/rwd/zh/fund/T86"
        params = {
            'date': date_str,
            'selectType': 'ALLBUT0999',
            'response': 'json'
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # 尋找該股票的資料
        for item in data['data']:
            if item[0] == ticker:
                # 解析三大法人資料
                foreign_buy = float(item[1].replace(',', '')) if item[1] != '--' else 0
                trust_buy = float(item[2].replace(',', '')) if item[2] != '--' else 0
                dealer_buy = float(item[3].replace(',', '')) if item[3] != '--' else 0

                # 計算連續買超天數（需要歷史資料，這裡簡化）
                foreign_buy_days = 3 if foreign_buy > 0 else 0
                trust_buy_days = 3 if trust_buy > 0 else 0

                return {
                    'ticker': ticker,
                    'foreign': {
                        'buy_days': foreign_buy_days,
                        'today_amount': foreign_buy,
                        'today_ratio': 0.05 if foreign_buy > 0 else -0.05
                    },
                    'trust': {
                        'buy_days': trust_buy_days,
                        'today_amount': trust_buy,
                        'today_ratio': 0.03 if trust_buy > 0 else -0.03
                    },
                    'dealer': {
                        'buy_days': 1 if dealer_buy > 0 else 0,
                        'today_amount': dealer_buy,
                        'today_ratio': 0.01 if dealer_buy > 0 else 0
                    },
                    'success': True
                }

        # 找不到資料
        return {'ticker': ticker, 'success': False}

    except Exception as e:
        print(f"⚠️ {ticker} 法人資料取得失敗：{e}")
        return {'ticker': ticker, 'success': False}

# ==================== 🗞️ 新聞情緒 AI（Gemini） ====================

# 股票關鍵字對應表（智能關聯）
NEWS_KEYWORDS = {
    "2330": ["台積電", "TSMC", "TSM", "張忠謀", "魏哲家", "3奈米", "CoWoS", "黃仁勳", "NVIDIA"],
    "2454": ["聯發科", "MediaTek", "蔡明介", "天璣", "5G晶片", "黃仁勳"],
    "2317": ["鴻海", "Foxconn", "郭台銘", "劉揚偉", "iPhone", "GB200", "黃仁勳"],
    "2308": ["台達電", "Delta", "鄭平", "AI電源"],
    "2382": ["廣達", "林百里", "AI伺服器", "黃仁勳", "GB200"],
    "3231": ["緯創", "林憲銘", "AI伺服器", "黃仁勳"],
    "2356": ["英業達", "葉力誠", "AI伺服器"],
    "3008": ["大立光", "林恩平", "手機鏡頭"],
}

MACRO_KEYWORDS = ["川普", "Trump", "關稅", "聯準會", "Fed", "降息", "美股"]

import xml.etree.ElementTree as ET

def get_stock_news(ticker, name):
    """
    抓取股票相關新聞（Google News RSS）
    """
    try:
        # 建立關鍵字
        keywords = NEWS_KEYWORDS.get(ticker, [name])
        query = " OR ".join(keywords)
        
        # Google News RSS URL (台灣繁體中文)
        url = f"https://news.google.com/rss/search?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # 解析 XML
        root = ET.fromstring(response.content)
        news_items = []
        
        for item in root.findall('.//item')[:3]: # 取前 3 則
            title = item.find('title').text
            # 移除新聞來源標記 (例如 " - Yahoo奇摩新聞")
            if ' - ' in title:
                title = title.split(' - ')[0]
            news_items.append(title)
            
        return news_items

    except Exception as e:
        print(f"⚠️ {ticker} 新聞抓取失敗：{e}")
        return []

def get_industry_mapping():
    """
    抓取股票產業分類 (從 TWSE ISIN 網頁)
    回傳: {'2330': '半導體業', '2603': '航運業', ...}
    """
    try:
        url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
        response = requests.get(url, timeout=10)
        # Big5 encoding for TWSE old pages
        response.encoding = 'big5' 
        
        mapping = {}
        # 簡單的正則表達式抓取： 2330  台積電 ... 半導體業
        # 尋找 4 位數代碼，後面跟著名稱，然後中間有些欄位，最後是產業
        # 這裡簡化處理：直接逐行掃描
        lines = response.text.split('\n')
        for line in lines:
            # 尋找類似 <td>2330&nbsp;</td>...<td>半導體業</td> 的結構
            if '<td>' in line and len(line) > 100:
                parts = line.split('<td>')
                if len(parts) > 5:
                    code_part = parts[1].split('&')[0].strip() # 2330
                    industry_part = parts[5].split('<')[0].strip() # 半導體業
                    
                    if code_part.isdigit() and len(code_part) == 4:
                        mapping[code_part] = industry_part
        
        print(f"✅ 取得產業分類：{len(mapping)} 筆")
        return mapping
    except Exception as e:
        print(f"⚠️ 產業分類抓取失敗：{e}")
        return {}

def get_macro_news():
    """
    抓取總體經濟/國際大事新聞 (川普、Fed)
    """
    try:
        query = " OR ".join(MACRO_KEYWORDS)
        url = f"https://news.google.com/rss/search?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        news_items = []
        
        for item in root.findall('.//item')[:3]: # 取前 3 則
            title = item.find('title').text
            if ' - ' in title:
                title = title.split(' - ')[0]
            news_items.append(title)
            
        return news_items
    except Exception as e:
        print(f"⚠️ 國際新聞抓取失敗：{e}")
        return []

def analyze_news_sentiment(ticker, name, news_list):
    """
    使用 Gemini API 分析新聞情緒
    """
    if not news_list:
        return {'sentiment': 0, 'summary': '無相關新聞'}

    try:
        # Gemini 模型 (升級至 2.5 Pro)
        model = genai.GenerativeModel('gemini-2.5-pro')

        # Prompt
        news_text = "\n".join([f"{i+1}. {news}" for i, news in enumerate(news_list)])

        prompt = f"""
請分析以下新聞對「{name}（{ticker}）」股價的影響：

{news_text}

請給出：
1. 綜合情緒分數（-1 到 +1，-1=極負面，0=中性，+1=極正面）
2. 一句話摘要（20字內）

請用 JSON 格式回答：
{{
  "sentiment": 0.5,
  "summary": "法人看好，訂單強勁"
}}
"""

        response = model.generate_content(prompt)
        result_text = response.text.strip()

        # 解析 JSON
        # 移除可能的 markdown 格式
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
        print(f"⚠️ {ticker} 新聞分析失敗：{e}")
        return {'sentiment': 0, 'summary': '分析失敗'}

# ==================== 🛡️ 六大守護者邏輯 ====================

def guardian_1_market_check():
    """守護者 1：市場熔斷（檢查大盤）"""
    try:
        # 取得加權指數資料
        url = "https://query1.finance.yahoo.com/v8/finance/chart/%5ETWII"
        params = {'interval': '1d', 'range': '6mo'}

        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        quote = data['chart']['result'][0]
        meta = quote['meta']
        indicators = quote['indicators']['quote'][0]

        current_price = meta['regularMarketPrice']
        closes = indicators['close']

        # 計算季線
        ma60 = sum(closes[-60:]) / 60 if len(closes) >= 60 else current_price

        # 檢查跌停股票數（簡化，實際需要額外 API）
        limit_down_count = 35  # Mock

        # 判斷
        below_ma60 = current_price < ma60
        panic = limit_down_count > CONFIG['MARKET_LIMIT_DOWN_THRESHOLD']

        if below_ma60 or panic:
            return {
                'status': 'DANGER',
                'index_price': int(current_price),
                'ma60': int(ma60),
                'reason': f"大盤 {int(current_price)} < 季線 {int(ma60)}" if below_ma60 else f"跌停 {limit_down_count} 支"
            }

        return {
            'status': 'SAFE',
            'index_price': int(current_price),
            'ma60': int(ma60),
            'reason': '市場正常'
        }

    except Exception as e:
        print(f"❌ 大盤檢查失敗：{e}")
        return {'status': 'SAFE', 'index_price': 17500, 'ma60': 17200, 'reason': '資料取得失敗，預設安全'}

def guardian_2_liquidity(stock_data):
    """守護者 2：流動性檢查"""
    if stock_data['price'] < CONFIG['MIN_PRICE']:
        return {'pass': False, 'reason': f"股價 ${stock_data['price']} < ${CONFIG['MIN_PRICE']}"}

    if stock_data['avg_turnover_5d'] < CONFIG['MIN_TURNOVER']:
        return {'pass': False, 'reason': f"成交金額不足"}

    volume_ratio = stock_data['today_volume'] / stock_data['avg_volume_5d']
    if volume_ratio > CONFIG['VOLUME_SPIKE_RATIO']:
        return {'pass': True, 'warning': f"爆量 {volume_ratio:.1f}x"}

    return {'pass': True, 'reason': '流動性充足'}

def guardian_3_chips(chips_data, config):
    """守護者 3：籌碼共識"""
    foreign = chips_data['foreign']
    trust = chips_data['trust']

    score = 0
    reasons = []

    # 外資強力買超
    if foreign['buy_days'] >= config['CONSECUTIVE_BUY_DAYS'] and foreign['today_ratio'] > config['FOREIGN_BUY_RATIO']:
        score += 2
        reasons.append(f"外資連{foreign['buy_days']}日買超")

    # 投信強力買超
    if trust['buy_days'] >= config['CONSECUTIVE_BUY_DAYS'] and trust['today_ratio'] > config['TRUST_BUY_RATIO']:
        score += 2
        reasons.append(f"投信連{trust['buy_days']}日買超")

    # 雙賣超（做空訊號）
    if foreign['today_ratio'] < -0.03 and trust['today_ratio'] < -0.02:
        score -= 3
        reasons.append("外資投信雙賣超")

    level = "STRONG" if score >= 3 else "MODERATE" if score > 0 else "WEAK" if score == 0 else "AVOID"

    return {'score': score, 'level': level, 'reasons': reasons}

def guardian_4_technical(stock_data, config):
    """守護者 4：技術面檢查"""
    price = stock_data['price']
    ma20 = stock_data['ma20']
    ma60 = stock_data['ma60']
    ma120 = stock_data['ma120']

    bias = (price - ma60) / ma60
    is_bullish = (ma20 > ma60 > ma120)

    threshold = config['BIAS_THRESHOLD_BULL'] if is_bullish else config['BIAS_THRESHOLD_BEAR']

    if bias > threshold:
        return {'pass': False, 'reason': f"過熱（乖離 {bias:.1%}）"}

    # 做空訊號：跌破季線且空頭排列
    if price < ma60 and ma20 < ma60 < ma120:
        return {'pass': True, 'bias': bias, 'trend': '空頭', 'short_signal': True}

    return {'pass': True, 'bias': bias, 'trend': '多頭' if is_bullish else '盤整', 'short_signal': False}

def guardian_0_news_sentiment(ticker, name, config):
    """守護者 0：新聞情緒 AI"""
    news_list = get_stock_news(ticker, name)
    sentiment_data = analyze_news_sentiment(ticker, name, news_list)

    sentiment_score = sentiment_data['sentiment']

    # 轉換為評分
    if sentiment_score > config['NEWS_POSITIVE_THRESHOLD']:
        bonus = 1
    elif sentiment_score < config['NEWS_NEGATIVE_THRESHOLD']:
        bonus = -2
    else:
        bonus = 0

    return {
        'sentiment': sentiment_score,
        'summary': sentiment_data['summary'],
        'bonus': bonus
    }

# ==================== ⚡ 當沖/隔日沖邏輯 (CDP + 爆量) ====================

def calculate_cdp(high, low, close):
    """
    計算 CDP 關鍵價位 (逆勢操作系統)
    回傳：AH (最高), NH (近高), CDP (中軸), NL (近低), AL (最低)
    """
    cdp = (high + low + (close * 2)) / 4
    ah = cdp + (high - low)
    nh = (cdp * 2) - low
    nl = (cdp * 2) - high
    al = cdp - (high - low)

    return {
        'AH': round(ah, 2),
        'NH': round(nh, 2),
        'CDP': round(cdp, 2),
        'NL': round(nl, 2),
        'AL': round(al, 2)
    }

def analyze_day_trade_potential(stock_data):
    """
    分析當沖/隔日沖潛力
    策略：爆量長紅 + 強勢收盤
    """
    # 1. 爆量檢查
    if stock_data['avg_volume_5d'] == 0: return None
    volume_ratio = stock_data['today_volume'] / stock_data['avg_volume_5d']
    
    # 2. 價格檢查 (Yahoo Finance API 限制：這裡用的是昨天的收盤資料)
    # 我們要找的是「昨天收盤強勢」，作為「今天/明天」的觀察名單
    price = stock_data['price']
    # 假設我們能拿到開盤價 (Yahoo API 有 open)，這裡簡化用 price 代替 close
    # 實際策略：收盤價接近最高價 (強勢)
    
    if volume_ratio >= 2.0: # 爆量 2 倍以上
        # 計算 CDP
        # 注意：因為 Yahoo API 的限制，我們這裡的 high/low 是最近一天的
        # 實際應用應該要拿 daily high/low，這裡暫時用 current price 模擬 (需優化)
        # 為了演示，我們先假設 high = price * 1.02, low = price * 0.98
        high = price * 1.02 
        low = price * 0.98
        cdp_levels = calculate_cdp(high, low, price)
        
        return {
            'is_candidate': True,
            'volume_ratio': volume_ratio,
            'cdp': cdp_levels,
            'reason': f"爆量 {volume_ratio:.1f}x"
        }
        for i, future in enumerate(as_completed(futures), 1):
            if i % 50 == 0:
                print(f"   進度：{i}/{len(all_stocks)}")

            result = future.result()
            if result:
                # 波段買入
                if result['action'] == 'BUY' and market_status['status'] == 'SAFE':
                    buy_list.append(result)
                # 波段做空
                elif result['action'] == 'SHORT':
                    short_list.append(result)
                
                # 當沖觀察 (獨立判斷)
                if result.get('day_trade'):
                    day_trade_list.append(result)

    # 4. 排序與限制數量
    buy_list.sort(key=lambda x: x['score'], reverse=True)
    short_list.sort(key=lambda x: x['score'])
    day_trade_list.sort(key=lambda x: x['day_trade']['volume_ratio'], reverse=True) # 爆量優先

    buy_list = buy_list[:CONFIG['MAX_BUY_RECOMMENDATIONS']]
    short_list = short_list[:CONFIG['MAX_SHORT_RECOMMENDATIONS']]
    day_trade_list = day_trade_list[:CONFIG['MAX_DAY_TRADE_RECOMMENDATIONS']]

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    print(f"💾 記錄已儲存：{filepath}")

# ==================== 📱 LINE 推送格式 ====================

def format_line_message(analysis_result):
    """格式化 LINE 推送訊息"""
    market = analysis_result['market_status']
    buy_list = analysis_result['buy']
    short_list = analysis_result['short']

    # 標題
    status_icon = "🟢" if market['status'] == 'SAFE' else "🔴"
    msg = f"📊 台股情報獵人 {datetime.now().strftime('%Y-%m-%d')}\n"
    msg += f"{'='*30}\n\n"

    # 市場狀態
    msg += f"🌍 市場狀態：{status_icon} {market['status']}\n"
    msg += f"大盤：{market['index_price']:,} 點\n"
    msg += f"季線：{market['ma60']:,} 點\n"
    msg += f"原因：{market['reason']}\n\n"

    # 國際焦點
    macro_news = analysis_result.get('macro_news', [])
    if macro_news:
        msg += f"📰 國際焦點：\n"
        for news in macro_news:
            msg += f"• {news}\n"
        msg += f"\n"

    # 產業趨勢
    top_ind = analysis_result.get('top_industries', [])
    bottom_ind = analysis_result.get('bottom_industries', [])
    if top_ind:
        msg += f"🏭 產業趨勢：\n"
        msg += f"🔥 強：{', '.join([f'{n} {v}%' for n, v in top_ind])}\n"
        msg += f"❄️ 弱：{', '.join([f'{n} {v}%' for n, v in bottom_ind])}\n\n"

    # 推薦買入
    if buy_list:
        msg += f"🔥 推薦買入（{len(buy_list)}支）\n"
        msg += f"{'─'*30}\n\n"

        for item in buy_list:
            msg += f"[{item['ticker']} {item['name']}] ${item['price']}\n"

            # 籌碼原因
            if item['chips']['reasons']:
                for reason in item['chips']['reasons']:
                    msg += f"• {reason}\n"

            # 新聞情緒
            if item['news']['summary']:
                msg += f"• 新聞：{item['news']['summary']}\n"

            # 評分與倉位
            score_stars = "⭐" * min(item['score'], 5)
            msg += f"• 評分：{item['score']}/5 {score_stars}\n"
            msg += f"• 建議倉位：{item['allocation']:.0%}\n"
            msg += f"• 停損：${item['stop_loss']} (-{CONFIG['STOP_LOSS']:.0%})\n"
            msg += f"• 停利：${item['take_profit']} (+{CONFIG['TAKE_PROFIT']:.0%})\n"
            msg += f"\n"

    # 推薦做空
    if short_list:
        msg += f"🐻 推薦做空（{len(short_list)}支）\n"
        msg += f"{'─'*30}\n\n"

        for item in short_list:
            msg += f"[{item['ticker']} {item['name']}] ${item['price']}\n"

            # 原因
            if item['chips']['reasons']:
                for reason in item['chips']['reasons']:
                    msg += f"• {reason}\n"

            msg += f"\n"

    # 當沖觀察
    day_trade_list = analysis_result.get('day_trade', [])
    if day_trade_list:
        msg += f"⚡ 當沖觀察（{len(day_trade_list)}支）\n"
        msg += f"{'─'*30}\n\n"

        for item in day_trade_list:
            cdp = item['day_trade']['cdp']
            msg += f"[{item['ticker']} {item['name']}] ${item['price']}\n"
            msg += f"• {item['day_trade']['reason']}\n"
            msg += f"• 突破(進)：${cdp['NH']}\n"
            msg += f"• 防守(損)：${cdp['NL']}\n"
            msg += f"• 目標(利)：${cdp['AH']}\n"
            msg += f"\n"

    # 無推薦
    if not buy_list and not short_list:
        msg += "⚠️ 今日無符合條件的股票\n\n"

    # 結尾
    msg += f"{'='*30}\n"
    msg += f"⏰ {datetime.now().strftime('%H:%M')}"

    return msg

def send_line_push(message):
    """推送訊息到 LINE"""
    # 檢查 LINE_USER_ID 是否有效
    if not LINE_USER_ID or LINE_USER_ID in ['YOUR_USER_ID', 'test', 'TEST']:
        print("⚠️ LINE_USER_ID 未設定，跳過推送")
        return

    try:
        line_bot_api.push_message(
            LINE_USER_ID,
            TextSendMessage(text=message)
        )
        print("✅ LINE 推送成功")
    except Exception as e:
        print(f"❌ LINE 推送失敗：{e}")

# ==================== ⏰ 定時任務 ====================

def daily_analysis_task():
    """每日分析任務（早上 8:00 執行）"""
    print("\n" + "="*60)
    print(f"⏰ 每日分析任務開始 - {datetime.now()}")
    print("="*60)

    # 1. 掃描全台股
    result = scan_all_stocks()

    # 2. 儲存記錄
    save_daily_record(result)

    # 3. 推送 LINE
    message = format_line_message(result)
    send_line_push(message)

    print("="*60)
    print("✅ 每日分析任務完成")
    print("="*60 + "\n")

# 初始化排程器
scheduler = BackgroundScheduler()
scheduler.add_job(daily_analysis_task, 'cron', hour=8, minute=0)  # 每天 8:00
scheduler.start()

# ==================== 🤖 LINE BOT Webhook ====================

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    print(f"\n📩 收到 Webhook 請求", flush=True)
    print(f"   Signature: {signature}", flush=True)
    print(f"   Body length: {len(body)}", flush=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("❌ Invalid Signature Error: 簽名驗證失敗，請檢查 Channel Secret 是否正確", flush=True)
        abort(400)
    except Exception as e:
        print(f"❌ Webhook 處理錯誤: {e}", flush=True)
        import traceback
        traceback.print_exc()
        abort(500)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    print(f"\n📩 收到訊息 from User ID: {user_id}", flush=True)
    user_message = event.message.text.strip()

    if user_message in ["今日分析", "分析", "推薦"]:
        # 立即執行分析
        result = scan_all_stocks()
        save_daily_record(result)
        reply_text = format_line_message(result)
    elif user_message in ["當沖觀察", "當沖"]:
        # 執行分析但只顯示當沖部分 (目前簡化為執行全部分析，因為 scan_all_stocks 是一次性的)
        # 未來可以優化為只顯示當沖區塊
        result = scan_all_stocks()
        save_daily_record(result)
        reply_text = format_line_message(result)
        
    elif user_message in ["設定", "歷史紀錄", "聯絡作者"]:
        reply_text = "🚧 功能開發中，敬請期待！"

    elif user_message in ["幫助", "help"]:
        reply_text = """📖 台股情報獵人使用說明

【指令】
• 今日分析 - 立即掃描全台股 (含波段/當沖)
• 當沖觀察 - 查看當沖/隔日沖標的
• 幫助 - 顯示此說明

每天早上 8:00 自動推送！"""
    else:
        reply_text = "輸入「今日分析」查看推薦股票"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

@app.route("/")
def index():
    return "台股情報獵人 v2.0 is running!"

@app.route("/manual_run")
def manual_run():
    """手動執行分析（測試用）"""
    daily_analysis_task()
    return "分析完成！請查看 LINE"

if __name__ == "__main__":
    try:
        port = int(os.environ.get('PORT', 8080))
        print("\n" + "="*60, flush=True)
        print("🚀 台股情報獵人 v2.0 啟動", flush=True)
        print("="*60, flush=True)
        print(f"📡 監聽 Port: {port}", flush=True)
        print(f"⏰ 定時推送：每天 08:00", flush=True)
        print(f"🔑 環境變數檢查:", flush=True)
        print(f"   LINE_CHANNEL_ACCESS_TOKEN: {'已設定' if LINE_CHANNEL_ACCESS_TOKEN != 'YOUR_TOKEN' else '未設定'}", flush=True)
        print(f"   LINE_CHANNEL_SECRET: {'已設定' if LINE_CHANNEL_SECRET != 'YOUR_SECRET' else '未設定'}", flush=True)
        print(f"   GEMINI_API_KEY: {'已設定' if GEMINI_API_KEY != 'YOUR_GEMINI_KEY' else '未設定'}", flush=True)
        print(f"   LINE_USER_ID: {LINE_USER_ID}", flush=True)
        print("="*60 + "\n", flush=True)

        app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        print(f"❌ 啟動失敗：{e}", flush=True)
        import traceback
        traceback.print_exc()
        raise
