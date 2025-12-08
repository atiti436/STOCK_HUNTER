# 📱 台股情報獵人 v2.0 - 使用說明

**最後更新：** 2025-12-02

---

## 🎯 系統功能

### 自動推送（每天早上 8:00）
- 掃描全台股上市股票（980 支）
- 推薦買入清單（最多 10 支）
- 推薦做空清單（最多 5 支）
- 每支股票包含：
  - 股價、停損點、停利點
  - 籌碼評分（外資投信買賣超）
  - 新聞情緒（AI 分析）
  - 建議倉位（8% 或 15%）

### 手動查詢
對 LINE BOT 說：
- `今日分析` → 立即掃描全台股
- `幫助` → 查看使用說明

---

## 🚀 Zeabur 部署步驟

### 前置準備

**1. 申請 LINE BOT**
- 網址：https://developers.line.biz/console/
- 建立 Messaging API Channel
- 取得：
  - Channel Access Token（長期）
  - Channel Secret

**2. 申請 Gemini API Key**
- 網址：https://aistudio.google.com/app/apikey
- 點「Create API Key」
- 複製 API Key

**3. GitHub 已推送**
- ✅ Repository：https://github.com/atiti436/STOCK_HUNTER
- ✅ 包含：stock_hunter_v2.py, requirements_v2.txt, zeabur.json

---

### Zeabur 部署

**步驟 1：登入 Zeabur**
```
1. 前往：https://zeabur.com/
2. 點「Sign in with GitHub」
3. 授權 Zeabur
```

**步驟 2：建立專案**
```
1. 點「Create Project」
2. Region：選 Taiwan 或 Singapore
3. 專案名稱：stock-hunter
4. 點「Create」
```

**步驟 3：部署服務**
```
1. 點「Add Service」
2. 選「Git」
3. 選「atiti436/STOCK_HUNTER」
4. Zeabur 會自動偵測 Python 專案
5. 點「Deploy」
```

**步驟 4：設定環境變數**
```
點「Variables」，新增 4 個變數：
```

| Key | Value | 說明 |
|-----|-------|------|
| `LINE_CHANNEL_ACCESS_TOKEN` | 你的 Token | 從 LINE Developers 取得 |
| `LINE_CHANNEL_SECRET` | 你的 Secret | 從 LINE Developers 取得 |
| `GEMINI_API_KEY` | 你的 Gemini Key | 從 Google AI Studio 取得 |
| `LINE_USER_ID` | 先填 `test` | 之後再改（下面教你） |

**步驟 5：重新部署**
```
1. 設定完環境變數
2. 點「Redeploy」
3. 等待 2-3 分鐘
```

**步驟 6：取得 Zeabur 網址**
```
1. 部署成功後，點「Domains」
2. 複製網址（例如：stock-hunter-abc123.zeabur.app）
```

**步驟 7：設定 LINE Webhook**
```
1. 回到 LINE Developers Console
2. 進入你的 Channel
3. 點「Messaging API」
4. 設定 Webhook URL：
   https://你的zeabur網址.zeabur.app/callback

5. 點「Verify」測試（應該成功）
6. 啟用「Use webhook」
7. 關閉「Auto-reply messages」
8. 關閉「Greeting messages」
```

**步驟 8：取得真實 LINE USER ID**
```
1. 加 LINE BOT 好友
2. 對 BOT 說「測試」
3. 回到 Zeabur → Logs
4. 找到類似這樣的訊息：
   USER ID: U1234567890abcdef...

5. 複製這個 USER ID
6. 回到 Variables
7. 修改 LINE_USER_ID = 你的真實 ID
8. 點「Save」→「Redeploy」
```

**步驟 9：測試**
```
瀏覽器訪問：
https://你的zeabur網址.zeabur.app/manual_run

應該顯示：「分析完成！請查看 LINE」
然後 LINE 會收到推送訊息！
```

---

## 📊 推送訊息範例

