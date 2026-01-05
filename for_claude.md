# 🔧 股票選股程式交接報告（2026-01-05）

## ⚠️ 重大發現

### 問題1：FinMind 批量 vs 單檔的資料延遲差異

**測試結果**：
```python
# 單檔抓取（有今日資料）✅
dl.taiwan_stock_daily(stock_id='2330', start_date='2026-01-02', end_date='2026-01-05')
→ 返回：2026-01-02, 2026-01-05 兩筆資料

# 批量抓取（延遲1-2天）❌
dl.taiwan_stock_daily(start_date='2026-01-02', end_date='2026-01-05')
→ 返回：只到 2026-01-02，沒有 2026-01-05
```

**結論**：
- FinMind 批量 API 有延遲（晚 1-2 天）
- 單檔查詢即時更新
- **這是核心問題！導致程式抓到舊資料**

---

## 🐛 目前程式的問題

### scan_v4.py (v4.2 嘗試優化版)

**問題清單**：

1. **步驟1：股價批量抓取抓到舊資料**
   - 位置：第 868 行
   - 現象：批量抓取只拿到 2025-12-01 的資料
   - 原因：FinMind 批量 API 延遲

2. **步驟4：歷史股價快取失效**
   - 位置：第 1057 行
   - 現象：`0/116 檔有歷史資料`
   - 原因：因為步驟1的日期錯誤，快取無法使用

3. **步驟6：營收逐檔抓取，超慢**
   - 位置：約 1077 行
   - 現象：116 次 API 呼叫，需 10-15 分鐘
   - 原因：未優化成批量抓取（但營收可能不支援批量）

4. **Token 輪替邏輯錯誤（已修正）**
   - 位置：第 330-342 行
   - 問題：任何錯誤都切換 Token
   - 修正：只在 Rate Limit 錯誤才切換

---

## ✅ 已完成的優化

### v4.2 優化項目

| 步驟 | 優化前 | 優化後 | 效果 |
|------|--------|--------|------|
| 3. 法人 | 122次逐檔 | **1次批量** | ✅ 秒殺 |
| 4. 歷史股價 | 122次逐檔 | **0次（快取）** | ✅ 秒殺 |

**注意**：優化有效，但因步驟1的資料問題，整體失敗。

---

## 🔑 關鍵程式碼位置

### scan_v4.py 重要區塊

```python
# 第 851-877 行：步驟1 批量抓取股價
dl.taiwan_stock_daily(start_date=start_date, end_date=end_date)  # ← 問題在這

# 第 880 行：日期判定邏輯
data_date = str(df_sorted['date'].iloc[0])  # ← 這裡拿到 2025-12-01

# 第 914-916 行：篩選最新交易日資料
df_latest = df_sorted[df_sorted['date'] == data_date]  # ← 因日期錯，篩選失敗

# 第 317-438 行：法人批量抓取（已優化）✅
dl.taiwan_stock_institutional_investors(start_date=..., end_date=...)  # 不指定 stock_id

# 第 257-273 行：歷史股價改從快取讀取（已優化）✅
def fetch_historical_prices(ticker, days=10, cache=None):
    return cache[ticker][:days]  # 從記憶體讀取，0次API

# 第 1057 行：使用快取
prices = fetch_historical_prices(ticker, days=20, cache=historical_data_cache)
```

---

## 💡 解決方案選項

### 方案A：混合模式（推薦）

**步驟1：用批量抓歷史 + 單檔抓今日**
```python
# 抓歷史 30 天（批量，快）
df_history = dl.taiwan_stock_daily(start_date='2025-12-01', end_date='2026-01-02')

# 抓今日資料（逐檔，但只抓需要的 116 檔）
for ticker in candidate_tickers:
    df_today = dl.taiwan_stock_daily(stock_id=ticker, start_date='2026-01-05', end_date='2026-01-05')
    # 合併到快取
```

**優點**：
- 歷史資料快（批量）
- 今日資料準（單檔）
- API 呼叫：30+116 = 146 次（可接受）

---

### 方案B：改用證交所 API（第二選擇）

**證交所 STOCK_DAY_ALL**：
```python
url = 'https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL'
response = requests.get(url)  # 1次呼叫，有今日資料
```

**優點**：
- 批量抓取，1次呼叫
- 有今日即時資料
- 免 Token

**缺點**：
- 只有當日，無歷史資料
- 需要另外抓歷史（回到逐檔）

---

### 方案C：週五資料暫用（臨時）

**使用方式**：
```bash
cd /d/claude-project/STOCK_HUNTER
python scan_v4.py --offline
```

**優點**：
- 0 API 呼叫
- 立即可用
- 週五資料品質好

**缺點**：
- 不是今日資料（週五 → 週一差 1 個交易日）

---

## 📊 API 使用統計（FinMind Dashboard）

**實際觀察**：
- 使用次數：170 次
- Token 限額：1600 次/小時（付費版）
- 使用率：10.6%

**結論**：API 用量很少，不需要過度擔心 Rate Limit。

---

## 🔧 待修復優先級

### P0（必須修復）
1. **修正步驟1的資料延遲問題**
   - 實施方案A：混合模式
   - 或方案B：改證交所 API

### P1（重要優化）
2. **營收改批量抓取**
   - 需先驗證 FinMind 營收 API 是否支援批量
   - 如不支援，接受逐檔（10分鐘可接受）

### P2（已完成）
3. ✅ 法人批量抓取
4. ✅ 歷史股價快取
5. ✅ Token 輪替邏輯修正

