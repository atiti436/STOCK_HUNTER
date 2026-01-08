# 選股程式規格書 v5.2 (融資券 + YoY 版)

**版本**: v5.2 - 2026-01-06
**目標**: 找「法人有在買、籌碼乾淨、趨勢向上」的股票

---

## 一、核心篩選條件

### 1. 基本面條件 (硬門檻)
| 項目 | 條件 | 說明 |
|------|------|------|
| 股價區間 | **90-300 元** | 鎖定中高價股 |
| 本益比 | PE < 35 | 避免估值過高 |
| 排除類型 | 金融、營建、ETF | 排除特殊產業 |

### 2. 技術面條件 (硬門檻 + 加分項)
**【硬門檻】**
| 項目 | 條件 | 說明 |
|------|------|------|
| 均線位置 | 股價 > MA20 | 趨勢向上 |
| 5日累積漲幅 | < 15% | 避免錯過強勢飆股 |
| RSI | < 85 | 避免過熱 |
| 日成交量 | > 800 張 | 流動性 |

**【加分項】**
| 項目 | +1 分條件 | 說明 |
|------|----------|------|
| 量能 | 今日量 > 5日均量 | 人氣匯聚 |
| 動能 | 乖離>1% 且收紅 | 攻擊態勢 |
| 位階 | 漲幅 0~5% | 穩健不追高 |

### 3. 籌碼面條件 (硬門檻 + 加分項)
| 項目 | 條件 | 說明 |
|------|------|------|
| 法人連續買超 | ≥ 2 天 (硬門檻) | 趨勢確立 |
| 法人5日買超 | > 300 張 (硬門檻) | 買盤力道 |
| 法人1月累積 | > -10,000 張 (硬門檻) | 避免法人撤退股 |
| +1 分 | 法人5日買超 > 0 | 加分項 |
| +1 分 | 連續買超 ≥ 3 天 | 加分項 |

### 4. v5.2 新增：融資券加分 (Bonus)
| 項目 | +1 分條件 | 說明 |
|------|----------|------|
| 籌碼安定 | 融資3日減 + 法人買 | [資減] 散戶走、法人來 |
| 軋空燃料 | 融券3日增 | [軋空] 有嘎空潛力 |

### 5. v5.2 新增：營收 YoY 加分 (Bonus)
| 項目 | +1 分條件 | 說明 |
|------|----------|------|
| 營收成長 | YoY > 0% | 基本面加分 (非硬門檻) |

> **空窗期處理**：1-10號若無當月資料，自動 fallback 上月 YoY

---

## 二、資料來源與 API

### 資料提供商
1. **FinMind API** (主要資料源)
   - 股價資料
   - 法人買賣超
   - 營收資料
   - 財報資料

2. **台灣證交所 API**
   - 本益比資料 (`https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d`)

### Token 管理
```python
FINMIND_TOKENS = [
    'Token1',  # Backer 付費版 1600/hr
    'Token2',  # 免費版 600/hr
    'Token3',  # 免費版 600/hr
]
```
- 支援輪替 (rate limit 時自動切換)
- 只在 429 錯誤時切換

---

## 三、資料流程 (6 大步驟)

### 步驟 1: 抓取當日股價資料
**API**: `taiwan_stock_daily`
```python
# v3: 逐檔抓取
for ticker in all_tickers:
    df = finmind.taiwan_stock_daily(stock_id=ticker, start_date=today, end_date=today)

# v4: 批量抓取 (優化)
df = finmind.taiwan_stock_daily(start_date=today, end_date=today)  # 全市場
```
**輸出**: `{ticker: {name, price, volume, change_pct}}`

### 步驟 2: 抓取 PE 本益比
**API**: 證交所 `BWIBBU_d`
```python
url = f'https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d?date={date}'
```
**篩選**: PE < 35
**輸出**: `{ticker: pe_value}`

### 步驟 3: 抓取法人買賣超資料
**API**: `taiwan_stock_institutional_investors`
```python
# v3: 逐檔抓取
for ticker in candidates:
    df = finmind.taiwan_stock_institutional_investors(
        stock_id=ticker, start_date=start, end_date=end)

# v4: 批量抓取 (優化)
df = finmind.taiwan_stock_institutional_investors(
    start_date=start, end_date=end)  # 全市場
```
**輸出**:
```python
{ticker: [
    {'date': '2026-01-05', 'total': 1000, 'foreign': 800, 'trust': 200, ...},
    ...
]}
```

