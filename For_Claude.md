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
1.  **Weekly Review (復盤系統)**:
    -   **Goal**: On Saturday/Sunday, auto-analyze the performance of the past week's recommendations.
    -   **Logic**: Read `records/*.json`, compare recommend price vs. current price, calculate win rate/ROI.
    -   **User Request**: "每日推薦紀錄後 週六OR日自動復盤".
2.  **Database**: Currently using JSON files in `records/`. Might need SQLite/PostgreSQL if data grows.
3.  **Async Processing**: If manual trigger takes too long (>30s), move to async reply pattern.

## ⚠️ Critical Notes
-   **Do NOT revert to Mock Data**. The user hates it.
-   **Do NOT downgrade the model**. Stick to 2.5 Pro.
-   **Zeabur Deployment**: Remember to push to GitHub to trigger deploy.