---

## 🚀 快速執行指南（給下個 Claude）

### 診斷問題
```bash
cd /d/claude-project/STOCK_HUNTER

# 測試批量抓取
python -c "
from FinMind.data import DataLoader
dl = DataLoader()
dl.login_by_token(api_token='...')
df = dl.taiwan_stock_daily(start_date='2026-01-05', end_date='2026-01-05')
print(df['date'].max())  # 應該是 2026-01-05，但批量可能只到 2026-01-02
"
```

### 執行選股
```bash
# 當日資料（需修復）
python scan_v4.py

# 離線模式（用週五資料）
python scan_v4.py --offline
```

---

## 📝 FinMind Token 資訊

**Token 1（付費 Backer）**：
```
eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMS0wMyAwMDoxODoyNSIsInVzZXJfaWQiOiJhdGl0aSIsImlwIjoiMTExLjI0My4xNDIuOTkifQ.0AoJDWaK-mWt1OhdyL6JdOI5TOkSpNEe-tDoI34aHjI
```
- 限額：1600 次/小時
- 使用率：約 10%

**備用 Token 2-3**：
- 位置：scan_v4.py 第 53-56 行

---

## 📚 相關檔案

| 檔案 | 用途 | 狀態 |
|------|------|------|
| `scan_v4.py` | 主程式（v4.2 嘗試優化版） | ⚠️ 有問題 |
| `scan_v3.py` | 舊版（穩定但慢） | ✅ 可用 |
| `data/history/2026-01-03.json` | 週五資料（6檔推薦） | ✅ 完整 |
| `data/history/2026-01-05.json` | 今日資料 | ❌ 空白/未產生 |
| `_BRAIN/STOCK_STRATEGY.md` | 持倉策略 | ✅ 最新 |

---

## 🎯 給下個 Claude 的建議

1. **先測試 FinMind 當下的資料狀態**
   - 批量抓取到幾號？
   - 單檔抓取到幾號？

2. **實施方案A（混合模式）**
   - 歷史用批量（快）
   - 今日用單檔（準）

3. **驗證營收 API 是否支援批量**
   ```python
   df = dl.taiwan_stock_month_revenue(start_date='2024-12-01', end_date='2026-01-05')
   # 不指定 stock_id，看是否回傳全市場
   ```

4. **如果時間緊迫**
   - 先用 `--offline` 模式給用戶週五資料
   - 再慢慢修正程式

---

## 🔗 相關文檔

- FinMind 文檔：https://finmind.github.io/
- 籌碼面 API：https://finmind.github.io/tutor/TaiwanMarket/Chip/
- 證交所 API：https://openapi.twse.com.tw/

---

## ⚠️ 最新調查發現（2026-01-05 23:40）

### 檔案留存狀況調查

**週五確實有抓到資料，但「不是批量原始資料」**：

| 檔案 | 大小 | 內容 | 用途 |
|------|------|------|------|
| `data/history/2026-01-03.json` | 2.8K | **最終推薦股**（6檔） | ❌ 無法重用 |
| `data/raw/2026-01-03.json` | 71K | **候選股**（145檔） | ⚠️ 部分可用 |

### 問題根源

**程式沒有保存「批量抓取的全市場歷史股價」**：

1. ✅ 步驟1：批量抓 30 天全市場股價 → 存在**記憶體**（`historical_data_cache`）
2. ✅ 處理完候選股、篩選、評分
3. ✅ 儲存最終結果到 `data/history/`
4. ❌ **記憶體清空，歷史股價快取沒有持久化**
5. ❌ 下次執行 → **從0開始抓**

### 真正的優化方案

**方案A+：保存批量資料快取**

```python
# 步驟1後加入（scan_v4.py 第 877 行後）
import pickle
cache_file = 'data/cache/stock_history_cache.pkl'
with open(cache_file, 'wb') as f:
    pickle.dump(historical_data_cache, f)
print(f'   [OK] 歷史股價快取已存檔: {cache_file}')
```

**下次執行時**：
1. 檢查快取是否存在且未過期（<24小時）
2. 讀取快取 `pickle.load()` - **0次API**
3. 只單檔抓今日資料（116檔） - **116次API**
4. 合併快取 + 今日資料 → 完成

**預估效果**：
- API呼叫：116次（vs 目前上千次）
- 執行時間：2-3分鐘（vs 目前15+分鐘）
- 開發時間：30分鐘

### 背景執行狀況

4個背景執行全部超時失敗（timeout 124），卡在步驟3法人資料（20/122檔），原因：
- 逐檔抓取太慢
- 部分股票 API 回應超過 20 秒
- 累積超過 10 分鐘限制

### 用戶決定

**選擇最簡化方案**：
1. ❌ 不要複雜優化（批次、快取）
2. ✅ 用最笨的 for 迴圈逐檔抓
3. ✅ 法人資料只抓 5 天（夠判斷趨勢）
4. ✅ 每次 API 都 print 原始資料（確認是否被擋IP或空值）
5. ✅ 建立 `scan_v4_simple.py` - 最保險、一定能跑完

---

**交接時間**：2026-01-05 23:40（更新）
**交接人**：Claude (Sonnet 4.5)
**接手人**：下一個 Claude

**最後提醒**：
1. 用戶很在意即時性，不要再建議用週五資料
2. **優先做 scan_v4_simple.py，把複雜優化留到明天**
3. 每個 API 呼叫都要 print，方便 debug
