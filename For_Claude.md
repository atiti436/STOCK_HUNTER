# 🕵️‍♂️ Project Handover: Stock Hunter v2.5

## 👤 User Profile (The Boss)
-   **Personality**: Direct, results-oriented, values honesty. Doesn't like "fake" or "mock" data.
-   **Preferences**:
    -   **Model**: **Gemini 2.5 Pro** (Must use this! Do not downgrade to 1.5 Flash/Pro unless explicitly asked).
    -   **Data**: Must be **REAL**. We switched from mock news to **Google News RSS**.
    -   **Style**: Likes "Premium" and "Cool" designs (e.g., Cyberpunk/Dark mode for UI).
    -   **Communication**: Keep it professional but friendly. Acknowledge mistakes immediately.
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
