# 📖 STOCK_HUNTER 開發導航

> 這份文件是「開發指南」，告訴你（和 AI）改功能時要動哪些檔案，避免漏更新。

---

## 🗺️ 檔案地圖

### 🎯 核心文件（必讀）

| 檔案 | 用途 | 何時讀取 |
|------|------|----------|
| [`SPEC.md`](file:///d:/claude-project/STOCK_HUNTER/SPEC.md) | **完整規格文件**（選股邏輯、評分系統、輸出格式） | 要改任何功能前先讀 |
| [`scan_20260106.py`](file:///d:/claude-project/STOCK_HUNTER/scan_20260106.py) | **主程式**（v5.3 選股 Bot） | 要改邏輯時 |
| [`for_claude.md`](file:///d:/claude-project/STOCK_HUNTER/for_claude.md) | **給 AI 的快速說明**（簡化版） | AI 第一次接觸專案時 |
| [`task.md`](file:///d:/claude-project/STOCK_HUNTER/task.md) | **待辦事項** | 有新想法時記錄 |

### 📚 說明文件

| 檔案 | 用途 | 何時讀取 |
|------|------|----------|
| [`SCAN_20260106.md`](file:///d:/claude-project/STOCK_HUNTER/SCAN_20260106.md) | v5.3 版本說明（功能、改動） | 要了解 v5.3 新功能時 |
| [`README_v3.md`](file:///d:/claude-project/STOCK_HUNTER/README_v3.md) | v3 版本說明（舊版參考） | 回顧歷史時 |
| [`SETUP_GITHUB_ACTIONS.md`](file:///d:/claude-project/STOCK_HUNTER/SETUP_GITHUB_ACTIONS.md) | GitHub Actions 自動化設定 | 要改排程時 |
| [`TODO_EMAIL_AUTO.md`](file:///d:/claude-project/STOCK_HUNTER/TODO_EMAIL_AUTO.md) | Email 自動化計畫（未實作） | 要做 Email 推送時 |

### 🐍 程式模組（src/）

| 檔案 | 職責 | 何時改 |
|------|------|--------|
| `src/main.py` | 主流程控制 | 改流程時 |
| `src/fetcher.py` | 抓取資料（股價、法人） | 改資料來源時 |
| `src/filter.py` | 篩選條件 | 改選股條件時 |
| `src/scorer.py` | **評分邏輯** | 改評分系統時 ⭐ |
| `src/output.py` | **輸出格式**（極簡卡、JSON） | 改報告格式時 ⭐ |
| `src/analysis.py` | 技術分析（ATR、RSI） | 改技術指標時 |
| `src/cache.py` | 快取管理 | 改快取邏輯時 |
| `src/config.py` | 設定檔 | 改常數時 |

### 🔧 輔助腳本（scripts/）

| 檔案 | 用途 |
|------|------|
| `scripts/update_data.py` | 更新股價資料 |
| `scripts/update_revenue.py` | 更新營收資料 |
| `scripts/push_to_linebot.py` | 推送到 LINE Bot |

### 📊 資料目錄（data/）

| 目錄 | 用途 |
|------|------|
| `data/history/` | 每日選股結果（JSON + 報告） |
| `data/raw/` | 原始資料（股價、法人） |
| `data/cache/` | API 快取 |

### 🗄️ 舊檔案（KEEP/）

不要動，只參考。

---

## 🛠️ 開發情境 → 要動哪些檔案

### 情境 1：改評分邏輯（例如新增 YoY 加分）

**要動的檔案**：
1. ✅ `src/scorer.py`（改評分邏輯）
2. ✅ `SPEC.md`（更新規格文件）
3. ✅ [`_BRAIN/LIBRARY/STOCK_HUNTER_SPEC.md`](file:///d:/claude-project/_BRAIN/LIBRARY/STOCK_HUNTER_SPEC.md)（同步更新）
4. ✅ [`_BRAIN/AGENTS.md`](file:///d:/claude-project/_BRAIN/AGENTS.md) - 版本紀錄（記錄 v5.X 改動）
5. ⚠️ 測試：`python scan_20260106.py --offline`（確認不會爆）

**檢查清單**：
- [ ] scorer.py 改好了？
- [ ] SPEC.md 更新了？
- [ ] LIBRARY/STOCK_HUNTER_SPEC.md 同步了？
- [ ] AGENTS.md 版本紀錄更新了？
- [ ] 測試過了？

---

### 情境 2：改報告格式（例如新增手機版卡片）

**要動的檔案**：
1. ✅ `src/output.py`（改輸出格式）
2. ✅ `SPEC.md`（更新輸出格式說明）
3. ✅ [`_BRAIN/LIBRARY/STOCK_HUNTER_SPEC.md`](file:///d:/claude-project/_BRAIN/LIBRARY/STOCK_HUNTER_SPEC.md)（同步更新）
4. ✅ [`_BRAIN/AGENTS.md`](file:///d:/claude-project/_BRAIN/AGENTS.md) - 版本紀錄
5. ⚠️ 測試：`python show_result.py`（看輸出對不對）

**檢查清單**：
- [ ] output.py 改好了？
- [ ] SPEC.md 更新了？
- [ ] LIBRARY/STOCK_HUNTER_SPEC.md 同步了？
- [ ] AGENTS.md 版本紀錄更新了？
- [ ] 測試過了？

---

### 情境 3：改選股條件（例如新增 PE < 25）

**要動的檔案**：
1. ✅ `src/filter.py`（改篩選條件）
2. ✅ `SPEC.md`（更新選股條件）
3. ✅ [`_BRAIN/LIBRARY/STOCK_HUNTER_SPEC.md`](file:///d:/claude-project/_BRAIN/LIBRARY/STOCK_HUNTER_SPEC.md)（同步更新）
4. ✅ [`_BRAIN/STOCK_STRATEGY.md`](file:///d:/claude-project/_BRAIN/STOCK_STRATEGY.md) - 選股條件 v2.0 區塊（如果是基本條件）
5. ✅ [`_BRAIN/AGENTS.md`](file:///d:/claude-project/_BRAIN/AGENTS.md) - 版本紀錄
6. ⚠️ 測試：`python scan_20260106.py --offline`

**檢查清單**：
- [ ] filter.py 改好了？
- [ ] SPEC.md 更新了？
- [ ] LIBRARY/STOCK_HUNTER_SPEC.md 同步了？
- [ ] STOCK_STRATEGY.md 選股條件更新了？
- [ ] AGENTS.md 版本紀錄更新了？
- [ ] 測試過了？

---

### 情境 4：新增功能（例如產業輪動分析）

**要動的檔案**：
1. ✅ `src/analysis.py`（新增分析模組）或新增 `src/rotation.py`
2. ✅ `src/main.py`（整合新功能到流程）
3. ✅ `src/output.py`（報告加入新區塊）
4. ✅ `SPEC.md`（新增功能說明）
5. ✅ [`_BRAIN/LIBRARY/STOCK_HUNTER_SPEC.md`](file:///d:/claude-project/_BRAIN/LIBRARY/STOCK_HUNTER_SPEC.md)（同步更新）
6. ✅ [`_BRAIN/AGENTS.md`](file:///d:/claude-project/_BRAIN/AGENTS.md) - 版本紀錄（例如 v5.3 新功能）
7. ⚠️ 測試：`python scan_20260106.py`（跑完整流程）

**檢查清單**：
- [ ] 新模組寫好了？
- [ ] main.py 整合了？
- [ ] output.py 加入新區塊了？
- [ ] SPEC.md 更新了？
- [ ] LIBRARY/STOCK_HUNTER_SPEC.md 同步了？
- [ ] AGENTS.md 版本紀錄更新了？
- [ ] 測試過了？

---

### 情境 5：修 Bug（例如 API 掛掉）

**要動的檔案**：
1. ✅ 找到問題檔案（可能是 `src/fetcher.py`、`src/cache.py`）
2. ✅ 改 Bug
3. ⚠️ 測試：`python scan_20260106.py`
4. ❌ **不用更新文件**（除非改了邏輯）

---

### 情境 6：改 GitHub Actions 排程

**要動的檔案**：
1. ✅ `.github/workflows/stock_scan.yml`（改排程時間、環境變數）
2. ✅ `SETUP_GITHUB_ACTIONS.md`（更新說明）

---

## 🔗 外部相關檔案（_BRAIN/）

當改 STOCK_HUNTER 功能時，這些 `_BRAIN` 的檔案可能也要同步更新：

| 檔案 | 何時更新 | 連結 |
|------|----------|------|
| **AGENTS.md** | 每次有新版本（v5.X） | [`_BRAIN/AGENTS.md`](file:///d:/claude-project/_BRAIN/AGENTS.md) |
| **STOCK_HUNTER_SPEC.md** | 改評分/選股/輸出邏輯 | [`_BRAIN/LIBRARY/STOCK_HUNTER_SPEC.md`](file:///d:/claude-project/_BRAIN/LIBRARY/STOCK_HUNTER_SPEC.md) |
| **STOCK_STRATEGY.md** | 改選股條件（基本條件） | [`_BRAIN/STOCK_STRATEGY.md`](file:///d:/claude-project/_BRAIN/STOCK_STRATEGY.md) |
| **stock_agent.md** | 改每日分析流程 | [`_BRAIN/.agent/workflows/stock_agent.md`](file:///d:/claude-project/.agent/workflows/stock_agent.md) |
| **morning_report.md** | 改早安報告流程 | [`_BRAIN/.agent/workflows/morning_report.md`](file:///d:/claude-project/.agent/workflows/morning_report.md) |

---

## 🚀 開發前提醒（給 AI）

### 讀取順序

當要改 STOCK_HUNTER 功能時，AI 應該：

1. **先讀** `DEV_GUIDE.md`（這份檔案）→ 知道要動哪些檔案
2. **再讀** `SPEC.md` → 了解完整規格
3. **再讀** 要改的程式檔案（例如 `src/scorer.py`）
4. **改完後**，記得更新相關文件（檢查清單）

### 測試指令

```bash
# 測試選股邏輯（用快取，不浪費 API）
python scan_20260106.py --offline

# 正式跑選股（會抓最新資料）
python scan_20260106.py

# 查看輸出結果
python show_result.py

# 回測（測試評分邏輯）
python backtest_v4.py
```

---

## ⚠️ 常見錯誤

- ❌ 改了 `src/scorer.py` 但忘記更新 `SPEC.md`
- ❌ 改了評分邏輯但忘記更新 `_BRAIN/LIBRARY/STOCK_HUNTER_SPEC.md`
- ❌ 新增功能但忘記更新 `_BRAIN/AGENTS.md` 版本紀錄
- ❌ 沒有測試就直接 commit（用 `--offline` 先測！）

---

## 📌 快速連結

- [返回 AGENTS.md](file:///d:/claude-project/_BRAIN/AGENTS.md)
- [查看規格 SPEC.md](file:///d:/claude-project/STOCK_HUNTER/SPEC.md)
- [詳細規格 STOCK_HUNTER_SPEC.md](file:///d:/claude-project/_BRAIN/LIBRARY/STOCK_HUNTER_SPEC.md)
- [持倉策略 STOCK_STRATEGY.md](file:///d:/claude-project/_BRAIN/STOCK_STRATEGY.md)

---

## 📝 版本紀錄

| 日期 | 內容 |
|------|------|
| 2026-01-09 | 初版建立（避免改功能時漏更新文件） |
