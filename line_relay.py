#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LINE 訊息轉發站 + 定時掃描
2026-01-01 重構：從 stock_hunter_v3.py (122KB) 精簡至此版本
2026-01-08 更新：整合 APScheduler 定時掃描

功能：
1. 接收 GitHub Actions 推送的訊息，轉發到 LINE
2. 每日 20:30 自動執行掃描並推送（APScheduler）
"""

import os
from flask import Flask, request, abort, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# ==================== 環境變數 ====================
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', '')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET', '')
ADMIN_USER_ID = os.getenv('ADMIN_USER_ID', '')

# 初始化
app = Flask(__name__)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ==================== 啟動排程器 ====================
try:
    from scheduler import start_scheduler
    scheduler = start_scheduler()
    print("🚀 LINE 轉發站啟動 (含定時掃描)", flush=True)
except Exception as e:
    print(f"⚠️ 排程器啟動失敗: {e}", flush=True)
    print("🚀 LINE 轉發站啟動 (純轉發模式)", flush=True)


# ==================== 健康檢查 ====================

@app.route("/", methods=['GET'])
def health_check():
    return jsonify({
        "status": "ok",
        "version": "relay-v1.0",
        "description": "LINE 訊息轉發站 (精簡版)"
    })


# ==================== 接收 GitHub Actions 推送 ====================

@app.route("/push_scan_result", methods=['POST'])
def push_scan_result():
    """
    接收 GitHub Actions 的選股結果，推送到 LINE
    """
    try:
        data = request.get_json()
        message = data.get('message', '')
        
        if not message:
            return jsonify({"error": "No message provided"}), 400
        
        # 廣播給所有追蹤者
        line_bot_api.broadcast(TextSendMessage(text=message))
        print(f"✅ 已廣播訊息 ({len(message)} 字)", flush=True)
        
        return jsonify({"status": "ok", "message_length": len(message)})
    
    except Exception as e:
        print(f"❌ 推送失敗: {e}", flush=True)
        return jsonify({"error": str(e)}), 500


# ==================== LINE Webhook (簡化版) ====================

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
    """
    簡化版訊息處理：只回覆說明
    """
    text = event.message.text.strip()
    
    # 查詢自己的 User ID
    if text in ['我的ID', 'myid', 'ID']:
        user_id = event.source.user_id
        reply = f"📱 您的 User ID:\n{user_id}"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return
    
    # 其他指令：顯示說明
    reply = """📋 選股 BOT v3.4 (精簡版)

⏰ 每日 20:30 自動推送選股結果

💡 即時分析請回家問 Claude

🔗 GitHub Actions 負責運算
🔗 本 BOT 只負責轉發訊息"""
    
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))


# ==================== 啟動 ====================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
