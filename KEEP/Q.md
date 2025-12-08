# 情報網 v4.0 專業審查報告

**審查日期：** 2025-12-01
**審查文件：**
- `情報網 v4.0 - AI 開發規格書.txt`（技術實作規格）
- `promt.txt`（投資邏輯審查框架）

**審查角色：** 基金經理人 + Quant 研究員 + 風控主管

---

## 📊 執行摘要

### 邏輯強度評分：**5/10**

| 評估維度 | 得分 | 說明 |
|---------|------|------|
| 架構完整度 | 5/10 | 模組清晰但資料來源不明 |
| 新聞層（AI評估） | 0/10 | **完全缺失** |
| 產業 Mapping | 0/10 | **完全缺失** |
| 籌碼指標 | 4/10 | 邏輯過簡，缺時間維度與金額門檻 |
| 技術指標與風控 | 6/10 | 有基礎邏輯但不夠全面 |
| 策略可行性 | 4/10 | 僅支援做多，缺風險事件過濾 |
| 回測機制 | 0/10 | **完全缺失** |

### 核心問題
❌ **名實不符**：標題為「情報網」但無新聞/資訊蒐集功能
❌ **資料來源不明**：Guardian 5 需要的 `cost_price`、`max_recent_price` 來源未定義
❌ **無法驗證**：缺少回測機制，無法評估策略勝率與風險

---

## 🔍 一、文件關係與矛盾分析

### 1.1 文件定位差異

| 項目 | 文件 1（開發規格書） | 文件 2（審查框架） |
|------|---------------------|-------------------|
| **性質** | 技術實作指南 | 策略審查標準 |
| **範圍** | 六大守護者邏輯 | 完整投資流程（7大面向） |
| **AI 應用** | 未提及 | 要求新聞情緒 AI 評估 |
| **產業分析** | 未提及 | 要求產業鏈 Mapping |
| **回測** | 未提及 | 要求回測與勝率計算 |

### 1.2 關鍵缺失

**文件 1 缺少文件 2 要求的核心環節：**

1. **新聞情緒分析層**
   - 文件 2 要求：新聞分類、時效判斷、標題黨過濾
   - 文件 1 現狀：完全未提及

2. **產業鏈 Mapping（軍火庫）**
   - 文件 2 要求：產業關聯、次族群、競爭對手
   - 文件 1 現狀：僅針對個股，無產業視角

3. **回測與驗證**
   - 文件 2 要求：歷史數據模擬、勝率計算、MDD
   - 文件 1 現狀：僅用 Mock Data 展示邏輯

---

## 📋 二、六大守護者專業審查

### 2.1 Guardian 1：市場熔斷

#### 規格定義
```python
if index_price < ma60 OR limit_down_count > 50:
    SYSTEM_HALT
```

#### 評估結果：⚠️ 6/10

**優點：**
- ✅ 有系統性風險防護意識
- ✅ 雙重條件（技術 + 市場氛圍）

**重大問題：**

| 問題 | 說明 | 風險等級 |
|------|------|---------|
| `index_price` 未定義 | 是加權指數？電子指數？ | 🔴 高 |
| `ma60` 來源不明 | 大盤的 60MA？如何計算？ | 🔴 高 |
| `limit_down_count > 50` 門檻過鬆 | 台股 1700 支，50 支僅 3%，2020/03 單日跌停曾達 800+ 支 | 🟡 中 |
| 缺少其他風險指標 | 應加入：VIX、RSI、融資斷頭比 | 🟡 中 |

**建議改進：**
```python
# 建議邏輯
if (index_price < ma60) OR \
   (limit_down_count > 100) OR \
   (market_rsi < 20) OR \
   (vix_equivalent > 30):
    SYSTEM_HALT
```

---

### 2.2 Guardian 2：流動性過濾

#### 規格定義
```python
if average_volume_5days < 1000:
    LIQUIDITY_FAIL
```

#### 評估結果：⚠️ 5/10

**優點：**
- ✅ 避免流動性陷阱

**重大問題：**

| 問題 | 說明 | 風險等級 |
|------|------|---------|
| `1000` 單位不明 | 張數？股數？交易金額？ | 🔴 高 |
| 未考慮股價差異 | 10元股票 vs 1000元股票，合理成交量差異大 | 🟡 中 |
| 只過濾低量，未偵測爆量 | 無法判斷「異常放量」（可能是出貨訊號） | 🟡 中 |
| 缺少成交金額標準 | 應改用「成交金額 > 5000萬」較合理 | 🟡 中 |

**建議改進：**
```python
# 建議邏輯
daily_turnover = average_volume_5days * price
volume_ratio = today_volume / average_volume_5days

if daily_turnover < 50_000_000:  # 5000萬
    LIQUIDITY_FAIL
elif volume_ratio > 5:  # 異常爆量
    ABNORMAL_VOLUME_WARNING
```

---

### 2.3 Guardian 3：籌碼共識

#### 規格定義
```
Foreign Buy + Trust Buy:  +3
Foreign Sell + Trust Buy: +1
Foreign Buy + Trust Sell: +1
Both Sell:               -2
```