```
📊 台股情報獵人 2025-12-02
==============================

🌍 市場狀態：🟢 SAFE
大盤：17,500 點
季線：17,200 點
原因：市場正常

🔥 推薦買入（3支）
──────────────────────────

[2330 台積電] $580
• 外資連5日買超
• 投信連4日買超
• 新聞：黃仁勳讚台積電、3奈米良率提升
• 評分：5/5 ⭐⭐⭐⭐⭐
• 建議倉位：15%
• 停損：$533 (-8%)
• 停利：$754 (+30%)

[2454 聯發科] $1020
• 外資連3日買超
• 新聞：AI晶片訂單強勁
• 評分：4/5 ⭐⭐⭐⭐
• 建議倉位：15%
• 停損：$938 (-8%)
• 停利：$1326 (+30%)

🐻 推薦做空（1支）
──────────────────────────

[2603 長榮] $150
• 外資投信雙賣超
• 評分：-3/5

==============================
⏰ 08:00
```

---

## 🔧 修改參數

編輯 `stock_hunter_v2.py`，找到 `CONFIG` 字典：

```python
CONFIG = {
    # 停損停利
    "STOP_LOSS": 0.08,              # 改成 0.05 = -5% 停損（更嚴格）
    "TAKE_PROFIT": 0.30,            # 改成 0.20 = +20% 獲利了結

    # 籌碼門檻
    "FOREIGN_BUY_RATIO": 0.05,      # 改成 0.10 = 外資買超 > 10%
    "TRUST_BUY_RATIO": 0.03,        # 改成 0.05 = 投信買超 > 5%

    # 推薦數量
    "MAX_BUY_RECOMMENDATIONS": 10,  # 改成 5 = 最多推薦 5 支
    "MAX_SHORT_RECOMMENDATIONS": 5, # 改成 3 = 最多推薦 3 支做空
}
```

修改後：
```bash
git add stock_hunter_v2.py
git commit -m "Update config"
git push
```

Zeabur 會自動重新部署。

---

## 📁 復盤記錄

每天分析後會自動儲存 JSON 檔案：

**位置：** `records/2025-12-02.json`

**格式：**
```json
{
  "date": "2025-12-02",
  "market_status": "SAFE",
  "index_price": 17500,
  "recommendations": {
    "buy": [
      {
        "ticker": "2330",
        "name": "台積電",
        "recommend_price": 580,
        "reason": {
          "chips_score": 4,
          "chips_reasons": ["外資連5日買超", "投信連4日買超"],
          "news_sentiment": 0.7,
          "news_summary": "黃仁勳讚台積電、3奈米良率提升"
        },
        "targets": {
          "stop_loss": 533,
          "take_profit": 754
        },
        "review": {
          "day1_price": 585,
          "day1_return": 0.86,
          "result": "WIN"
        }
      }
    ]
  }
}
```

**查看記錄：**
在 Zeabur → Logs → Files → `records/`

---

## 🤖 與 Claude 復盤

每天收到推送後，可以問 Claude：

```
"為什麼推薦 2330 台積電？"
"外資買超邏輯有效嗎？"
"昨天推薦的股票今天漲了嗎？"
"我應該調整哪些參數？"
```

Claude 會根據復盤記錄幫你分析並提出建議。

---

## 🐛 常見問題

### Q1: LINE BOT 沒反應？
檢查：
1. Webhook URL 是否正確（要加 `/callback`）
2. 是否啟用「Use webhook」
3. 是否關閉「Auto-reply messages」
4. Zeabur 是否正常運行（查看 Logs）

### Q2: 沒收到推送？
檢查：
1. `LINE_USER_ID` 是否正確
2. Zeabur → Logs 有沒有錯誤訊息
3. 手動測試 `/manual_run` 是否成功

### Q3: Gemini API 配額用完？
免費版限制：1500 次/天
- 減少新聞分析數量
- 升級到付費版
- 暫時關閉新聞功能

### Q4: 掃描太慢？
- 正常需要 2-3 分鐘掃描 980 支股票
- 可以減少掃描數量（修改 `all_stocks[:300]`）

---

## 📞 聯絡資訊

有問題可以：
1. 查看 Zeabur Logs
2. 查看 `For_Claude.md`（交接報告）
3. 問 Claude

---

## ✅ 檢查清單

部署完成後：
- [ ] LINE BOT 已建立
- [ ] Gemini API Key 已取得
- [ ] GitHub 已推送
- [ ] Zeabur 專案已建立
- [ ] 環境變數已設定（4 個）
- [ ] LINE Webhook 已設定
- [ ] LINE USER ID 已更新
- [ ] 手動測試成功（/manual_run）
- [ ] 對話測試成功（今日分析）
- [ ] 等待明天早上 8:00 自動推送

---

**版本：** v2.0
**最後更新：** 2025-12-02