### 步驟 4: 抓取歷史股價 (計算技術指標)
**API**: `taiwan_stock_daily` (10-20日)
```python
# v3: 逐檔抓取
for ticker in candidates:
    df = finmind.taiwan_stock_daily(stock_id=ticker, start_date, end_date)

# v4: 使用步驟1的快取 (優化)
historical_cache = build_cache_from_step1()
```
**計算**:
- MA10, MA20
- RSI(14)
- 5日漲幅
- 5日均量

### 步驟 5: 抓取營收資料 ⚡ 建議快取化
**API**: `taiwan_stock_month_revenue`
```python
df = finmind.taiwan_stock_month_revenue(
    stock_id=ticker, start_date='2024-01', end_date='2025-12')
```
**計算**: YoY (當月 vs 去年同月)

**⚡ 優化建議 (GEMINI)**:
- 營收每月只公布一次 (每月10號)
- 建立獨立腳本 `update_revenue.py`，每月11號執行
- 存成本機檔案 `data/cache/revenue_cache.pkl`
- 每日選股直接讀快取 → **速度快100倍** (120次API → 0次)

```python
# update_revenue.py (每月11號執行)
import pickle
from FinMind.data import DataLoader

def update_revenue_cache():
    dl = DataLoader()
    dl.login_by_token(api_token=TOKEN)

    # 抓全市場營收
    all_revenue = {}
    for ticker in all_tickers:
        df = dl.taiwan_stock_month_revenue(
            stock_id=ticker,
            start_date='2023-01',
            end_date='2025-12'
        )
        all_revenue[ticker] = calculate_yoy(df)

    # 存檔
    with open('data/cache/revenue_cache.pkl', 'wb') as f:
        pickle.dump({
            'data': all_revenue,
            'update_date': datetime.now(),
        }, f)

# scan.py (每日選股)
def load_revenue_cache():
    with open('data/cache/revenue_cache.pkl', 'rb') as f:
        cache = pickle.load(f)

    # 檢查是否過期 (超過35天提醒更新)
    age = (datetime.now() - cache['update_date']).days
    if age > 35:
        print(f'[WARN] 營收快取已 {age} 天未更新，建議執行 update_revenue.py')

    return cache['data']
```

### 步驟 6: 抓取財報資料
**API**: `taiwan_stock_financial_statement`
```python
df = finmind.taiwan_stock_financial_statement(
    stock_id=ticker, start_date='2024-Q1', end_date='2025-Q3')
```
**計算**: ROE (股東權益報酬率)

---

## 四、篩選邏輯

```
全市場股票 (1700+ 檔)
  ↓
【步驟1】基本篩選: 價格30-300, 排除金融/營建/ETF
  ↓ (~240 檔)
【步驟2】PE篩選: PE < 35
  ↓ (~600 檔 → 取交集 ~120 檔)
【步驟3-6】抓取詳細資料 (法人/技術/營收/財報)
  ↓
【最終篩選】套用所有條件
  ↓
輸出: 0-10 檔推薦股
```

### v5.1 篩選順序 (逐條檢查)
1. 基本資料完整性 (`inst` 和 `hist` 存在)
2. 籌碼面: 連續買超≥2天 且 5日買超>300張 且 1月累積>-10000張
3. 技術面: 5日漲<**15%** 且 價>MA20 且 RSI<**85**
4. 評分: 計算5項加分 (法人買超、連買≥3、攻擊態勢、量增、穩漲)
5. 過濾: 只顯示 **≥3分** 股票
6. 通過 → 加入結果

---

## 五、評分與排序

### v3 評分 (簡單版)
```python
score = buy_days * 10 + (inst_5day / 100)
```
- 法人連續買超天數 × 10
- 法人5日買超張數 / 100

### v4 評分 (進階版)
```python
score = (
    institutional_weight * 0.4 +  # 籌碼面 40%
    technical_weight * 0.3 +      # 技術面 30%
    fundamental_weight * 0.3      # 基本面 30%
)
```

**籌碼面權重**:
- 法人5日買超張數 (0-100分)
- 連續買超天數 (0-100分)
- 法人主力判定 (外資/投信加分)

**技術面權重**:
- MA位置 (價格乖離%)
- RSI (50-70 最佳)
- 成交量 (量價配合)

**基本面權重**:
- PE ratio (越低越好)
- ROE (越高越好)
- 營收YoY (越高越好)

---

## 六、停損停利計算 (v5.1 ATR 劇本小卡)