#### 評估結果：⚠️ 4/10

**優點：**
- ✅ 量化籌碼共識
- ✅ 區分不同組合

**重大問題：**

| 問題 | 說明 | 風險等級 |
|------|------|---------|
| **時間維度缺失** | 當日買超？連續 N 日？ | 🔴 高 |
| **金額門檻缺失** | 買超 1 張 vs 1000 張評分相同？ | 🔴 高 |
| **自營商缺席** | 台股三大法人：外資、投信、**自營商** | 🟡 中 |
| **未排除 ETF 調整** | ETF 換股日，外資大買可能只是被動配置 | 🟡 中 |
| **無籌碼集中度** | 未考慮主力持股比例、董監持股質押 | 🟡 中 |
| **無買超佔比** | 未計算「買超佔成交量比例」 | 🟡 中 |

**致命案例：**
```
案例 1：外資買超 10 張（成交 10000 張）→ 買超佔比 0.1%
案例 2：外資買超 10 張（成交 100 張）→ 買超佔比 10%
目前邏輯：兩者評分相同（+3 或 +1）
```

**建議改進：**
```python
# 建議評分邏輯
def chips_score(stock):
    # 1. 計算連續買超天數
    foreign_consecutive = count_consecutive_buy_days(stock, 'foreign')
    trust_consecutive = count_consecutive_buy_days(stock, 'trust')

    # 2. 計算買超金額佔比
    foreign_buy_ratio = stock.foreign_buy_amount / stock.total_turnover
    trust_buy_ratio = stock.trust_buy_amount / stock.total_turnover

    # 3. 評分
    score = 0
    if foreign_buy_ratio > 0.1 and trust_buy_ratio > 0.05:
        score += 3  # 強力共識
    elif foreign_consecutive >= 3 or trust_consecutive >= 3:
        score += 2  # 持續買超
    elif foreign_buy_ratio > 0.05 or trust_buy_ratio > 0.03:
        score += 1  # 溫和買超

    # 4. 扣分條件
    if foreign_buy_ratio < -0.1 and trust_buy_ratio < -0.05:
        score -= 2  # 法人同步賣超

    return score
```

---

### 2.4 Guardian 4：技術過熱檢查

#### 規格定義
```python
bias = (price - ma20) / ma20
if bias > 0.2:
    OVERHEATED
```

#### 評估結果：⚠️ 6/10

**優點：**
- ✅ 避免追高
- ✅ 邏輯簡單明確

**重大問題：**

| 問題 | 說明 | 風險等級 |
|------|------|---------|
| **僅用 MA20 不足** | 應加入 MA60、MA120 判斷趨勢 | 🟡 中 |
| **強勢股誤判** | 飆股在啟動期可能長期乖離 > 30% | 🟡 中 |
| **無量價配合** | 未判斷「量能是否同步放大」 | 🟡 中 |
| **缺少其他技術指標** | 應加入 RSI、MACD、布林通道 | 🟡 中 |
| **price 定義不明** | 收盤價？即時價？ | 🔴 高 |

**誤判案例：**
```
台積電（2330）在 2024 年多頭行情：
- 連續 60 日乖離 > 20%
- 目前邏輯：持續標記為 OVERHEATED，錯失上漲行情
```

**建議改進：**
```python
def tech_check(stock):
    bias_20 = (stock.price - stock.ma20) / stock.ma20
    bias_60 = (stock.price - stock.ma60) / stock.ma60
    rsi_14 = calculate_rsi(stock, 14)
    volume_ratio = stock.today_volume / stock.avg_volume_20

    # 多頭格局：允許較高乖離
    if stock.ma20 > stock.ma60 > stock.ma120:
        if bias_20 > 0.3 and rsi_14 > 80:
            return "OVERHEATED"
    # 盤整/空頭：嚴格標準
    else:
        if bias_20 > 0.15 and rsi_14 > 70:
            return "OVERHEATED"

    # 量價背離
    if bias_20 > 0.2 and volume_ratio < 0.8:
        return "DIVERGENCE_WARNING"

    return "SAFE"
```

---

### 2.5 Guardian 5：出場策略（The Reaper）

#### 規格定義
```python
# 停損
if current_price < cost_price * 0.9 OR current_price < ma20:
    SELL

# 移動停利
if current_price < max_recent_price * 0.9:
    SELL
```

#### 評估結果：❌ 3/10

**優點：**
- ✅ 有停損機制
- ✅ 有移動停利概念

**致命問題：**

| 問題 | 說明 | 風險等級 |
|------|------|---------|
| **`cost_price` 來源不明** | 規格書完全未說明從哪來 | 🔴 致命 |
| **`max_recent_price` 定義模糊** | 最近幾天？買入後最高？ | 🔴 致命 |
| **OR 邏輯過於激進** | 買入隔天跌破 MA20 就停損？ | 🟡 中 |
| **未考慮持有時間** | 買入當天就可能觸發停損 | 🟡 中 |
| **與 Guardian 1 關聯不明** | 大盤熔斷時，Guardian 5 還執行嗎？ | 🟡 中 |

