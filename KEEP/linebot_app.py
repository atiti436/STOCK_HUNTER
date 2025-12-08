#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Manpan 情報網 v4.1 - LINE BOT 版本

功能：
1. 每日推送分析結果
2. 互動問答（WHY/HOW）
3. 週報統計
4. 參數調整
"""

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    TemplateSendMessage, ButtonsTemplate, MessageAction
)
import os
from datetime import datetime
import json
import random

# ==================== LINE BOT 設定 ====================
# 請到 LINE Developers 申請後填入
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', 'YOUR_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET', 'YOUR_CHANNEL_SECRET')

app = Flask(__name__)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ==================== 📊 六大守護者邏輯（從 Colab 移植） ====================

CONFIG = {
    # 守護者 1：市場熔斷
    "MARKET_MA60_PERIOD": 60,
    "MARKET_LIMIT_DOWN_THRESHOLD": 100,

    # 守護者 2：流動性
    "MIN_TURNOVER": 50_000_000,
    "VOLUME_SPIKE_RATIO": 5,

    # 守護者 3：籌碼面
    "FOREIGN_BUY_RATIO": 0.05,
    "TRUST_BUY_RATIO": 0.03,
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
}

# Mock Data 生成器（實際使用時要串接真實 API）
def generate_market_data(scenario="bull"):
    """生成大盤資料"""
    if scenario == "bull":
        return {
            "index_name": "台灣加權指數",
            "current_price": 17500,
            "ma60": 17200,
            "limit_down_count": 35,
            "date": datetime.now().strftime("%Y-%m-%d")
        }
    else:
        return {
            "index_name": "台灣加權指數",
            "current_price": 16800,
            "ma60": 17200,
            "limit_down_count": 120,
            "date": datetime.now().strftime("%Y-%m-%d")
        }

def generate_mock_stocks():
    """生成模擬股票（簡化版，只保留 2 支）"""
    return [
        # 完美買點：台積電
        {
            "ticker": "2330",
            "name": "台積電",
            "price": 580,
            "ma20": 565,
            "ma60": 550,
            "ma120": 520,
            "avg_volume_5d": 25000,
            "avg_turnover_5d": 145_000_000,
            "today_volume": 28000,
            "chips": {
                "foreign": {"buy_days": 5, "today_amount": 150_000_000, "today_ratio": 0.08},
                "trust": {"buy_days": 4, "today_amount": 50_000_000, "today_ratio": 0.03},
                "dealer": {"buy_days": 1, "today_amount": 10_000_000, "today_ratio": 0.01}
            },
            "total_turnover_today": 1_800_000_000
        },
        # 籌碼背離：長榮
        {
            "ticker": "2603",
            "name": "長榮",
            "price": 150,
            "ma20": 148,
            "ma60": 145,
            "ma120": 140,
            "avg_volume_5d": 30000,
            "avg_turnover_5d": 200_000_000,
            "today_volume": 32000,
            "chips": {
                "foreign": {"buy_days": 0, "today_amount": -50_000_000, "today_ratio": -0.05},
                "trust": {"buy_days": 0, "today_amount": -20_000_000, "today_ratio": -0.02},
                "dealer": {"buy_days": 2, "today_amount": 5_000_000, "today_ratio": 0.01}
            },
            "total_turnover_today": 1_000_000_000
        }
    ]

# 守護者函數
def guardian_1_market_check(market_data, config):
    """守護者 1：市場熔斷"""
    current = market_data['current_price']
    ma60 = market_data['ma60']
    limit_down = market_data['limit_down_count']

    below_ma60 = current < ma60
    panic = limit_down > config['MARKET_LIMIT_DOWN_THRESHOLD']

    if below_ma60 or panic:
        return {
            "status": "DANGER",
            "reason": f"大盤 {current} < 季線 {ma60}" if below_ma60 else f"跌停 {limit_down} 支"
        }

    return {"status": "SAFE", "reason": "市場正常"}

def guardian_2_liquidity(stock, config):
    """守護者 2：流動性"""
    turnover = stock['avg_turnover_5d']
    volume_ratio = stock['today_volume'] / stock['avg_volume_5d']

    if turnover < config['MIN_TURNOVER']:
        return {"pass": False, "reason": f"流動性不足（{turnover/1e6:.1f}M）"}

    if volume_ratio > config['VOLUME_SPIKE_RATIO']:
        return {"pass": True, "warning": f"爆量警示（量比 {volume_ratio:.1f}x）"}

    return {"pass": True, "reason": "流動性充足"}

def guardian_3_chips(stock, config):
    """守護者 3：籌碼共識"""
    foreign = stock['chips']['foreign']
    trust = stock['chips']['trust']

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

    # 雙賣超
    if foreign['today_ratio'] < -0.03 and trust['today_ratio'] < -0.02:
        score -= 3
        reasons.append("外資投信雙賣超")

    level = "STRONG" if score >= 3 else "MODERATE" if score > 0 else "AVOID"

    return {"score": score, "level": level, "reasons": reasons}

def guardian_4_technical(stock, config):
    """守護者 4：技術面"""
    bias = (stock['price'] - stock['ma60']) / stock['ma60']
    is_bullish = (stock['ma20'] > stock['ma60'] > stock['ma120'])
    threshold = config['BIAS_THRESHOLD_BULL'] if is_bullish else config['BIAS_THRESHOLD_BEAR']

    if bias > threshold:
        return {"pass": False, "reason": f"技術過熱（乖離 {bias:.1%}）"}

    return {"pass": True, "bias": bias, "trend": "多頭" if is_bullish else "空頭"}

def guardian_6_position(chips_score, config):
    """守護者 6：倉位配置"""
    if chips_score >= 3:
        return {"allocation": config['HIGH_CONFIDENCE_ALLOCATION'], "confidence": "HIGH"}
    elif chips_score > 0:
        return {"allocation": config['MEDIUM_CONFIDENCE_ALLOCATION'], "confidence": "MEDIUM"}
    else:
        return {"allocation": 0, "confidence": "NONE"}

# ==================== 📊 分析引擎 ====================

def analyze_stock(stock, config):
    """分析單一股票"""
    # 守護者 2
    liquidity = guardian_2_liquidity(stock, config)
    if not liquidity['pass']:
        return {"ticker": stock['ticker'], "name": stock['name'], "result": "FAIL", "reason": liquidity['reason']}

    # 守護者 4
    technical = guardian_4_technical(stock, config)
    if not technical['pass']:
        return {"ticker": stock['ticker'], "name": stock['name'], "result": "FAIL", "reason": technical['reason']}

    # 守護者 3
    chips = guardian_3_chips(stock, config)

    # 守護者 6
    position = guardian_6_position(chips['score'], config)

    return {
        "ticker": stock['ticker'],
        "name": stock['name'],
        "price": stock['price'],
        "result": "PASS",
        "liquidity": liquidity,
        "technical": technical,
        "chips": chips,
        "position": position,
        "raw_data": stock  # 保留原始資料供 WHY/HOW 查詢
    }

def run_daily_analysis():
    """執行每日分析（給 LINE BOT 推送用）"""
    market = generate_market_data("bull")
    market_check = guardian_1_market_check(market, CONFIG)

    # 生成報告文字
    report = f"📊 Manpan 情報網 - 每日分析\n"
    report += f"{'='*30}\n\n"

    # 市場狀態
    status_icon = "🟢" if market_check['status'] == 'SAFE' else "🔴"
    report += f"🌍 市場狀態：{status_icon} {market_check['status']}\n"
    report += f"大盤：{market['current_price']:,} 點\n"
    report += f"季線：{market['ma60']:,} 點\n"
    report += f"原因：{market_check['reason']}\n\n"

    if market_check['status'] == 'SAFE':
        stocks = generate_mock_stocks()
        report += f"🔍 候選股票分析\n{'─'*30}\n\n"

        for stock in stocks:
            result = analyze_stock(stock, CONFIG)

            if result['result'] == 'PASS' and result['position']['allocation'] > 0:
                report += f"✅ {result['ticker']} {result['name']}\n"
                report += f"價格：${result['price']}\n"
                report += f"籌碼評分：{result['chips']['score']} ({result['chips']['level']})\n"
                report += f"建議倉位：{result['position']['allocation']:.0%}\n"

                # WHY 說明
                if result['chips']['reasons']:
                    report += f"原因：\n"
                    for reason in result['chips']['reasons']:
                        report += f"  • {reason}\n"
                report += f"\n"
            elif result['result'] == 'FAIL':
                report += f"🚫 {result['ticker']} {result['name']}\n"
                report += f"淘汰：{result['reason']}\n\n"
    else:
        report += "⚠️ 市場熔斷，停止買入\n"

    report += f"{'='*30}\n"
    report += f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    return report

# ==================== 💬 WHY/HOW 問答系統 ====================

# 知識庫：每個守護者的詳細說明
KNOWLEDGE_BASE = {
    "守護者1": {
        "名稱": "市場熔斷",
        "目的": "判斷大盤是否安全，避免在崩盤時買入",
        "邏輯": [
            "檢查加權指數是否跌破季線（60日均線）",
            "檢查跌停股票數量是否 > 100 支",
            "任一條件成立就停止所有買入操作"
        ],
        "為什麼": "系統性風險最優先，大盤崩盤時個股很難獨善其身",
        "HOW": "每天開盤前檢查加權指數與季線的關係"
    },
    "守護者2": {
        "名稱": "流動性過濾",
        "目的": "過濾成交量太低的股票，避免有價無市",
        "邏輯": [
            "計算近 5 日平均成交金額（而非成交量）",
            "門檻：日均成交 5000 萬台幣",
            "加碼檢查：今日量 > 5 倍平均量 → 爆量警示"
        ],
        "為什麼": "低價股 1000 張 = 1000 萬，高價股 1000 張 = 6 億，用成交金額才公平",
        "HOW": "取近 5 個交易日的平均成交金額，排除假日"
    },
    "守護者3": {
        "名稱": "籌碼共識",
        "目的": "追蹤三大法人動向，判斷主力是買還是賣",
        "邏輯": [
            "外資連續 3 日買超 + 佔比 > 5%：+2 分",
            "投信連續 3 日買超 + 佔比 > 3%：+2 分",
            "外資投信雙賣超：-3 分",
            "評分 >= 3 分：強力買入（15% 倉位）"
        ],
        "為什麼": "法人資金大、研究深入，跟著主力走勝率較高",
        "HOW": "每天收盤後查詢三大法人買賣超資料"
    },
    "守護者4": {
        "名稱": "技術面檢查",
        "目的": "避免追高，判斷股價是否過度偏離均線",
        "邏輯": [
            "計算乖離率 = (股價 - 季線) / 季線",
            "多頭市場：允許乖離 30%",
            "空頭市場：只允許乖離 15%",
            "超過門檻 → 淘汰（技術過熱）"
        ],
        "為什麼": "股價偏離均線太遠容易拉回，風險高",
        "HOW": "每天計算股價與 MA60 的差距百分比"
    },
    "守護者5": {
        "名稱": "出場策略",
        "目的": "動態停損停利，保護獲利、控制虧損",
        "邏輯": [
            "第 1 層：大盤熔斷 → 強制賣出",
            "第 2 層：虧損 -8% → 硬停損",
            "第 3 層：跌破月線且虧損 → 技術停損",
            "第 4 層：從高點回落 10% → 移動停利",
            "第 5 層：獲利 +30% → 獲利了結"
        ],
        "為什麼": "有紀律的出場比進場更重要，避免小賺變大虧",
        "HOW": "持有滿 3 天後才啟動停損，避免震盪洗盤"
    },
    "守護者6": {
        "名稱": "倉位配置",
        "目的": "根據籌碼評分決定買多少",
        "邏輯": [
            "評分 >= 3 分：15% 資金",
            "評分 > 0 分：8% 資金",
            "評分 <= 0 分：不交易"
        ],
        "為什麼": "分散風險，避免單一股票暴雷",
        "HOW": "最多 7 支高評分股票才會滿倉（15% × 7 ≈ 100%）"
    },
    "外資買超": "外國機構投資人（資金最大）買進股票的金額超過賣出金額",
    "投信買超": "本土基金公司買進股票的金額超過賣出金額",
    "乖離率": "股價偏離移動平均線的程度，用來判斷是否過熱或超跌",
    "季線": "60 日移動平均線（MA60），代表近 3 個月的平均成本",
    "移動停利": "當股票獲利 > 10% 後，如果從高點回落 10% 就賣出，鎖住大部分獲利"
}

def answer_why_how(question):
    """回答 WHY/HOW 問題"""
    question = question.lower()

    # 關鍵字匹配
    if "守護者1" in question or "市場熔斷" in question or "大盤" in question:
        kb = KNOWLEDGE_BASE["守護者1"]
        return f"📚 {kb['名稱']}\n\n目的：{kb['目的']}\n\n為什麼：{kb['為什麼']}\n\n如何運作：{kb['HOW']}"

    elif "守護者2" in question or "流動性" in question:
        kb = KNOWLEDGE_BASE["守護者2"]
        return f"📚 {kb['名稱']}\n\n目的：{kb['目的']}\n\n為什麼：{kb['為什麼']}\n\n如何運作：{kb['HOW']}"

    elif "守護者3" in question or "籌碼" in question or "法人" in question:
        kb = KNOWLEDGE_BASE["守護者3"]
        logic_text = "\n".join([f"• {l}" for l in kb['邏輯']])
        return f"📚 {kb['名稱']}\n\n目的：{kb['目的']}\n\n邏輯：\n{logic_text}\n\n為什麼：{kb['為什麼']}"

    elif "守護者4" in question or "技術" in question or "乖離" in question:
        kb = KNOWLEDGE_BASE["守護者4"]
        return f"📚 {kb['名稱']}\n\n目的：{kb['目的']}\n\n為什麼：{kb['為什麼']}\n\n如何運作：{kb['HOW']}"

    elif "守護者5" in question or "停損" in question or "停利" in question:
        kb = KNOWLEDGE_BASE["守護者5"]
        logic_text = "\n".join([f"• {l}" for l in kb['邏輯']])
        return f"📚 {kb['名稱']}\n\n目的：{kb['目的']}\n\n邏輯：\n{logic_text}\n\n為什麼：{kb['為什麼']}"

    elif "守護者6" in question or "倉位" in question:
        kb = KNOWLEDGE_BASE["守護者6"]
        return f"📚 {kb['名稱']}\n\n目的：{kb['目的']}\n\n為什麼：{kb['為什麼']}\n\n如何運作：{kb['HOW']}"

    elif "外資" in question:
        return f"💡 外資買超\n\n{KNOWLEDGE_BASE['外資買超']}\n\n為什麼重要：外資資金龐大，通常有深入研究團隊，連續買超代表看好後市"

    elif "投信" in question:
        return f"💡 投信買超\n\n{KNOWLEDGE_BASE['投信買超']}\n\n為什麼重要：投信操作靈活，買超常代表短中期看好"

    elif "季線" in question or "ma60" in question:
        return f"💡 季線 (MA60)\n\n{KNOWLEDGE_BASE['季線']}\n\n為什麼用季線：比月線穩定，比半年線靈敏，是多空分水嶺"

    elif "移動停利" in question:
        return f"💡 移動停利\n\n{KNOWLEDGE_BASE['移動停利']}\n\n範例：買入成本 100，最高漲到 120（獲利 20%），從 120 回落到 108 時賣出（保住 8% 獲利）"

    else:
        return """💬 可以問我的問題：

