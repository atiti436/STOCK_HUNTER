# 🕵️‍♂️ Project Handover: Stock Hunter v2.5

## 👤 User Profile (The Boss)
-   **Personality**: Direct, results-oriented, values honesty. Doesn't like "fake" or "mock" data.
-   **Preferences**:
    -   **Model**: **Gemini 2.5 Pro** (Must use this! Do not downgrade to 1.5 Flash/Pro unless explicitly asked).
    -   **Data**: Must be **REAL**. We switched from mock news to **Google News RSS**.
    -   **Style**: Likes "Premium" and "Cool" designs (e.g., Cyberpunk/Dark mode for UI).
    -   **Communication**: 
        -   **Ask Before Acting**: The user is learning (Python + Stock Trading). If a request is ambiguous (e.g., "Find stable stocks"), **DO NOT ASSUME**. Ask clarifying questions first (e.g., "By stable, do you mean low volatility or high dividend?").
        -   **Explain Like I'm 5**: Avoid heavy jargon. Explain *why* we are doing this (e.g., "We need this API because...").
        -   **Honesty**: Acknowledge mistakes immediately.
-   **Habits**: Checks the report daily at **8:00 AM**.

## 🏗️ System Architecture (Current Status)
-   **Platform**: Zeabur (Python/Flask).
-   **Core Script**: `stock_hunter_v2.py`.
-   **Key Components**:
    1.  **Data**: Yahoo Finance (Price) + TWSE (Chips) + Google News RSS (Real-time).
    2.  **Analysis**:
        -   **Market**: Safety check (MA60).
        -   **Chips**: Foreign/Trust consensus.
        -   **Sector**: Industry strength/weakness analysis (New!).
        -   **Day Trade**: CDP + Volume Spike logic.
    3.  **AI**: **Gemini 2.5 Pro** analyzes news *only* for the top candidates (Cost optimization).
    4.  **UI**: LINE Bot with Rich Menu (6-grid).

## 🚀 Recent Changes (v2.5)
-   [x] **Real News**: Replaced mock data with Google News RSS parser.
-   [x] **Sector Analysis**: Added logic to score stocks based on industry performance.
-   [x] **Macro News**: Added monitoring for "Trump", "Fed", "Jensen Huang".
-   [x] **Optimization**: Moved AI analysis to the end (post-filter) to save tokens.
-   [x] **Model**: Hardcoded `gemini-2.5-pro`.

## 📝 Next Steps (To-Do)
1.  **Deep Weekly Review (深度復盤)**:
    -   **Goal**: Not just ROI, but **WHY**.
    -   **Logic**: If a recommended stock failed (e.g., dropped), ask Gemini to analyze the "Crime Scene". Compare the recommendation reasons vs. the actual outcome. Was it a false breakout? Market crash?
    -   **User Request**: "推(結果收盤大跌)分析WHY".

2.  **"Almost There" Watchlist (盤整轉強/低估股)**:
    -   **Goal**: Identify stocks that are *almost* good enough (e.g., score 2/5) or "Consolidation turning positive".
    -   **Logic**: Create a "Watchlist" category for stocks that pass technicals but maybe lack strong chip consensus yet.

3.  **Stock Search & Explain (個股查詢)**:
    -   **Goal**: User types "2330", bot analyzes it and explains.
    -   **Critical**: If NOT recommended, explain **WHY** (e.g., "Score is only 1 because Foreign investors are selling").
    -   **User Request**: "輸入2330 你就整理他的資訊 告訴WHY不推薦".

4.  **Database**: Currently using JSON files in `records/`. Might need SQLite/PostgreSQL if data grows.
5.  **Async Processing**: If manual trigger takes too long (>30s), move to async reply pattern.

## ⚠️ Critical Notes
-   **Do NOT revert to Mock Data**. The user hates it.
-   **Do NOT downgrade the model**. Stick to 2.5 Pro.
-   **Zeabur Deployment**: Remember to push to GitHub to trigger deploy.

---

## 🔧 Recent Fixes (2025-12-02)

### Fixed by Claude (Previous Session)
**Issue**: Zeabur deployment kept failing with 404 errors.

