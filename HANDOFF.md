# 台股情報獵人 v4.2 - 交接日誌

## 專案概述
LINE Bot 選股工具，每日自動掃描台股並推薦當沖/波段標的。

**檔案位置:** `d:\claude-project\STOCK_HUNTER\stock_hunter_v3.py`
**GitHub:** https://github.com/atiti436/STOCK_HUNTER
**部署平台:** Zeabur (自動從 GitHub 部署)

---

## 功能清單

### 1. 每日自動掃描 (8:00 推播)
- 掃描全市場 → 快速篩選 → Top 15 深度分析
- 輸出當沖觀察 + 波段推薦

### 2. 單股分析 (輸入 4 碼股票代碼)
- 趨勢判斷 (MA5/MA20/RSI)
- 籌碼分析 (外資/投信買賣超)
- 估值判斷 (本益比)
- 融資融券 (券資比)
- **AI 建議** (持有者/想買者)

### 3. 權限控制
- 管理員 (`ADMIN_USER_ID`): 無限制
- 一般用戶: 單股分析每日 3 次

---

## 已完成的修改 (v4.0 → v4.2)

| 版本 | 功能 |
|------|------|
| v4.0 | CDP tick size 對齊、當沖排除金融股(代碼 17)、Gemini 2.5 Pro、Top 15 分析 |
| v4.1 | 單股分析、本益比、融資融券、查詢次數限制 |
| v4.2 | AI 建議輸出 (趨勢判讀+持有/買進建議) |

---

## 重要函數

| 函數 | 用途 |
|------|------|
| `scan_all_stocks()` | 完整市場掃描 |
| `analyze_single_stock(ticker)` | 單股分析 |
| `format_single_stock_message()` | 格式化 AI 建議輸出 |
| `get_pe_ratio_data()` | 取得本益比 |
| `get_margin_trading_data()` | 取得融資融券 |
| `check_query_limit()` | 檢查查詢次數 |
| `round_to_tick()` | 對齊 tick size |

---

## 環境變數

```
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET
GEMINI_API_KEY
ADMIN_USER_ID  (管理員 LINE User ID)
```

---

## LINE 指令

| 指令 | 權限 | 功能 |
|------|------|------|
| `分析` | 管理員 | 完整市場掃描 |
| `2330` | 所有人 (3次/日) | 單股分析 |
| `狀態` | 所有人 | 大盤狀態 |
| `我的ID` | 所有人 | 查詢 User ID |

---

## 待辦/可改進

1. **連續買賣超** - 目前只有今日，可改為「連 N 日」
2. **產業平均本益比** - 目前只有絕對值判斷
3. **型態辨識** - W底、頭肩頂等
4. **Gemini 深度分析** - 用 AI 做更複雜的研判

---

## 測試方式

1. 對 Bot 發送 `2330` 測試單股分析
2. 對 Bot 發送 `狀態` 測試大盤
3. 對 Bot 發送 `分析` 測試完整掃描 (需管理員)

---

## 注意事項

- 融資融券 API 可能需要微調欄位解析
- 非交易時間 API 回傳可能不同
- Zeabur 重新部署會清除記憶體中的查詢次數記錄