【守護者系列】
• 守護者1 是什麼
• 為什麼需要守護者3
• 守護者5 怎麼運作

【名詞解釋】
• 什麼是外資買超
• 什麼是乖離率
• 什麼是移動停利

【股票分析】
• 為什麼推薦台積電
• 今天有什麼股票

試試看輸入上面的問題！"""

# ==================== 🤖 LINE BOT Webhook ====================

@app.route("/callback", methods=['POST'])
def callback():
    """LINE BOT Webhook"""
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """處理用戶訊息"""
    user_message = event.message.text.strip()

    # 指令：今日分析
    if user_message in ["今日分析", "分析", "今天", "推薦"]:
        reply_text = run_daily_analysis()

    # 指令：參數查詢
    elif user_message in ["參數", "設定", "config"]:
        reply_text = f"""⚙️ 目前參數設定

【守護者 3：籌碼】
• 外資買超門檻：{CONFIG['FOREIGN_BUY_RATIO']:.0%}
• 投信買超門檻：{CONFIG['TRUST_BUY_RATIO']:.0%}
• 連續買超天數：{CONFIG['CONSECUTIVE_BUY_DAYS']} 天

【守護者 5：停損停利】
• 停損：-{CONFIG['STOP_LOSS']:.0%}
• 獲利了結：+{CONFIG['TAKE_PROFIT']:.0%}
• 移動停利：高點回落 {CONFIG['TRAILING_STOP']:.0%}

【守護者 6：倉位】
• 高信心：{CONFIG['HIGH_CONFIDENCE_ALLOCATION']:.0%}
• 中信心：{CONFIG['MEDIUM_CONFIDENCE_ALLOCATION']:.0%}"""

    # 指令：幫助
    elif user_message in ["幫助", "help", "?"]:
        reply_text = """📖 Manpan 情報網使用說明

【指令】
• 今日分析 - 查看今天推薦股票
• 參數 - 查看目前參數設定
• 幫助 - 顯示此說明

【問答】
直接輸入問題，例如：
• 守護者1 是什麼
• 為什麼推薦台積電
• 什麼是外資買超
• 移動停利怎麼運作

每天早上 8:00 會自動推送分析！"""

    # WHY/HOW 問答
    else:
        reply_text = answer_why_how(user_message)

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

# ==================== 🚀 主程式 ====================

@app.route("/")
def index():
    return "Manpan 情報網 LINE BOT is running!"

@app.route("/test_analysis")
def test_analysis():
    """測試分析功能（瀏覽器訪問用）"""
    return f"<pre>{run_daily_analysis()}</pre>"

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