### ATR (Average True Range) 計算
```python
# 14日平均真實波幅
atr = average(true_range[-14:])
true_range = max(high - low, abs(high - prev_close), abs(low - prev_close))

# 股票類型判斷
if atr / price > 2.5%:
    stock_type = '🐰 兔子 (活潑)'  # 停損設寬
elif atr / price < 1.5%:
    stock_type = '🐢 烏龜 (牛皮)'  # 停損設窄
else:
    stock_type = '🚶 普通'
```

### ATR 通道法停損停利
```python
stop_loss = price - 2 * atr  # 停損
t1 = price + 2 * atr         # 目標一 (先賣一半)
t2 = price + 4 * atr         # 目標二 (趨勢滿足)
```

---

## 七、輸出格式

### JSON 輸出 (v5.1 存檔)
```json
{
  "date": "2026-01-06",
  "timestamp": "2026-01-06T19:36:00",
  "count": 3,
  "stocks": [
    {
      "ticker": "3706",
      "name": "神達",
      "price": 92.6,
      "change_pct": 1.97,
      "pe": 15.0,
      "inst_5day": 36061,
      "inst_leader": "外資",
      "buy_days": 7,
      "5day_change": 12.5,
      "rsi": 72.4,
      "atr": 2.2,
      "atr_pct": 2.4,
      "stock_type": "兔子",
      "stop_loss": 88.2,
      "t1": 97.0,
      "t2": 101.4,
      "stop_note": "2xATR (-4.8%)",
      "score": 4,
      "score_reasons": ["法人買超", "連7天", "攻擊", "量增"],
      "tags": ["[已漲]", "[攻擊]"]
    }
  ]
}
```

### 終端輸出 (表格)
```
================================================================================
推薦股票 TOP 6
================================================================================
排名  代碼  股名      股價    漲幅   PE   法人5日  主力  連買  5日漲  營收YoY  RSI  停損
================================================================================
1    2327  國巨*    241.0   +3.7%  24.2  +5514   投信   4天   +7.6%  +22.4%  54.6  225.5
2    3231  緯創     155.0   +2.0%  20.1  +73398  外資   5天   +5.8%  +194%   70.4  146.6
...
```

### v5.3 極簡行動卡 (Format C) - LINE/手機適用
```
━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 華新科 2492 $132.0
━━━━━━━━━━━━━━━━━━━━━━━━━
🐰 活潑股｜外資連5買
📈 +7,751張｜資減+軋空

💵 進場: 130~132
🛡️ 停損: 123 (-7%)
🎯 目標: 141/149 (+7%/+13%)
━━━━━━━━━━━━━━━━━━━━━━━━━
```

**入場價計算公式**:
```python
entry_low = price - 0.5 * atr   # 等回檔 0.5ATR
entry_high = price              # 收盤價
```

### v5.3 報告結構順序 (2026-01-07)

> 設計原則：**結論優先、詳細收合**

```
1. 📱 極簡行動卡 ← 最上面，一眼看
2. 🔄 產業輪動 ← 今日資金流向 vs Bot 推薦
3. 📊 綜合排名 ← 快速比較
4. 📖 詳細分析 ← 用 <details> 收合，需要再展開
   └─ 每支股票：基本資料 + 新聞 (每支都要查!)
```

---

## 八、已知問題與優化方向

### v3 問題
1. **逐檔抓取慢** - 法人資料 120檔 × 0.5秒 = 1分鐘
2. **歷史股價重複抓** - 每次執行都重新抓 10日資料
3. **沒有資料快取** - 無法離線分析

### v4 優化
1. ✅ **法人改批量抓取** - 1次API抓全市場 (秒殺)
2. ✅ **歷史股價快取** - 步驟1資料重用 (0次API)
3. ❌ **營收仍逐檔** - FinMind 不支援批量營收API
4. ❌ **批量 API 有延遲** - 延遲1-2天 (單檔即時)

### v4_simple 改進
1. ✅ **For 迴圈保證完成** - 不會超時
2. ✅ **法人只抓5天** - 減少資料量
3. ✅ **Debug 輸出** - 前3檔印原始資料
4. ❌ **未實作快取** - 每次都重新下載

---

## 九、建議新版本設計

### 核心改進
1. **混合模式資料抓取**
   - 歷史資料用批量 (快)
   - 今日資料用單檔 (準)

2. **持久化快取**
   ```python
   # 每日存檔
   cache_file = f'data/cache/stock_{date}.pkl'
   pickle.dump({
       'stocks': stocks,
       'pe_data': pe_data,
       'institutional': institutional,
       ...
   }, cache_file)
   ```

3. **⚡ 營收資料快取化** (GEMINI建議)
   - 獨立腳本 `update_revenue.py` (每月11號執行)
   - 存成 `data/cache/revenue_cache.pkl`
   - 每日選股直接讀快取
   - **效益**: 每日節省120次API, ~1分鐘