**災難性案例：**
```
情境：買入台積電 600 元
Day 1：收盤 598，跌破 MA20（605）→ 觸發停損
Day 5：反彈至 620
結果：過早停損，錯失後續漲幅
```

**關鍵疑問：**
1. **`cost_price` 如何取得？**
   - Mock Data 要包含「模擬持倉列表」嗎？
   - 用戶手動輸入？
   - 系統自動記錄交易？

2. **`max_recent_price` 定義？**
   - 選項 A：買入後最高價
   - 選項 B：20 日內最高價
   - 選項 C：創新高後的最高價

**建議改進：**
```python
def exit_strategy(position):
    holding_days = (today - position.buy_date).days
    profit_ratio = (price - position.cost) / position.cost
    max_profit = (position.max_price_since_buy - position.cost) / position.cost

    # 停損（持有 3 天後才啟用）
    if holding_days >= 3:
        if price < position.cost * 0.92:  # -8% 停損
            return "STOP_LOSS"
        if price < position.ma20 and profit_ratio < -0.05:
            return "TECH_STOP_LOSS"

    # 移動停利（獲利 > 10% 後啟用）
    if max_profit > 0.1:
        if price < position.max_price_since_buy * 0.9:
            return "TRAILING_STOP"

    # 獲利了結
    if profit_ratio > 0.3:  # +30% 獲利
        return "TAKE_PROFIT"

    return "HOLD"
```

---

### 2.6 Guardian 6：倉位配置

#### 規格定義
```
Score >= 3: 20% Allocation (High Confidence)
Score > 0:  10% Allocation (Medium Confidence)
Score <= 0: No Trade
```

#### 評估結果：⚠️ 5/10

**優點：**
- ✅ 根據信心度調整倉位
- ✅ 邏輯簡單

**重大問題：**

| 問題 | 說明 | 風險等級 |
|------|------|---------|
| **未考慮歷史勝率** | 評分高不等於勝率高 | 🟡 中 |
| **缺少動態調整** | 未使用 Kelly 公式等動態倉位管理 | 🟡 中 |
| **無產業分散限制** | 可能同時買入多支同產業股票 | 🔴 高 |
| **無個股上限** | 單一股票可以佔 20%？ | 🟡 中 |

**風險案例：**
```
情境：同時找到 5 支高評分股票（都是 AI 概念股）
- 2330 台積電：20%
- 3711 日月光：20%
- 2454 聯發科：20%
- 3231 緯創：20%
- 6669 緯穎：20%

結果：100% 資金集中在「AI 產業」→ 產業風險過度集中
```

**建議改進：**
```python
def position_sizing(stocks_with_scores):
    positions = {}
    industry_exposure = {}

    for stock in stocks_with_scores:
        # 基礎配置
        if stock.score >= 3:
            base_allocation = 0.15  # 降為 15%
        elif stock.score > 0:
            base_allocation = 0.08  # 降為 8%
        else:
            continue

        # Kelly 公式調整（如果有歷史勝率）
        if stock.win_rate and stock.avg_profit:
            kelly = (stock.win_rate * stock.avg_profit - (1 - stock.win_rate)) / stock.avg_profit
            base_allocation = min(base_allocation, kelly * 0.5)

        # 產業限制
        industry = stock.industry
        if industry_exposure.get(industry, 0) + base_allocation > 0.3:
            base_allocation = 0.3 - industry_exposure.get(industry, 0)

        if base_allocation > 0:
            positions[stock.id] = base_allocation
            industry_exposure[industry] = industry_exposure.get(industry, 0) + base_allocation

    return positions
```

---

## 🚨 三、重大盲點與風險警示

### 3.1 資訊來源判定（事實 vs 幻覺）

| 數據項目 | 來源狀態 | 風險 |
|---------|---------|------|
| `index_price` | ⚠️ 未定義 | 無法驗證 Mock Data 真實性 |
| `ma60` | ⚠️ 計算方式未說明 | 可能與實際市況不符 |
| `limit_down_count` | ⚠️ 定義不明 | 門檻設定缺乏依據 |
| `average_volume_5days` | ⚠️ 單位不明 | 可能誤判流動性 |
| `foreign_investors` | ⚠️ 買超定義模糊 | 無法區分真實法人動向 |
| `cost_price` | ❌ **完全未定義** | **致命缺陷** |
| `max_recent_price` | ❌ **完全未定義** | **致命缺陷** |

### 3.2 推理鏈條檢查

#### 邏輯流程
```
Guardian 1（大盤檢查）
    ↓ PASS
Guardian 2-4（個股篩選）→ 計算評分
    ↓ PASS
Guardian 6（倉位配置）→ 決定買入比例
    ↓
Guardian 5（出場策略）→ 持倉檢查
```

#### 發現的跳步

1. **Guardian 1 → Guardian 2-4**
   - ✅ 邏輯連貫：先判斷大盤再篩個股

