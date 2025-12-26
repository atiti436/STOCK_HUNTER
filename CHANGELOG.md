# 📋 STOCK_HUNTER 更新日誌

> 記錄專案的開發歷程、決策和變更

---

## 2025-12-26

### ✅ 新增

- `scripts/update_data.py` - 資料抓取腳本
  - 從 GitHub (voidful/tw-institutional-stocker) 抓法人排行 JSON
  - 從 FinMind 抓營收資料
  - 產生 `data/*.json` 供 Bot 使用

- `.github/workflows/daily_update.yml` - GitHub Actions 自動化
  - 每天台灣晚上 21:00 自動執行
  - 支援手動觸發 (workflow_dispatch)

- `data/` 資料夾
  - `institutional_rankings.json` - 法人 5/20/60/120 日買賣超排行
  - `timeseries_sample.json` - 熱門股時間序列
  - `revenue.json` - 營收資料 (YoY, 連續成長)
  - `last_update.json` - 更新時間戳記

### 💬 討論

- **法人 N 日累積**：借鏡 `voidful/tw-institutional-stocker` 的做法
  - 人家每天用 GitHub Actions 抓資料存 JSON
  - 我們不用直接打 TWSE API，讀他的 JSON 就好
  
- **全換 FinMind？**
  - 優點：穩定、統一來源
  - 缺點：即時報價要付費、法人資料晚 8 點更新
  - 結論：混合使用（法人排行讀 GitHub JSON，營收用 FinMind）

- **停損邏輯討論**（南亞科 2408 為例）
  - Bot 寫死 MA20/MA60，對追高進場不適合
  - Agent (Claude) 可以靈活建議 MA10 或固定 %

### 🎫 今日交易記錄

- **南亞科 2408** 買進 187.5 元 × 1 張
  - 收盤 189 元 (+0.8%)
  - 停損建議：172 元 (MA10)
  - 停利目標：200 / 220 / 230

### ⏳ 待辦

- [ ] 改 Bot 讀 `data/` 的 JSON，不再即時打 API
- [ ] 測試 LINE 推播（等額度恢復）
- [ ] 加入 N 日法人累積到確信度評分

---

## 版本紀錄

| 版本 | 日期 | 說明 |
|------|------|------|
| v5.0 | 2025-12 | 滿帆洋行整合版 |
| v4.0 | 2025-12 | 單股分析、查詢限制 |