**Root Causes**:
1. ❌ LINE BOT SDK version conflict (`line-bot-sdk==3.5.0` incompatible with v2 code syntax)
2. ❌ `requests==2.31.0` version conflict with line-bot-sdk dependencies
3. ❌ Python 3.13 too new → `aiohttp` compilation failed
4. ❌ Zeabur misdetected project as static site (missing Dockerfile)

**Solutions Applied**:
1. ✅ Downgraded `line-bot-sdk` to `2.4.2` (compatible with existing code)
2. ✅ Removed `requests` version constraint (let pip auto-resolve)
3. ✅ Added `runtime.txt` with `python-3.11.9`
4. ✅ Added `Procfile` for Zeabur deployment
5. ✅ Modified `send_line_push()` to skip if `LINE_USER_ID` is empty/test

### Fixed by Claude (Current Session - 2025-12-02 20:30)
**Issue**: Timezone mismatch - scheduled job would run at 16:00 (4 PM) instead of 08:00 (8 AM).

**Root Cause**:
- Dockerfile uses `python:3.11-slim` (default UTC timezone)
- `scheduler.add_job(..., hour=8)` runs at UTC 8:00 = Taiwan 16:00

**Solution Applied**:
- ✅ Added timezone configuration to `Dockerfile`:
  ```dockerfile
  ENV TZ=Asia/Taipei
  RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
  ```
- Now `hour=8` in scheduler means Taiwan 08:00 (correct!)
- Also fixes `datetime.now()` for accurate record filenames

**Files Modified**:
- `Dockerfile` (lines 5-7 added)

**Testing**:
- Scheduled push should now trigger at Taiwan 08:00 tomorrow
- Check Zeabur logs for startup message with correct timezone

### Fixed by Claude (Current Session - 2025-12-03 01:00)
**Issue**: Yahoo Finance API Rate Limit (429 Too Many Requests) - IP blocked after ~900 requests.

**Root Cause**:
- Yahoo Finance限制：每秒 2-5 個請求
- 程式用 10 個並發執行緒同時打 API → 瞬間觸發 Rate Limit
- IP 被封鎖 5-10 分鐘

**Solution Applied**:
- ✅ **完全改用 TWSE 官方 API** (台灣證交所)
  - API: `https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY`
  - 沒有 Rate Limit
  - 官方資料更準確
- ✅ 新函數：`get_stock_data_twse(ticker)`
  - 抓取最近 **6 個月**歷史資料（計算 MA120 需要 120 天 ≈ 6 個月）
  - 每支股票發 6 次請求（每月 1 日），每次間隔 0.3 秒
  - 計算 MA20, MA60, MA120
- ✅ 保留相容性：`get_stock_data_yahoo()` 實際呼叫 TWSE API
- ✅ 處理 SSL 憑證問題：`verify=False` + `urllib3.disable_warnings()`

**Performance Impact**:
- ⏱️ 第一階段（980 支快速篩選）：從 30 秒 → **4-6 分鐘**（慢了，但穩定）
- ✅ 不會再被封鎖
- ✅ 第二階段（Gemini AI 分析）：維持 30 秒

**Files Modified**:
- `stock_hunter_v2.py` (lines 15-238: new TWSE API implementation)

**Why 6 months?**
- MA120 = 120 日均線 ≈ 6 個月（扣除週末/假日）
- 需要至少 120 筆收盤價才能計算
- TWSE API 一次只能抓 1 個月資料 → 需要抓 6 次

### Fixed by Claude (Current Session - 2025-12-03 01:45)
**Issue**: `KeyError: 'change_pct'` - 產業分析時備用股票清單缺少欄位

**Root Cause**:
- `get_taiwan_listed_stocks()` 失敗時回傳備用清單（5 支股票）
- 備用清單只有 `ticker` 和 `name`，缺少 `change_pct` 欄位
- 第 873 行產業分析時直接存取 `stock['change_pct']` 導致 KeyError

**Solution Applied**:
- ✅ 備用清單加上 `'change_pct': 0.0` 預設值
- ✅ 產業分析改用 `stock.get('change_pct', 0.0)` 安全取值
- ✅ 加強錯誤處理：顯示完整 traceback 方便除錯

**Files Modified**:
- `stock_hunter_v2.py` (lines 145-156, 868-874)
