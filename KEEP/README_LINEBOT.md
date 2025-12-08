# 📱 Manpan 情報網 - LINE BOT 使用說明

## 🎯 功能特色

### 1. ✅ 每日自動推送（早上 8:00）
自動推送當天的股票分析結果，包含：
- 市場狀態（大盤是否安全）
- 推薦股票清單
- 籌碼評分與原因
- 建議倉位配置

### 2. ✅ 互動問答系統（WHY/HOW）
直接問問題，BOT 會回答：
- 「守護者1 是什麼？」
- 「為什麼推薦台積電？」
- 「什麼是外資買超？」
- 「移動停利怎麼運作？」

### 3. ✅ 六大守護者邏輯（內建說明）
每個守護者都有詳細解釋：
- 守護者 1：市場熔斷（大盤安全檢查）
- 守護者 2：流動性過濾（成交金額門檻）
- 守護者 3：籌碼共識（三大法人）
- 守護者 4：技術面檢查（乖離率）
- 守護者 5：出場策略（停損停利）
- 守護者 6：倉位配置（根據評分）

---

## 🚀 快速開始

### 步驟 1：申請 LINE BOT

1. 前往 [LINE Developers](https://developers.line.biz/console/)
2. 登入後點「Create a new provider」
3. 建立 Channel（選擇 Messaging API）
4. 取得兩個重要資訊：
   - **Channel Access Token**（長期）
   - **Channel Secret**

### 步驟 2：設定環境變數

在你的電腦或雲端平台設定：

```bash
# Windows (CMD)
set LINE_CHANNEL_ACCESS_TOKEN=你的_Access_Token
set LINE_CHANNEL_SECRET=你的_Secret

# Mac/Linux
export LINE_CHANNEL_ACCESS_TOKEN=你的_Access_Token
export LINE_CHANNEL_SECRET=你的_Secret
```

### 步驟 3：安裝套件

```bash
pip install -r requirements.txt
```

### 步驟 4：本地測試

```bash
python linebot_app.py
```

啟動後會顯示：
```
* Running on http://0.0.0.0:5000
```

### 步驟 5：使用 ngrok 測試（本地開發）

因為 LINE BOT 需要 HTTPS，本地測試要用 ngrok：

```bash
# 下載 ngrok: https://ngrok.com/download
ngrok http 5000
```

會得到一個網址，例如：
```
https://abc123.ngrok.io
```

### 步驟 6：設定 Webhook

回到 LINE Developers Console：
1. 點選你的 Channel
2. 找到「Messaging API」頁籤
3. 設定 Webhook URL：`https://abc123.ngrok.io/callback`
4. 啟用「Use webhook」
5. 關閉「Auto-reply messages」

---

## 🎮 使用方式

### 指令列表

| 指令 | 說明 |
|------|------|
| `今日分析` | 查看今天推薦的股票 |
| `參數` | 查看目前的參數設定 |
| `幫助` | 顯示使用說明 |

### 問答範例

直接輸入問題：

```
你：守護者1 是什麼
BOT：📚 市場熔斷
     目的：判斷大盤是否安全，避免在崩盤時買入
     為什麼：系統性風險最優先，大盤崩盤時個股很難獨善其身
     如何運作：每天開盤前檢查加權指數與季線的關係
```

```
你：什麼是外資買超
BOT：💡 外資買超
     外國機構投資人（資金最大）買進股票的金額超過賣出金額
     為什麼重要：外資資金龐大，通常有深入研究團隊，連續買超代表看好後市
```

---

## 📊 每日推送範例

```
📊 Manpan 情報網 - 每日分析
==============================

🌍 市場狀態：🟢 SAFE
大盤：17,500 點
季線：17,200 點
原因：市場正常

🔍 候選股票分析
──────────────────────────

✅ 2330 台積電
價格：$580
籌碼評分：4 (STRONG)
建議倉位：15%
原因：
  • 外資連5日買超
  • 投信連4日買超

🚫 2603 長榮
淘汰：外資投信雙賣超

==============================
⏰ 2025-12-02 08:00
```

---

## 🔧 參數調整

修改 `linebot_app.py` 的 `CONFIG` 字典：

```python
CONFIG = {
    "STOP_LOSS": 0.08,              # 停損 -8%（可改成 -5% 更嚴格）
    "TAKE_PROFIT": 0.30,            # 獲利了結 +30%
    "FOREIGN_BUY_RATIO": 0.05,      # 外資買超門檻 5%
    "TRUST_BUY_RATIO": 0.03,        # 投信買超門檻 3%
    # ... 其他參數
}
```

---

## 🌐 部署到雲端（24 小時運作）

### 選項 1：Render（免費，推薦）

1. 註冊 [Render](https://render.com/)
2. 點「New」→「Web Service」
3. 連接你的 GitHub 儲存庫
4. 設定環境變數（LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET）
5. 點「Create Web Service」

### 選項 2：Google Cloud Run

```bash
# 先建立 Dockerfile
gcloud run deploy manpan-bot \
  --source . \
  --platform managed \
  --region asia-east1 \
  --allow-unauthenticated
```

---

## 📚 知識庫（內建問答）

BOT 可以回答的問題：

### 守護者系列
- 守護者1/2/3/4/5/6 是什麼
- 為什麼需要 XXX
- XXX 怎麼運作

### 台股名詞
- 外資買超
- 投信買超
- 乖離率
- 季線
- 移動停利

### 股票分析
- 為什麼推薦台積電
- 今天有什麼股票

---

## 🔮 未來功能（Phase 2-4）

### Phase 2：每日推送（已規劃）
- [ ] 使用 APScheduler 定時推送
- [ ] 早上 8:00 自動發送分析

### Phase 3：週報系統
- [ ] 記錄每天推薦的股票
- [ ] 統計勝率（推薦後 5 日漲跌）
- [ ] 每週日發送週報

### Phase 4：真實資料串接
- [ ] 串接 Yahoo Finance API（取代 Mock Data）
- [ ] 串接台灣證交所 API（三大法人資料）
- [ ] 即時更新股價

---

## 🐛 常見問題

### Q1: BOT 沒有回應？
檢查：
1. Webhook URL 是否正確（要用 HTTPS）
2. ngrok 是否還在運行
3. 環境變數是否設定正確

### Q2: 推送訊息失敗？
檢查：
1. Channel Access Token 是否正確
2. 是否啟用「Use webhook」
3. 是否關閉「Auto-reply messages」

### Q3: 想改成真實資料？
修改 `generate_mock_stocks()` 函數，改成呼叫真實 API

---

## 📞 聯絡資訊

有問題可以：
1. 直接問 LINE BOT（輸入「幫助」）
2. 查看程式碼註解（每個函數都有說明）
3. 問我（Claude）😊

---

**版本：** v4.1
**最後更新：** 2025-12-02
**開發者：** Manpan Team