2. **Guardian 3 → Guardian 6**
   - ❌ **跳步**：評分直接決定倉位，未考慮：
     - 個股歷史勝率
     - 產業相關性
     - 現有持倉結構

3. **Guardian 5 的獨立性問題**
   - ⚠️ Guardian 5 與其他守護者無關聯
   - 如果 Guardian 1 觸發熔斷，Guardian 5 應該更激進停損
   - 如果 Guardian 3 評分轉負，Guardian 5 應該降低停損容忍度

### 3.3 未被檢查的假設

| 假設 | 反例/風險 |
|------|----------|
| **假設 1：外資+投信同步買超 = 強勢股** | 反例：法人聯合倒貨給散戶（如 2021 年航運股） |
| **假設 2：bias > 20% = 過熱** | 反例：強勢股在啟動初期可能持續高乖離（如 2023 年 AI 股） |
| **假設 3：volume < 1000 = 流動性不足** | 問題：高價股（如大立光 3008）成交量本來就低 |
| **假設 4：跌破 MA20 = 賣出訊號** | 反例：強勢股回測 MA20 是加碼點（如台積電常態） |
| **假設 5：Mock Data 能代表真實市場** | 風險：實際市場有「黑天鵝事件」、「流動性枯竭」等極端情境 |

---

## 🔧 四、專業改進建議

### 4.1 補足缺失模組

#### A. 新聞情緒 AI 評估層（Guardian 0）

**目標：** 將「情報網」名實相符

```python
def guardian_0_news_sentiment(stock):
    """
    爬取新聞 → Gemini 分類 → 過濾正負面
    """
    # 1. 爬取近 3 日新聞
    news = fetch_news(stock.name, days=3)

    # 2. Gemini API 情緒分析
    sentiment_scores = []
    for article in news:
        prompt = f"分析這則新聞對 {stock.name} 的影響：{article.title}\n{article.summary}"
        response = gemini_api(prompt)
        sentiment_scores.append(response.score)  # -1 到 +1

    # 3. 綜合評分
    avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)

    # 4. 過濾
    if avg_sentiment > 0.5:
        return "POSITIVE_NEWS", +2
    elif avg_sentiment < -0.5:
        return "NEGATIVE_NEWS", -3
    else:
        return "NEUTRAL", 0
```

**優先級：🔴 高**（這是「情報網」的核心功能）

---

#### B. 產業鏈 Mapping（軍火庫）

**目標：** 避免產業風險集中，發現關聯機會

```python
INDUSTRY_MAP = {
    "AI": {
        "上游": ["2330 台積電", "3711 日月光"],
        "中游": ["2454 聯發科", "3231 緯創"],
        "下游": ["6669 緯穎", "4938 和碩"],
        "競爭對手": ["2382 廣達 vs 2357 華碩"],
    },
    "電動車": {
        "上游": ["2308 台達電", "1216 統一"],
        # ...
    }
}

def check_industry_risk(selected_stocks):
    """檢查是否過度集中單一產業"""
    industry_count = {}
    for stock in selected_stocks:
        industry = get_industry(stock)
        industry_count[industry] = industry_count.get(industry, 0) + 1

    # 警告：單一產業 > 3 支股票
    for industry, count in industry_count.items():
        if count > 3:
            print(f"⚠️ 警告：{industry} 產業持倉過多（{count} 支）")
```

**優先級：🟡 中**

---

#### C. 回測引擎

**目標：** 驗證策略勝率與風險

```python
def backtest(strategy, historical_data, start_date, end_date):
    """
    回測框架
    """
    portfolio = Portfolio(initial_cash=1_000_000)
    trades = []

    for date in date_range(start_date, end_date):
        # 1. 執行六大守護者
        signals = strategy.run(historical_data[date])

        # 2. 執行買賣
        for signal in signals:
            if signal.action == "BUY":
                portfolio.buy(signal.stock, signal.allocation)
            elif signal.action == "SELL":
                portfolio.sell(signal.stock)

        # 3. 更新持倉市值
        portfolio.update_market_value(historical_data[date])
        trades.append(portfolio.snapshot())

    # 4. 計算績效
    return calculate_metrics(trades)

# 績效指標
def calculate_metrics(trades):
    total_return = (trades[-1].value - trades[0].value) / trades[0].value
    sharpe_ratio = calculate_sharpe(trades)
    max_drawdown = calculate_mdd(trades)
    win_rate = sum(1 for t in trades if t.profit > 0) / len(trades)

    return {
        "總報酬": f"{total_return:.2%}",
        "夏普比率": f"{sharpe_ratio:.2f}",
        "最大回撤": f"{max_drawdown:.2%}",
        "勝率": f"{win_rate:.2%}",
    }
```

**優先級：🔴 高**

---

### 4.2 優化現有守護者

