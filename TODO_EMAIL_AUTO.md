# 📧 Email 自動化待辦清單

> **完整計畫**：[`EMAIL_AUTO_PLAN.md`](file:///d:/_BRAIN/LIBRARY/EMAIL_AUTO_PLAN.md)
> **開始日期**：2026-01-08
> **目標日期**：2026-01-12（階段 1 完成）

---

## 📎 快速連結（開發時常用）

| 檔案 | 連結 | 何時需要 |
|------|------|----------|
| **完整計畫** | [`EMAIL_AUTO_PLAN.md`](file:///d:/_BRAIN/LIBRARY/EMAIL_AUTO_PLAN.md) | 看完整架構、API 範例 |
| **AI 入口** | [`AGENTS.md`](file:///d:/_BRAIN/AGENTS.md) | 看規則、找其他檔案 |
| **開發規範** | [`CLAUDE.md`](file:///c:/Users/atiti/.claude/CLAUDE.md) | 看 Todo、溝通規範 |
| **持倉策略** | [`STOCK_STRATEGY.md`](file:///d:/_BRAIN/STOCK_STRATEGY.md) | 測試時參考持股資料 |
| **選股規格** | [`SPEC.md`](file:///d:/claude-project/STOCK_HUNTER/SPEC.md) | 了解篩選邏輯 |
| **選股程式** | [`scan_20260106.py`](file:///d:/claude-project/STOCK_HUNTER/scan_20260106.py) | 參考現有程式結構 |
| **Workflow** | [`.github/workflows/daily_update.yml`](file:///d:/claude-project/STOCK_HUNTER/.github/workflows/daily_update.yml) | 修改 GitHub Actions |

---

## 🎯 階段 1：基礎持股健診 Email（優先）

**目標**：1/12 前完成，1/13 出門前可用

---

### 👤 用戶準備工作（30 分鐘）

- [ ] **建立 Google Sheet「股票持倉」**
  - [ ] Sheet 1：持股清單（複製 EMAIL_AUTO_PLAN.md 的表格結構）
  - [ ] 填入目前持股：國巨、神達
  - [ ] Sheet 2：交易紀錄（選配）

- [ ] **建立 GAS Web App**
  - [ ] Google Sheet → 擴充功能 → Apps Script
  - [ ] 複製 EMAIL_AUTO_PLAN.md 的 `Code.gs`
  - [ ] 修改 `SECRET_TOKEN`（自己設定一組亂數，例如：`stock_2026_abc123`）
  - [ ] 部署 → Web 應用程式
  - [ ] 複製網址：`https://script.google.com/macros/s/.../exec`
  - [ ] 測試：`curl "網址?token=你的token"` 確認有回傳 JSON

- [ ] **設定 Gmail App Password**
  - [ ] Gmail → 帳戶設定 → 安全性 → 兩步驟驗證
  - [ ] 產生「應用程式密碼」（郵件 + 其他裝置）
  - [ ] 複製 16 位密碼（去掉空格）

- [ ] **設定 GitHub Secrets**
  - [ ] `GAS_HOLDINGS_URL`：GAS Web App 網址
  - [ ] `GAS_TOKEN`：你設定的 secret token
  - [ ] `GMAIL_USER`：你的 Gmail 信箱
  - [ ] `GMAIL_APP_PASSWORD`：16 位應用程式密碼
  - [ ] `EMAIL_TO`：收件信箱（可以跟 GMAIL_USER 相同）

---

### 💻 開發工作（2 天）

#### Day 1（1/8）：建立核心功能

- [ ] **建立 `scripts/read_holdings.py`**
  ```python
  # 功能：
  # 1. 讀取環境變數 GAS_HOLDINGS_URL, GAS_TOKEN
  # 2. 呼叫 GAS API
  # 3. 解析 JSON，回傳持股清單
  # 4. 儲存到 data/holdings_cache.json（供其他 script 使用）
  # 5. 錯誤處理：API 失敗時回傳空清單 + 警告
  ```
  - [ ] 寫程式
  - [ ] 本地測試（設定環境變數）
  - [ ] 確認 JSON 格式正確

- [ ] **建立 `scripts/holdings_check.py`**
  ```python
  # 功能：
  # 1. 讀取 data/holdings_cache.json
  # 2. 查詢每檔持股當前價格（FinMind API）
  # 3. 計算損益 %
  # 4. 判斷邏輯：
  #    - 是否跌破停損？
  #    - 是否達到停利？
  #    - 獲利 > 5% 且停損未移動 → 建議移動停損
  # 5. 生成操作建議（維持/出場/移動停損）
  # 6. 儲存到 data/holdings_analysis.json
  ```
  - [ ] 寫停損停利判斷邏輯
  - [ ] 寫移動停損建議邏輯
  - [ ] 本地測試（用假資料）
  - [ ] 確認建議合理

- [ ] **建立 `scripts/send_email.py`**
  ```python
  # 功能：
  # 1. 讀取：
  #    - data/holdings_analysis.json（持股健診）
  #    - scan_result_v3.txt（推薦股票，只取極簡行動卡）
  # 2. 生成 Email 內容：
  #    - 主旨：📊 持股健診報告 YYYY-MM-DD
  #    - 內容：
  #      🚨 需要操作（紅色警示）
  #      ✅ 正常持股
  #      📊 今日推薦（簡要）
  # 3. 用 Gmail SMTP 寄送
  # 4. 錯誤處理：寄送失敗時印錯誤但不中斷 workflow
  ```
  - [ ] 寫 Email 文字模板（先純文字，HTML 之後再說）
  - [ ] 串接 Gmail SMTP
  - [ ] 本地測試（寄到自己信箱）
  - [ ] 確認手機可正常閱讀

---

#### Day 2（1/9）：整合 + 測試

- [ ] **修改 `.github/workflows/daily_update.yml`**
  - [ ] 加入 `python scripts/read_holdings.py`
  - [ ] 加入 `python scripts/holdings_check.py`
  - [ ] 加入 `python scripts/send_email.py`
  - [ ] 設定環境變數傳遞
  - [ ] 錯誤處理：Email 失敗不影響 LINE 推送

- [ ] **本地完整測試**
  ```bash
  # 模擬完整流程
  python scan_20260106.py
  python scripts/read_holdings.py
  python scripts/holdings_check.py
  python scripts/send_email.py
  ```
  - [ ] 確認所有 script 順利執行
  - [ ] 確認 Email 收到且內容正確

- [ ] **GitHub Actions 測試**
  - [ ] Commit + Push
  - [ ] 手動觸發 workflow（Run workflow）
  - [ ] 檢查 Actions log
  - [ ] 確認 Email 收到
  - [ ] 修正任何錯誤

- [ ] **Edge Case 測試**
  - [ ] GAS API 失敗時的處理
  - [ ] FinMind API 失敗時的處理
  - [ ] Gmail SMTP 失敗時的處理
  - [ ] 持股清單為空時的處理

- [ ] **文件更新**
  - [ ] 更新 SPEC.md（如果有改選股邏輯）
  - [ ] 更新 README.md（加入 Email 功能說明）

---

### ✅ 階段 1 完成檢查清單

- [ ] 每晚 20:30 自動執行
- [ ] Email 正常寄送到信箱
- [ ] Email 包含持股健診
  - [ ] 顯示當前價格
  - [ ] 顯示損益 %
  - [ ] 判斷是否觸及停損/停利
  - [ ] 給出操作建議
- [ ] Email 包含推薦股票（簡要）
- [ ] 手機可正常閱讀
- [ ] 用戶可透過手機 Google Sheets 更新持股
- [ ] 錯誤處理完善（不會因單一 API 失敗而中斷）

---

## 🔮 階段 2：新聞 + AI 分析（1/13 之後）

**等階段 1 穩定後再做**

### 待辦

- [ ] 申請 NewsAPI Key
- [ ] 申請 Gemini API Key
- [ ] 建立 `scripts/fetch_news.py`
- [ ] 建立 `scripts/ai_analyze.py`
- [ ] 調教 AI prompt
- [ ] 測試 AI 分析品質

---

## 📝 注意事項

### 開發規範（參考 CLAUDE.md）

- ✅ **先計畫後執行**：先列 Todo → 確認 → 開始
- ✅ **每完成一個 Todo 就標記**：不能批次完成
- ✅ **遇到問題立即報告**：不要自己決定替代方案
- ✅ **完成時對照需求檢查**：列出已完成/未完成

### 測試原則

- ✅ 本地測試通過才 push
- ✅ GitHub Actions 測試通過才算完成
- ✅ 實際收到 Email 才算成功

### 時間管理

- 🎯 1/8-1/9：開發 + 測試
- 🎯 1/10-1/11：修 bug + 優化
- 🎯 1/12：最終確認，確保 1/13 可用

---

**建立日期**：2026-01-07
**更新日期**：2026-01-07
**狀態**：等待開始