4. **離線分析模式**
   ```bash
   python scan.py --offline  # 用快取
   python scan.py            # 重新抓取
   ```

5. **篩選統計輸出**
   ```
   篩選統計:
     無資料: 0 檔
     籌碼面不過: 45 檔 (連續買超<2天 或 5日買超<300張)
     技術面不過: 38 檔 (5日漲>=10% 或 量<=均量)
     跌破MA20: 28 檔
     RSI過熱: 7 檔
     營收衰退: 2 檔

   最終通過: 0 檔
   ```

6. **模組化設計**
   - `fetcher.py` - 資料抓取
   - `filter.py` - 篩選邏輯
   - `scorer.py` - 評分排序
   - `output.py` - 輸出格式
   - `cache.py` - 快取管理
   - `update_revenue.py` - 營收快取更新 (每月執行) ⚡

---

## 十、API 使用量估算

### 每日執行
| 步驟 | v3 模式 | v4 模式 | v4_simple | **建議新版** | **新版+營收快取** |
|------|---------|---------|-----------|------------|------------------|
| 1. 股價 | 240次 | 1次 | 1次 | 1+120次 | 1+120次 |
| 2. PE | 1次 | 1次 | 1次 | 1次 | 1次 |
| 3. 法人 | 120次 | 1次 | 120次 | 1次 | 1次 |
| 4. 歷史 | 120次 | 0次(快取) | 120次 | 0次(快取) | 0次(快取) |
| 5. 營收 | 120次 | 120次 | 120次 | 120次 | **0次(快取)** ⚡ |
| 6. 財報 | 120次 | 120次 | 120次 | 120次 | 120次 |
| **總計** | **721次** | **363次** | **602次** | **363次** | **243次** ⚡ |
| **時間** | ~6分鐘 | ~3分鐘 | ~4分鐘 | ~3分鐘 | **~2分鐘** ⚡ |

### 每月執行 (update_revenue.py)
| 項目 | 次數 | 時間 | 頻率 |
|------|------|------|------|
| 營收更新 | 1700次 | ~15分鐘 | 每月11號執行1次 |

**總結**:
- 每日選股: 243次 API, ~2分鐘
- 每月營收更新: 1700次 API, ~15分鐘
- **每日節省**: 120次 API, ~1分鐘
- **每月節省**: 120次×30天 = 3600次 API ⚡

---

## 附錄: 技術指標公式

### RSI (Relative Strength Index)
```python
gains = [max(0, prices[i] - prices[i-1]) for i in range(1, period+1)]
losses = [max(0, prices[i-1] - prices[i]) for i in range(1, period+1)]

avg_gain = sum(gains) / period
avg_loss = sum(losses) / period

if avg_loss == 0:
    rsi = 100
else:
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
```

### MA (Moving Average)
```python
ma10 = sum(prices[:10]) / 10
ma20 = sum(prices[:20]) / 20
```

### 乖離率
```python
deviation = (price - ma) / ma * 100
```

---

**建立時間**: 2026-01-06 00:35
**更新時間**: 2026-01-06 23:50 (v5.2 融資券+YoY 實作完成)
**基於版本**: scan_20260106.py (v5.2 融資券 + YoY + ATR 劇本小卡版)

---

## 📂 改版同步清單

> ⚠️ 更新 `scan_20260106.py` 後，記得一併更新以下檔案：

| 檔案 | 位置 | 更新內容 |
|------|------|----------|
| ✅ **本檔案** | `STOCK_HUNTER/SPEC.md` | 篩選條件、評分系統、版本時間 |
| ✅ **說明文件** | `STOCK_HUNTER/SCAN_20260106.md` | 快速指令、功能說明 |
| ✅ **AI 入口** | `_BRAIN/AGENTS.md` | 股票分析 Agent 區塊 |
| ⭕ **劇本報告** | `data/history/analysis_*.md` | 跑完後的人工分析 (視需要) |

---

## 🚀 未來優化 (待辦)

| 優先 | 功能 | 說明 |
|------|------|------|
| P1 | **Email 發送報告** | 讓 Agent 可以直接發 Email (Zapier/SMTP) |
| P2 | **AI 新聞分析自動化** | Bot 推送時自動附上新聞重點、題材判讀、風險評估 (需 Gemini API) |
| P3 | 相關美股連動 | 自動查詢相關美股走勢 |
| P3 | 0050 候選股預測 | 每季 2/5/8/11 月底掃描潛在納入股 |