| 守護者 | 改進方向 | 優先級 |
|--------|---------|--------|
| **Guardian 1** | • 加入大盤 RSI<br>• 加入 VIX 台指波動率<br>• 加入融資斷頭比<br>• `limit_down_count` 改為 > 100 | 🔴 高 |
| **Guardian 2** | • 改用「成交金額 > 5000萬」<br>• 加入「爆量偵測」（量比 > 5）<br>• 加入「量縮警示」（量比 < 0.5） | 🟡 中 |
| **Guardian 3** | • 區分「連續買超天數」<br>• 加入「買超佔成交比」<br>• 納入自營商<br>• 排除 ETF 調整日 | 🔴 高 |
| **Guardian 4** | • 加入 MA60/MA120 多空排列<br>• 加入 RSI、MACD<br>• 加入布林通道<br>• 區分「多頭」vs「空頭」格局 | 🟡 中 |
| **Guardian 5** | • 明確定義 `max_recent_price = 買入後 20 日最高`<br>• 加入「持有天數門檻」（3 天後才啟用停損）<br>• 停損改為 -8%（而非 -10%）<br>• 加入「獲利了結」機制（+30%） | 🔴 高 |
| **Guardian 6** | • 加入 Kelly 公式<br>• 加入產業分散限制（單一產業 < 30%）<br>• 降低單一個股上限（15%）<br>• 考慮歷史勝率 | 🟡 中 |

---

### 4.3 可執行的量化指標清單

#### A. 技術指標

```python
# 1. RSI (相對強弱指標)
def calculate_rsi(prices, period=14):
    """判斷超買超賣"""
    # RSI > 70: 超買
    # RSI < 30: 超賣

# 2. MACD (趨勢指標)
def calculate_macd(prices):
    """判斷趨勢轉折"""
    ema_12 = prices.ewm(span=12).mean()
    ema_26 = prices.ewm(span=26).mean()
    macd = ema_12 - ema_26
    signal = macd.ewm(span=9).mean()
    return macd, signal

# 3. 布林通道
def calculate_bollinger_bands(prices, period=20):
    """判斷波動區間"""
    ma = prices.rolling(period).mean()
    std = prices.rolling(period).std()
    upper = ma + 2 * std
    lower = ma - 2 * std
    return upper, ma, lower

# 4. 量能比
def volume_ratio(today_volume, avg_volume):
    """判斷量能異常"""
    return today_volume / avg_volume
```

#### B. 籌碼指標

```python
# 5. 籌碼集中度
def chip_concentration(stock):
    """前 15 大股東持股變化"""
    current_top15 = stock.top15_holdings
    last_month_top15 = stock.top15_holdings_30days_ago
    return current_top15 - last_month_top15

# 6. 外資持股比例
def foreign_ownership_ratio(stock):
    """外資持股佔已發行股數比例"""
    return stock.foreign_shares / stock.total_shares

# 7. 融資使用率
def margin_usage_rate(stock):
    """融資餘額 / 融資限額"""
    return stock.margin_balance / stock.margin_limit
```

#### C. 基本面指標（建議未來加入）

```python
# 8. 本益比 (P/E Ratio)
def pe_ratio(stock):
    return stock.price / stock.eps

# 9. 股價淨值比 (P/B Ratio)
def pb_ratio(stock):
    return stock.price / stock.book_value_per_share

# 10. 殖利率
def dividend_yield(stock):
    return stock.annual_dividend / stock.price
```

---

### 4.4 風險管理模組（建議新增 Guardian 7）

```python
def guardian_7_risk_management(portfolio):
    """
    風險管理守護者
    """
    risks = []

    # 1. 單日最大損失
    if portfolio.today_pnl < portfolio.total_value * -0.03:
        risks.append("單日虧損 > 3%，停止新增部位")

    # 2. 總體曝險
    if portfolio.stock_exposure > 0.8:
        risks.append("持股比例 > 80%，降低曝險")

    # 3. 產業集中度
    industry_exposure = calculate_industry_exposure(portfolio)
    for industry, ratio in industry_exposure.items():
        if ratio > 0.3:
            risks.append(f"{industry} 產業曝險 > 30%")

    # 4. 相關性檢查
    correlation_matrix = calculate_correlation(portfolio.holdings)
    high_corr_pairs = find_high_correlation(correlation_matrix, threshold=0.8)
    if high_corr_pairs:
        risks.append(f"高相關性持股：{high_corr_pairs}")

    return risks
```

---

## ❓ 五、需要釐清的問題清單

### 5.1 必須立即回答（否則無法開發）

#### Guardian 1 - 市場熔斷

| 問題 | 選項 | 建議 |
|------|------|------|
| `index_price` 是哪個指數？ | A. 加權指數<br>B. 電子指數<br>C. 其他 | **建議 A** |
| `ma60` 如何計算？ | A. 大盤近 60 日收盤價平均<br>B. 其他 | **建議 A** |
| `limit_down_count` 定義？ | A. 當日跌停股票數量<br>B. 跌幅 > 9% 股票數量 | **建議 A，門檻改為 > 100** |

#### Guardian 2 - 流動性

| 問題 | 選項 | 建議 |
|------|------|------|
| `average_volume_5days` 單位？ | A. 張數<br>B. 股數<br>C. 成交金額 | **建議改用成交金額 > 5000萬** |
| 是否加入爆量偵測？ | A. 是（量比 > 5 警示）<br>B. 否 | **建議 A** |

#### Guardian 3 - 籌碼

| 問題 | 選項 | 建議 |
|------|------|------|
| 買超/賣超時間範圍？ | A. 當日<br>B. 連續 3 日<br>C. 連續 5 日 | **建議 B（連續 3 日）** |
| 買超金額門檻？ | A. 無門檻<br>B. 買超佔成交比 > 5%<br>C. 買超佔成交比 > 10% | **建議 B** |
| 是否納入自營商？ | A. 是<br>B. 否 | **建議 A** |

#### Guardian 5 - 出場策略

| 問題 | 選項 | 建議 |
|------|------|------|
| `cost_price` 來源？ | A. Mock Data 包含模擬持倉<br>B. 用戶手動輸入<br>C. 系統自動記錄 | **建議 A（MVP 階段）** |
| `max_recent_price` 定義？ | A. 買入後最高價<br>B. 買入後 20 日最高價<br>C. 買入後創新高後的最高價 | **建議 B（買入後 20 日最高）** |
| 停損條件是否太激進？ | A. 維持「跌破 MA20 OR 虧損 10%」<br>B. 改為「跌破 MA20 AND 虧損 5%」<br>C. 改為「持有 3 天後，虧損 8%」 | **建議 C** |

---

### 5.2 功能範圍確認

| 問題 | 選項 |
|------|------|
| 是否要加入新聞情緒分析（Guardian 0）？ | A. 是（呼應「情報網」名稱）<br>B. 否（先做最小可行產品） |
| 是否要加入產業鏈 Mapping？ | A. 是<br>B. 否 |
| 是否要加入回測功能？ | A. 是<br>B. 否（先用 Mock Data 驗證邏輯） |
| 輸出格式要用 emoji 嗎？ | A. 是（如規格書範例：🔥🚫✅）<br>B. 否（純文字） |
| Mock Data 要包含幾支股票？ | A. 4 支（如規格書：A/B/C/D）<br>B. 10 支（更全面測試）<br>C. 其他 |
| Mock Data 要包含持倉清單嗎？ | A. 是（測試 Guardian 5）<br>B. 否 |

---

### 5.3 技術細節確認

| 問題 | 選項 |
|------|------|
| 檔案命名？ | A. `manpan_v4.py`<br>B. `intelligence_network_v4.py`<br>C. 其他 |
| 是否需要模組化？ | A. 單一檔案，函數分隔<br>B. 多檔案（models, guardians, utils）<br>C. 其他 |
| 是否需要設定檔？ | A. 是（如 `config.py` 存放參數）<br>B. 否（硬編碼在腳本中） |

---

## 🎓 六、策略可行性評估

### 6.1 做多策略可行性

#### 有效情境（✅ 勝率預估 55-60%）

| 市場環境 | 個股條件 | 說明 |
|---------|---------|------|
| 大盤多頭 | 法人同步買超 + 技術面健康 | 順勢交易，勝率最高 |
| 大盤盤整 | 產業題材明確 + 籌碼集中 | 選股勝於選時 |
| 跌深反彈 | 過度超賣 + 籌碼穩定 | 短線反彈機會 |

#### 容易失誤情境（❌ 勝率預估 < 40%）

| 市場環境 | 個股條件 | 風險 |
|---------|---------|------|
| 大盤空頭 | 即使籌碼好 | 系統性風險（Guardian 1 應阻擋） |
| 產業輪動 | 買入落後股 | 可能繼續落後 |
| 財報前夕 | 業績不確定性 | 可能暴雷 |
| 重大事件 | FOMC、戰爭 | 市場恐慌 |

#### 建議禁止下單情境

```python
BLACKOUT_PERIODS = [
    "財報公布前 3 天",
    "FOMC 會議日",
    "台股單日跌幅 > 3%",
    "美股單日跌幅 > 2%",
    "VIX > 30（恐慌指數）",
    "個股除權息前 5 天",
]
```

---

### 6.2 回測建議

#### A. 回測方式

```python
# 建議回測框架
backtest_config = {
    "期間": "2020-01-01 至 2024-12-01（5 年）",
    "初始資金": 1,000,000,
    "交易成本": "0.1425%（買） + 0.4425%（賣）",
    "滑價": "0.1%",
    "再平衡頻率": "每日",
    "基準指標": "台灣加權指數",
}
```

#### B. 勝率預估

| 策略版本 | 預期勝率 | 說明 |
|---------|---------|------|
| **目前版本**（僅六大守護者） | 45-50% | 邏輯過簡，缺少新聞/產業層 |
| **+ Guardian 0**（新聞情緒） | 50-55% | 加入資訊優勢 |
| **+ 產業 Mapping** | 55-60% | 避免集中風險 |
| **+ 優化籌碼/技術指標** | 60-65% | 提升信號品質 |
| **完整專業版** | 65-70% | 接近專業基金水準 |

#### C. 回測的盲點與避免

| 盲點 | 避免方式 |
|------|---------|
| **過度擬合（Overfitting）** | • 分為訓練期（2020-2022）、驗證期（2023-2024）<br>• 參數不要過度優化 |
| **倖存者偏差** | • 包含下市股票<br>• 包含全額交割股 |
| **未來函數** | • 確保所有數據都是「當日收盤前可取得」<br>• 不使用「未來資訊」 |
| **交易成本低估** | • 加入滑價 0.1%<br>• 加入手續費 + 證交稅 |
| **極端事件缺失** | • 測試期間應包含 2020/03 股災、2022 熊市 |

---

## 🎯 七、最終建議與執行方案

### 7.1 策略升級路徑

#### 方案 A：最小可行產品（MVP）⏱️ 2-3 小時

**範圍：**
- ✅ 實作六大守護者（按規格書）
- ✅ 用 Mock Data 驗證邏輯
- ✅ 補充缺失的參數定義（用合理假設）

**優點：**
- 快速驗證核心邏輯
- 建立基礎框架

**缺點：**
- 無法驗證實戰效果
- 缺少新聞/產業層

**交付物：**
- `manpan_v4.py`（單一檔案）
- Mock Data（4-6 支測試股票 + 2-3 支持倉）
- 測試報告（展示各種情境）

---

#### 方案 B：專業完整版 ⏱️ 8-12 小時

**範圍：**
- ✅ 方案 A 所有內容
- ✅ Guardian 0（新聞情緒 AI）
- ✅ 產業鏈 Mapping
- ✅ 回測引擎
- ✅ 優化籌碼/技術指標
- ✅ 風險管理模組（Guardian 7）

**優點：**
- 真正的「情報網」（名實相符）
- 可驗證歷史績效
- 接近專業投資模型

**缺點：**
- 開發時間較長
- 需要外部 API（Gemini、新聞源）

**交付物：**
- `intelligence_network_v4/`（模組化專案）
- 完整回測報告
- 績效分析（勝率、夏普、MDD）

---

#### 方案 C：混合方案（建議）⏱️ 5-6 小時

**階段 1（2 小時）：** MVP 驗證
- 實作六大守護者
- 用 Mock Data 測試

**階段 2（2 小時）：** 加入新聞層
- Guardian 0（新聞情緒）
- 產業 Mapping（簡化版）

**階段 3（2 小時）：** 回測與優化
- 簡易回測框架
- 優化籌碼評分邏輯

**優點：**
- 漸進式開發，降低風險
- 每階段都有可驗證成果
- 可依實際狀況調整

---

### 7.2 技術架構建議（方案 C）

```
intelligence_network_v4/
│
├── manpan_v4.py              # 主程式（MVP）
├── guardian_0_news.py        # 新聞情緒分析
├── industry_mapping.py       # 產業鏈字典
├── backtest_engine.py        # 回測框架
├── config.py                 # 參數設定
├── mock_data.py              # Mock Data 生成器
│
├── data/
│   ├── stocks_mock.json      # 測試股票數據
│   ├── portfolio_mock.json   # 測試持倉數據
│   └── market_mock.json      # 測試大盤數據
│
└── reports/
    ├── daily_report.txt      # 每日分析報告
    └── backtest_result.csv   # 回測結果
```

---

### 7.3 建議參數設定（補充規格書缺失）

```python
# config.py

# Guardian 1: 市場熔斷
MARKET_CONFIG = {
    "index": "加權指數",
    "ma_period": 60,
    "limit_down_threshold": 100,  # 改為 100（原規格 50 太鬆）
    "rsi_threshold": 20,           # 新增：大盤 RSI < 20 熔斷
}

# Guardian 2: 流動性
LIQUIDITY_CONFIG = {
    "min_turnover": 50_000_000,    # 改為成交金額 5000 萬
    "volume_spike_ratio": 5,       # 新增：爆量偵測
}

# Guardian 3: 籌碼
CHIPS_CONFIG = {
    "foreign_buy_threshold": 0.05,  # 買超佔成交比 > 5%
    "trust_buy_threshold": 0.03,    # 買超佔成交比 > 3%
    "consecutive_days": 3,          # 連續買超天數
}

# Guardian 4: 技術
TECH_CONFIG = {
    "bias_threshold_bull": 0.3,     # 多頭允許 30% 乖離
    "bias_threshold_bear": 0.15,    # 空頭僅允許 15% 乖離
    "rsi_overbought": 70,
    "rsi_oversold": 30,
}

# Guardian 5: 出場
EXIT_CONFIG = {
    "stop_loss": 0.08,              # -8% 停損（改為 8%，原規格 10%）
    "trailing_stop": 0.10,          # 從高點回落 10%
    "take_profit": 0.30,            # +30% 獲利了結
    "holding_days_min": 3,          # 持有 3 天後才啟用停損
    "max_recent_days": 20,          # max_recent_price = 20 日最高
}

# Guardian 6: 倉位
POSITION_CONFIG = {
    "high_confidence": 0.15,        # 改為 15%（原規格 20%）
    "medium_confidence": 0.08,      # 改為 8%（原規格 10%）
    "max_industry_exposure": 0.30,  # 單一產業上限 30%
}
```

---

## 📊 八、專業總結

### 8.1 整體評價

**邏輯強度：5/10**

這份規格書展現了「風險意識」和「模組化思維」，六大守護者的設計有其合理性。然而，作為一個名為「情報網」的系統，**缺少最核心的「情報蒐集」功能**（新聞分析、產業鏈關聯），這是最大的矛盾。

此外，多處關鍵參數定義不明（如 `cost_price` 來源、`max_recent_price` 定義、籌碼買超門檻），導致無法直接實作。

---

### 8.2 關鍵優點

1. **結構清晰**
   - 六大守護者分工明確
   - 邏輯流程連貫（大盤 → 個股 → 倉位 → 出場）

2. **風險意識**
   - Guardian 1（市場熔斷）
   - Guardian 5（停損/停利）
   - Guardian 6（倉位控制）

3. **量化評分**
   - Guardian 3 的籌碼評分（-2 到 +3）
   - Guardian 6 的倉位配置

---

### 8.3 致命缺陷

1. **缺少「情報」核心**
   - 無新聞情緒分析
   - 無產業鏈關聯
   - 與「情報網」名稱不符

2. **參數定義不明**
   - Guardian 5 的 `cost_price` 來源未說明
   - Guardian 3 的買超定義模糊（時間？金額？）
   - Guardian 2 的流動性門檻（1000 是什麼單位？）

3. **無法驗證**
   - 缺少回測機制
   - 無法計算勝率、最大回撤
   - 僅用 Mock Data 無法證明實戰有效性

---

### 8.4 風險警示

| 風險類型 | 說明 | 發生機率 |
|---------|------|---------|
| **過早停損** | Guardian 5 的 OR 邏輯可能導致買入隔天就停損 | 🔴 高 |
| **產業集中** | Guardian 6 無產業分散限制，可能同時買入 5 支 AI 股 | 🔴 高 |
| **法人倒貨** | Guardian 3 無金額門檻，可能誤判「假突破」 | 🟡 中 |
| **錯失強勢股** | Guardian 4 的 bias > 20% 可能過濾掉飆股 | 🟡 中 |
| **黑天鵝事件** | Guardian 1 無應對極端事件（如戰爭、金融危機） | 🟡 中 |

---

### 8.5 最終建議

#### 短期（MVP）
1. **先釐清問題**（見第五章：需要釐清的問題清單）
2. **實作方案 A**（2-3 小時，驗證邏輯）
3. **用 Mock Data 測試**（至少 6 支股票 + 3 支持倉）

#### 中期（專業化）
1. **加入 Guardian 0**（新聞情緒 AI）
2. **加入產業 Mapping**（避免集中風險）
3. **優化籌碼邏輯**（買超佔比、連續天數）

#### 長期（專業投資模型）
1. **建立回測引擎**（驗證 2020-2024 歷史數據）
2. **加入 Guardian 7**（風險管理模組）
3. **優化技術指標**（MACD、布林通道、相對強弱）
4. **加入基本面篩選**（本益比、殖利率）

---

### 8.6 預期績效（基於專業經驗推估）

| 策略版本 | 年化報酬 | 夏普比率 | 最大回撤 | 勝率 |
|---------|---------|---------|---------|------|
| **目前版本**（規格書原樣） | 3-5% | 0.3-0.5 | -25% | 45-50% |
| **+ 新聞情緒** | 8-12% | 0.6-0.8 | -20% | 50-55% |
| **+ 產業 Mapping** | 10-15% | 0.8-1.0 | -18% | 55-60% |
| **完整專業版** | 15-20% | 1.0-1.3 | -15% | 60-65% |
| **台灣加權指數**（基準） | 8% | 0.5 | -30% | - |

**註：** 以上為牛熊市混合情境的預估，實際績效需經回測驗證。

---

## ✅ 九、下一步行動

### 請決策：

#### 選項 1：立即開發 MVP（建議）
- ⏱️ 2-3 小時
- 📝 先釐清「必須回答的問題」（第五章 5.1）
- 🚀 實作六大守護者 + Mock Data
- ✅ 驗證邏輯可行性

#### 選項 2：完整專業版
- ⏱️ 8-12 小時
- 📝 補充所有缺失模組
- 🚀 包含新聞 AI、產業鏈、回測
- ✅ 可實戰應用

#### 選項 3：混合方案（漸進式）
- ⏱️ 5-6 小時（分 3 階段）
- 📝 階段 1: MVP → 階段 2: 新聞層 → 階段 3: 回測
- 🚀 每階段驗證成果
- ✅ 風險最低

---

**等待您的指示，請選擇執行方案並回答關鍵問題！** 🚀

---

_報告完成日期：2025-12-01_
_分析框架：基金經理人 + Quant 研究員 + 風控主管_
_文件版本：v1.0_
