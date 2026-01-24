# 📊 STOCK_HUNTER 重構規格書

> **目的**：統一選股系統，消除版本混亂
> **日期**：2026-01-23
> **狀態**：Draft（等待使用者確認）

---

## 📖 新 Claude 閱讀指引（必讀！）

> ⚠️ **本規格書超過 1100 行，請分段讀取，不可只讀前 200 行就開始執行！**

### 閱讀步驟

1. **第一段**：讀 L1-400（目的、版本定義、輸出格式）
2. **第二段**：讀 L400-800（測試驗證、常見陷阱、嚴禁事項）
3. **第三段**：讀 L800-1112（偽代碼、執行步驟、回滾程序）

### 快速執行方式

使用 workflow 指令自動分段讀取：
```
/refactor
```

workflow 位置：[.agent/workflows/refactor.md](file:///d:/claude-project/.agent/workflows/refactor.md)

### 讀完後

問使用者：「我已讀完 1112 行規格書，確認要執行重構嗎？」
使用者回答「GO」後，開始執行 Phase 0-5。

---

## 🎯 為什麼要重構

**現況問題**：
- ❌ 三個檔案做類似的事（scan_20260106.py、compare_versions_v7.py、scan_all_versions.py）
- ❌ 格式不統一（本地 vs Zeabur）
- ❌ 評分系統混亂（8分/10分不明確）
- ❌ V7 狙擊股遺漏（本地版）
- ❌ 維護地獄（改一次要改三個地方）

**目標**：
- ✅ **單一真相來源**：scan_all_versions.py
- ✅ **格式統一**：本地 = Zeabur
- ✅ **不遺漏**：V4/V5/V6/V7/V8/V9 全支援
- ✅ **可維護**：改一次就全部更新

---

## 📁 檔案架構（最終版）

### 保留檔案

```
STOCK_HUNTER/
├── scan_20260106.py         ← BASE 篩選（工人）
├── scan_all_versions.py     ← 主程式（遙控器）+ 版本篩選
├── scheduler.py             ← 定時排程（Zeabur 用）
└── data/
    ├── raw/
    │   └── *_candidates.json    ← 候選池
    └── history/
        └── analysis_*.md        ← 分析報告
```

### 刪除檔案

```
❌ compare_versions_v7.py    ← 功能併入 scan_all_versions.py
❌ scan_result_lite.txt      ← 改用 scan_result_v9_lite.txt
```

---

## 🔄 資料流

```
┌─────────────────────────────────────┐
│  scan_all_versions.py（主程式）      │
└─────────────────────────────────────┘
         │
         ├─ Step 1: 呼叫 scan_20260106.py (subprocess)
         │           └─ 拉取 FinMind API
         │           └─ 套用 BASE 硬門檻
         │           └─ 產生 candidates.json
         │
         ├─ Step 2: 讀取 candidates.json
         │           └─ 55~80 檔候選股
         │
         ├─ Step 3: 套用多版本篩選
         │           ├─ V4: 穩健（5日<10%, YoY>0）
         │           ├─ V5: 寬鬆（5日<15%）
         │           ├─ V6: 嚴格（5日<5%, YoY>0）
         │           ├─ V6*: 短線（5日<5%）
         │           ├─ V7: 狙擊（今日跌, 近支撐）
         │           ├─ V8: 量縮（連3天站MA20+量縮）
         │           └─ V9: V7+KD 金叉
         │
         ├─ Step 4: 計算評分（10 分制）
         │           └─ 所有候選股都計算，不限版本
         │
         └─ Step 5: 產生輸出
                     ├─ scan_result_all_versions.txt（完整）
                     └─ scan_result_v9_lite.txt（LINE 推送）
```

---

## 🏗️ BASE 硬門檻（scan_20260106.py）

**由 scan_20260106.py 執行**，產生 candidates.json：

```python
# 共同硬門檻（產生 55~80 檔候選池）
價格：30-300 元
今日漲幅：-2% ~ 5%
成交量：> 800 張
PE：< 35
法人今日：買超 > 0
法人連買：>= 2 天
法人5日累積：> 300 張
股價：> MA20
RSI：< 85
```

**輸出**：`data/raw/YYYY-MM-DD_HHMM_candidates.json`

---

## 🎯 版本定義（scan_all_versions.py）

### V4 - 穩健版

```python
條件：
- 30 <= 價格 <= 300
- 法人連買 >= 2 天
- 法人5日 > 300 張
- 5日漲幅 < 10%
- YoY > 0%（硬門檻）

適合：波段 3-7 天
```

### V5 - 寬鬆版

```python
條件：
- 90 <= 價格 <= 300
- 法人連買 >= 2 天
- 法人5日 > 300 張
- 5日漲幅 < 15%
- YoY：不管

適合：當沖/隔日沖
```

### V6 - 嚴格版

```python
條件：
- 30 <= 價格 <= 300
- 法人連買 >= 2 天
- 法人5日 > 300 張
- 5日漲幅 < 5%（起漲點）
- YoY > 0%（硬門檻）

適合：波段 3-10 天
```

### V6* - 短線版

```python
條件：
- 30 <= 價格 <= 300
- 法人連買 >= 2 天
- 法人5日 > 300 張
- 5日漲幅 < 5%（起漲點）
- YoY：不管

適合：短線 1-3 天
```

### V7 - 狙擊版（Daily Dip）

> ⚠️ **新 Claude 容易誤解的點**：
> 
> V7 的「今日漲幅 -4%~0%」跟 BASE 的「今日漲幅 -2%~5%」看起來衝突，
> 但 **V7 是從 candidates.json 的 stocks 篩選**（已經被 BASE 過濾過），
> 所以 V7 實際能選到的範圍是 **-2% ~ 0%**（兩者交集）。
> 
> **這是設計上的限制，不是 bug！** V7 找的是「小幅回檔」的股票。

```python
條件：
- 30 <= 價格 <= 300
- 今日漲幅：-4% ~ 0%（回檔）← 實際範圍 -2% ~ 0%
- 法人5日 > 500 張（加強）
- RSI < 70
- 5日漲幅：-5% ~ 5%（橫盤整理）
- 均線多頭：MA10 > MA20
- 接近支撐：|價格 - MA10| < 2% 或 |價格 - MA20| < 2%

適合：左側交易 2-5 天
特性：買在回檔，需要耐心
```


### V8 - 量縮蓄勢版

```python
條件：
- 連續 3 天 收盤 > MA20
- 連續 3 天 成交量 < MA20(Volume) * 0.8

適合：Swing Trade 2-5 天
狀態：實驗中
```

### V9 - KD 翻揚版

```python
條件：
- 符合 V7 所有條件
- K9 > D9（KD 金叉確認）

適合：右側交易 2-7 天
特性：確認止跌再買，較安全
```

---

## 🎲 評分系統（10 分制）

**對所有候選股計算，不限版本**：

```python
1. 法人買超 (inst_5day > 0)          → +1 分
2. 法人連買 (buy_days >= 3)          → +1 分
3. 攻擊 (bias_ma20 > 1 且收紅)       → +1 分
4. 量增 (volume > avg_volume)        → +1 分
5. 穩漲 (0 < change_pct < 5)         → +1 分
6. 資減 (margin_change < 0 且 inst_5day > 0)  → +1 分
7. 軋空 (short_change > 0)                    → +1 分
8. YoY (revenue_yoy > 0)             → +1 分
9. 投信買 (trust_today > 0)          → +1 分
10. 投信連買 (trust_buy_days >= 2)   → +1 分

滿分：10 分
```

**評分用途**：
- 內部排序（評分高的排前面）
- **不用於篩選**（評分 0 分也可能顯示，只要通過版本）

---

## 📱 輸出格式（scan_result_v9_lite.txt）

### 格式範例（參照 Zeabur 20:30）

```
📊 2026-01-23 選股

🏆 精成科 6191 $120 ⟨全過⟩🐰
   外資連3買｜YoY+91%
   💵117~120｜🛡️111｜🎯128

🏆 建準 2421 $153 ⟨全過⟩🐢
   外資連3買｜YoY+30%
   💵151~153｜🛡️143｜🎯163

⭐ 豐泰 9910 $99 ⟨V5 V6*⟩🐢
   外資連4買
   💵97~99｜🛡️92｜🎯105

─── V7 狙擊 ───

🎯 廣達 2382 $280 ⟨V7⟩RSI51
   💵278~280

🎯 聯茂 6213 $178 ⟨V7 V9⟩RSI55 KD✓
   💵175~178
```

### 格式規則

**1. 標題**
```
📊 YYYY-MM-DD 選股
（空行）
```

**2. 主列表（順勢股）**

通過 V4/V5/V6/V6* 任一版本的股票：

```
{emoji} {股名} {代號} ${價格} {版本標籤}
   {法人資訊}｜{題材}
   💵{進場區間}｜🛡️{停損}｜🎯{停利}
（空行）
```

**emoji 規則**：
- 🏆 = 通過 >= 4 個版本（全過）
- ⭐ = 通過 2-3 個版本
- 📋 = 通過 1 個版本

**版本標籤**：
- `⟨全過⟩` = 通過 V4/V5/V6/V6*
- `⟨V5 V6*⟩` = 通過 2 個版本，列出版本名

**法人資訊**：
- `外資連{n}買` = buy_days >= 2
- `法人+{n}張` = buy_days < 2

**題材**：
- YoY >= 10%：`YoY+{n}%`
- YoY 0-10%：`YoY+{n}%`
- YoY <= 0：省略

**價格資訊**：
- 進場區間：`{price - 0.5*ATR} ~ {price}`
- 停損：`{price - 2*ATR}`
- 停利：`{price + 2*ATR}`

**股性標籤（ATR 計算）**：
- 🐰 兔子 = 活潑股（ATR% > 3%，波動大）
- 🐢 烏龜 = 穩健股（ATR% <= 3%，波動小）
- ATR% = ATR / 收盤價 * 100

**股性用途**：
- 🐰 適合短線操作（波動大 = 獲利空間大，但風險也高）
- 🐢 適合波段持有（穩健上漲，不會被洗掉）

### 格式對照表（防止出錯）

| 項目 | ✅ 正確 | ❌ 錯誤 |
|------|--------|--------|
| 版本標籤 | `⟨全過⟩` `⟨V5 V6*⟩` | `⟨7分⟩` `⟨4分⟩` |
| V7 分隔線 | `─── V7 狙擊 ───` | `━━━━━` |
| V9 顯示 | 在 V7 區塊標 `⟨V7 V9⟩` | 獨立 `─── V9 ───` 區塊 |
| V8 only | 在 `─── V8 量縮 ───` 區塊 | 放進主列表 |
| 評分用途 | 內部排序 | 篩選門檻 |

**錯誤輸出範例（不可出現）**：
```
🏆 精成科 6191 $120 ⟨7分⟩    ← ❌ 顯示評分
━━━━━━━━━━━━━━━━━━━━━    ← ❌ 錯誤分隔線
⚡ V7/V8/V9 特殊股              ← ❌ 錯誤標題
```

**正確輸出範例**：
```
🏆 精成科 6191 $120 ⟨全過⟩    ← ✅ 版本標籤
─── V7 狙擊 ───               ← ✅ 正確分隔線
🎯 聯茂 6213 $178 ⟨V7 V9⟩RSI55 KD✓  ← ✅ V9 顯示在 V7 區塊
```

**3. V7 狙擊區塊**

只通過 V7（不通過 V4/V5/V6/V6*）的股票：

```
─── V7 狙擊 ───
（空行）
🎯 {股名} {代號} ${價格} ⟨V7⟩RSI{rsi}
   💵{支撐價}~{價格}
（空行）
```

**支撐價**：`min(MA10, MA20)` 或 `價格 * 0.97`

**V9 顯示規則（重要！）**：
- V9 = V7 + KD 金叉，所以 **V9 一定也是 V7**
- 如果股票同時通過 V7 + V9，在 V7 區塊顯示，標籤改為 `⟨V7 V9⟩` 或加 `KD✓`
- **不存在「V9 獨有」的情況**

範例：
```
─── V7 狙擊 ───

🎯 廣達 2382 $280 ⟨V7⟩RSI51
   💵278~280

🎯 聯茂 6213 $178 ⟨V7 V9⟩RSI55 KD✓
   💵175~178
```

**4. V8 量縮區塊**

V8 是獨立維度（看成交量縮），與 V4-V7 正交。

只通過 V8（不通過 V4/V5/V6/V6*/V7）的股票：

```
─── V8 量縮 ───
（空行）
🔋 {股名} {代號} ${價格} ⟨V8⟩
   連{n}天量縮｜站穩MA20
（空行）
```

**V8 emoji**：🔋（蓄勢待發）

**注意**：V8 目前是「實驗中」狀態，若沒有 V8 股票，不顯示此區塊。

---

## 🧪 測試驗證標準

### 執行測試

```bash
cd d:\claude-project\STOCK_HUNTER
python scan_all_versions.py
```

**⚠️ 重要**：
- ✅ **真實測試**：接 FinMind API，產生真實資料
- ❌ **不要「乾測試」**：不要用假資料或 mock
- ✅ **等待完成**：約 1-2 分鐘，耐心等待

### 成功標準

**1. 檔案產生**
```
✅ scan_result_all_versions.txt（完整報告）
✅ scan_result_v9_lite.txt（LINE 推送卡）
✅ data/raw/YYYY-MM-DD_HHMM_candidates.json
```

**2. 格式檢查**

對比 `scan_result_v9_lite.txt` 與 Zeabur 20:30 結果：
- ✅ 標題格式一致
- ✅ emoji 使用正確
- ✅ 版本標籤 `⟨全過⟩` `⟨V5 V6*⟩`（不是評分）
- ✅ V7 區塊使用 `─── V7 狙擊 ───`（不是 `━━━━━`）
- ✅ 價格資訊完整（進場/停損/停利）

**3. 邏輯檢查**
- ✅ V7 狙擊股有出現（如：廣達 2382）
- ✅ 豐泰 9910 有出現（不被評分篩選）
- ✅ 全過股排在前面

**4. 數量檢查**
```
V4: 3-5 檔
V5: 5-8 檔
V6: 2-4 檔
V6*: 3-6 檔
V7: 0-2 檔（看市況）
V8: 0-1 檔
V9: 0-1 檔
```

---

## ⚠️ 重要：不要直接複製 compare_versions_v7.py

> **這是最重要的原則！違反此原則會把舊的 bug 一起帶過來！**

### 為什麼不能直接複製？

**原因**：
1. **compare_versions_v7.py 已經修改過多次**
   - 歷經多次緊急修補
   - 可能包含過時的邏輯
   - 可能有隱藏的 bug

2. **複製會把錯誤也帶過來**
   - 舊的條件判斷可能有誤
   - 舊的格式化邏輯可能不完整
   - 舊的註解可能是錯的

3. **重構的目的就是從零開始**
   - 按照規格書的定義重新寫
   - 確保邏輯正確
   - 乾淨無歷史包袱

### 正確做法

✅ **參考但不複製**：

1. **讀取 compare_versions_v7.py**
   - 理解它的**邏輯結構**
   - 看懂它**想做什麼**
   - 但不要複製任何程式碼

2. **按照本規格書的偽代碼重新寫**
   - 參照 L814-989 的 `generate_v9_lite_card()` 偽代碼
   - 確保版本定義符合 L132-232
   - 確保輸出格式符合 L260-406

3. **參考 Zeabur 20:30 的輸出**
   - 這是**正確的格式範例**
   - 用它來驗證你的輸出
   - 確保分隔線、emoji、標籤一致

### 可複製的部分

**唯一可以複製的**：
- ATR 計算公式（數學公式不會錯）
- 基本的工具函數（如 `round()`, `min()`, `max()`）

**絕對不可複製的**：
- 版本判斷邏輯（可能過時）
- 格式化字串（可能不符合新格式）
- 篩選條件（可能有 bug）
- 主要的業務邏輯函數

### 示例對比

❌ **錯誤做法**：
```python
# 直接從 compare_versions_v7.py 複製 generate_lite_output() 函數
# 然後改個名字叫 generate_v9_lite_card()
# 這樣會把舊 bug 一起帶過來！
```

✅ **正確做法**：
```python
# 1. 讀取規格書 L814-989 的偽代碼
# 2. 理解每個步驟的目的
# 3. 從零開始寫，按照偽代碼的邏輯
# 4. 用 Zeabur 20:30 輸出驗證格式
```

### 檢查清單

**重構前問自己**：
- [ ] 我是在**重寫**還是在**複製**？
- [ ] 我的程式碼是基於**規格書**還是**舊檔案**？
- [ ] 我有參考**偽代碼** (L814-989) 嗎？
- [ ] 我有對比**Zeabur 輸出**嗎？

**如果答案是「複製」、「舊檔案」、「沒有」，請停止並重新開始！**

---

## ⚠️ 常見陷阱與誤解

### 1. 「乾測試」誤解

❌ **錯誤理解**：
```
使用者說「乾測試」→ Claude 以為是 dry run（模擬執行）
→ 使用假資料或 mock
→ 沒有接 API
```

✅ **正確理解**：
```
使用者說「乾測試」→ 意思是「做完直接測試」
→ 接真實 API
→ 產生真實結果
→ 驗證能用
```

### 2. 評分 vs 版本標籤

❌ **錯誤**：顯示 `⟨7分⟩` `⟨4分⟩`
✅ **正確**：顯示 `⟨全過⟩` `⟨V5 V6*⟩`

**評分只用於內部排序，不顯示給使用者。**

### 3. 評分篩選門檻

❌ **錯誤**：評分 < 3 分就不顯示
✅ **正確**：只要通過任一版本就顯示（不管評分）

**範例**：豐泰 9910 評分可能只有 2 分，但通過 V5/V6*，所以要顯示。

### 4. V7 遺漏

❌ **錯誤**：只遍歷 `v5_with_score`
✅ **正確**：遍歷 `all_stocks_with_score`（所有候選股）

### 5. subprocess 呼叫

❌ **錯誤**：
```python
subprocess.run(['python', 'scan_20260106.py'])
```

✅ **正確**：
```python
subprocess.run(
    ['python', str(scan_script)],
    check=True,
    capture_output=True,
    text=True,
    encoding='utf-8',
    errors='replace'  # Windows cp950 相容
)
```

### 6. 分隔線

❌ **錯誤**：
```
━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ V7/V8/V9 特殊股
━━━━━━━━━━━━━━━━━━━━━━━━━
```

✅ **正確**：
```
─── V7 狙擊 ───
```

### 7. V7 條件與 BASE 衝突的誤解

❌ **錯誤理解**：
```
V7 要求今日漲幅 -4%~0%
BASE 硬門檻是 -2%~5%
兩者衝突！V7 會選不到股票！
→ 認為這是 bug 需要修正
```

✅ **正確理解**：
```
V7 是從 candidates.json 的 stocks 篩選
candidates.json 已經被 BASE 過濾過了
所以 V7 實際能選到的範圍是 -2%~0%（兩者交集）
這是設計上的限制，不是 bug！
V7 找的是「小幅回檔」的股票
```

---

## 🆘 新 Claude 遇到問題時

**執行重構過程中遇到問題不要慌，按照這個流程處理**：

### 1. 先診斷問題類型

**語法錯誤 (SyntaxError)**：
- 檢查括號、引號是否配對
- 檢查縮排是否正確（Python 用 4 空格）
- 檢查是否少了冒號 `:`

**導入錯誤 (ImportError, ModuleNotFoundError)**：
- 檢查檔案頭部的 `import` 語句
- 確認所有用到的函數都有導入
- 參考規格書 L657-661（Gemini 3 補丁）

**變數未定義 (NameError)**：
- 檢查變數名稱拼寫
- 確認變數在使用前已定義
- 檢查是否在正確的作用域

**屬性錯誤 (AttributeError, KeyError)**：
- 檢查字典 key 是否存在（用 `.get()` 代替 `[]`）
- 檢查物件是否有該屬性
- 加入 `None` 檢查

**subprocess 執行錯誤**：
- 檢查是否使用 `sys.executable` 而非 `'python'`
- 檢查路徑是否正確（Windows 用 `\\` 或 `/`）
- 檢查 `encoding='utf-8', errors='replace'` 是否加入

### 2. 常見問題速查表

| 錯誤訊息 | 可能原因 | 解決方法 |
|---------|---------|---------|
| `NameError: name 'math' is not defined` | 忘記 `import math` | 在檔案頭部加入 `import math` |
| `KeyError: 'atr'` | 股票資料缺少 ATR 欄位 | 改用 `s.get('atr', price * 0.03)` |
| `FileNotFoundError: scan_20260106.py` | 路徑錯誤 | 用絕對路徑或 `os.path.join(SCRIPT_DIR, 'scan_20260106.py')` |
| `UnicodeEncodeError: 'cp950'` | Windows 編碼問題 | subprocess 加入 `encoding='utf-8', errors='replace'` |
| `TypeError: unsupported operand type(s)` | 變數類型錯誤（如 None + int） | 加入 `if value is not None:` 檢查 |
| `IndexError: list index out of range` | 串列為空 | 用 `if len(list) > 0:` 先檢查 |

### 3. Debug 步驟

**Step 1: 最小化問題範圍**
```python
# 在可能出錯的地方加入 print
print(f"Debug: s = {s}")
print(f"Debug: ticker = {s.get('ticker', 'N/A')}")
print(f"Debug: price = {s.get('price', 0)}")
```

**Step 2: 逐段測試**
```python
# 先測試函數定義是否正確
def generate_v9_lite_card(...):
    return "測試"

# 再測試能否讀取資料
def generate_v9_lite_card(...):
    print(f"候選股數量: {len(all_stocks_with_score)}")
    return "測試"

# 最後完整實作
```

**Step 3: 參考規格書偽代碼**
- 回到 L814-989，逐行對照
- 確認每個步驟都有實作
- 確認邏輯順序正確

### 4. 驗證修復是否成功

**修復後必須執行**：
```bash
# 1. 語法檢查
python -m py_compile scan_all_versions.py

# 2. 實際執行
python scan_all_versions.py

# 3. 檢查輸出
cat scan_result_v9_lite.txt | head -20
```

### 5. 何時向使用者求助

**以下情況請停止並詢問使用者**：
- ❌ 不確定版本定義是否正確
- ❌ 不確定輸出格式是否符合需求
- ❌ 修改超過 3 次仍無法解決
- ❌ 錯誤訊息看不懂（罕見錯誤）
- ❌ 需要修改規格書範圍外的檔案

**詢問格式**：
```
遇到問題：[簡述問題]
已嘗試：[列出嘗試過的方法]
錯誤訊息：[完整錯誤訊息]

請問：
A. [解決方案 A]
B. [解決方案 B]
C. 其他建議？
```

### 6. 緊急回滾

**如果問題無法解決且影響進度**：
```bash
# 立即從備份還原
cp BACKUP_20260126/scan_all_versions.py .

# 向使用者報告
echo "已回滾到備份版本，問題：[描述問題]"
```

---

## 🚫 嚴禁事項（新 Claude 必讀）

**以下是絕對不可做的事，違反任一項代表重構失敗：**

| # | 嚴禁事項 | 正確做法 |
|---|----------|----------|
| 1 | ❌ 用 mock 資料測試 | ✅ 接真實 FinMind API |
| 2 | ❌ 顯示評分數字給使用者（如 `⟨7分⟩`） | ✅ 顯示版本標籤（如 `⟨全過⟩`） |
| 3 | ❌ 用評分作為篩選門檻 | ✅ 只要通過任一版本就顯示 |
| 4 | ❌ 在沒備份的情況下修改檔案 | ✅ 先執行 Phase 0 備份 |
| 5 | ❌ 跳過驗證步驟直接說「完成了」 | ✅ 用工具執行驗證命令並截圖 |
| 6 | ❌ 只遍歷 `v5_with_score` 找 V7 | ✅ 遍歷 `all_stocks_with_score` |
| 7 | ❌ 忘記 V9 ⊂ V7（V9 一定也是 V7） | ✅ V9 在 V7 區塊顯示，標 `⟨V7 V9⟩` |
| 8 | ❌ 把 V8 only 放進主列表 | ✅ V8 only 在 `─── V8 量縮 ───` 區塊 |

---

## �🔙 備份計畫（執行前必做）

**⚠️ 執行 Phase 1 之前，必須先備份**：

**Linux/Mac**：
```bash
cd d:\claude-project\STOCK_HUNTER

# 建立備份目錄
mkdir -p BACKUP_20260126

# 備份關鍵檔案
cp scan_all_versions.py BACKUP_20260126/
cp compare_versions_v7.py BACKUP_20260126/
cp scheduler.py BACKUP_20260126/

# 驗證備份成功
ls -lh BACKUP_20260126/
```

**Windows PowerShell**：
```powershell
cd d:\claude-project\STOCK_HUNTER

# 建立備份目錄
New-Item -ItemType Directory -Path BACKUP_20260126 -Force

# 備份關鍵檔案
Copy-Item scan_all_versions.py BACKUP_20260126\
Copy-Item compare_versions_v7.py BACKUP_20260126\
Copy-Item scheduler.py BACKUP_20260126\

# 驗證備份成功
Get-ChildItem BACKUP_20260126
```

**如果改壞了，還原方法**：

**Linux/Mac**：
```bash
# 還原所有檔案
cp BACKUP_20260126/* .

# 或只還原特定檔案
cp BACKUP_20260126/scan_all_versions.py .
```

**Windows PowerShell**：
```powershell
# 還原所有檔案
Copy-Item BACKUP_20260126\* .

# 或只還原特定檔案
Copy-Item BACKUP_20260126\scan_all_versions.py .
```

---

## 📋 執行步驟（逐步檢查清單）

### Phase 0: 備份（必做）

- [ ] 0.1 建立 BACKUP_20260126 目錄
- [ ] 0.2 備份 scan_all_versions.py
- [ ] 0.3 備份 compare_versions_v7.py
- [ ] 0.4 備份 scheduler.py
- [ ] 0.5 驗證備份檔案存在

### Phase 1: 修改 scan_all_versions.py

- [ ] 1.1 重寫 `generate_v9_lite_card()` 函數
  - 參照 `compare_versions_v7.py` 的 `generate_lite_output()`
  - 版本標籤取代評分
  - 移除評分篩選門檻
  - V7 區塊用 `─── V7 狙擊 ───`

- [ ] 1.2 確認評分系統（10 分制）
  - 對所有候選股計算
  - 用於內部排序
  - 不用於篩選

- [ ] 1.3 確認 V7/V8/V9 邏輯不遺漏
  - 遍歷 `all_stocks_with_score`
  - V7 獨有股票單獨顯示

- [ ] 1.4 **檢查 Imports**（Gemini 3 補丁）
  - 確認 `scan_all_versions.py` 頭部包含所有必要 library
  - 特別注意：`import math`, `import json`, `import sys`, `import os`, `import subprocess`
  - 從 `compare_versions_v7.py` 複製函數時，一併複製該函數用到的 imports

- [ ] 1.5 **保留完整報告**（Gemini 3 補丁）
  - 確保 `scan_result_all_versions.txt` 的生成邏輯維持不變
  - 完整報告是 Debug 用的，**不可刪除或簡化**
  - 只重構 Lite 卡片 (`scan_result_v9_lite.txt`)

- [ ] 1.6 **子程序呼叫規範**（Gemini 3 補丁）
  - 在 `scan_all_versions.py` 內部呼叫 `scan_20260106.py` 時
  - **必須使用 `sys.executable`，嚴禁使用字串 `'python'`**
  - 範例：`subprocess.run([sys.executable, 'scan_20260106.py'], ...)`

### Phase 1.5: 最小可行測試 (MVT) - 建議執行

> **目的**：在完整測試前，先確認函數本身能正常運作，隔離問題是「函數邏輯」還是「資料/API」

**MVT-1: 測試函數定義**

```bash
# 確認語法正確，沒有 SyntaxError
python -m py_compile scan_all_versions.py
```

**預期結果**：無輸出（代表語法正確）

**如果失敗**：
- 檢查括號、引號配對
- 檢查縮排（4 空格）
- 檢查冒號 `:`

---

**MVT-2: 測試函數執行（用假資料）**

在 `scan_all_versions.py` 暫時加入測試程式碼：

```python
# 暫時加在檔案最後面（測試完要刪除）
if __name__ == '__main__':
    # 建立最小測試資料
    test_stock = {
        'ticker': '2330',
        'name': '台積電',
        'price': 600,
        'score': 7,
        'buy_days': 3,
        'inst_5day': 5000,
        'foreign_5day': 4000,
        'trust_5day': 1000,
        'revenue_yoy': 25.5,
        'atr': 18,
        'rsi': 55,
        'ma10': 590,
        'ma20': 580
    }

    all_stocks_with_score = [test_stock]
    v4_set = {'2330'}
    v5_set = {'2330'}
    v6_set = {'2330'}
    v6s_set = {'2330'}
    v7_set = set()
    v8_set = set()
    v9_set = set()
    date_str = '2026-01-26'

    # 測試函數
    result = generate_v9_lite_card(
        all_stocks_with_score,
        v4_set, v5_set, v6_set, v6s_set,
        v7_set, v8_set, v9_set,
        date_str
    )

    print("=== MVT 測試結果 ===")
    print(result)
    print("=== MVT 測試完成 ===")
```

**執行測試**：
```bash
python scan_all_versions.py
```

**預期結果**：
```
=== MVT 測試結果 ===
📊 2026-01-26 選股

🏆 台積電 2330 $600 ⟨全過⟩🐰
   外資連3買｜YoY+26%
   💵591~600｜🛡️564｜🎯636
=== MVT 測試完成 ===
```

**檢查項目**：
- [ ] 函數能執行，沒有 crash
- [ ] 輸出包含標題 `📊 2026-01-26 選股`
- [ ] 版本標籤是 `⟨全過⟩`，不是 `⟨7分⟩`
- [ ] emoji 使用正確（🏆 = 全過）
- [ ] 價格資訊完整（進場/停損/停利）

**如果失敗**：
- 檢查錯誤訊息（NameError, KeyError, etc.）
- 參考「🆘 新 Claude 遇到問題時」章節
- 逐步 debug（加入 print）

---

**MVT-3: 測試 V7 狙擊區塊**

修改測試資料，加入 V7 only 股票：

```python
    test_stock_v7 = {
        'ticker': '2382',
        'name': '廣達',
        'price': 280,
        'score': 3,
        'buy_days': 1,
        'inst_5day': 8000,
        'foreign_5day': 7000,
        'trust_5day': 1000,
        'revenue_yoy': 96.9,
        'atr': 8,
        'rsi': 51,
        'ma10': 278,
        'ma20': 275
    }

    all_stocks_with_score = [test_stock, test_stock_v7]
    v4_set = {'2330'}
    v5_set = {'2330'}
    v6_set = {'2330'}
    v6s_set = {'2330'}
    v7_set = {'2382'}  # V7 only
    v8_set = set()
    v9_set = set()
```

**預期結果**：
```
📊 2026-01-26 選股

🏆 台積電 2330 $600 ⟨全過⟩🐰
   ...

─── V7 狙擊 ───

🎯 廣達 2382 $280 ⟨V7⟩RSI51
   💵275~280
```

**檢查項目**：
- [ ] V7 區塊存在
- [ ] 分隔線是 `─── V7 狙擊 ───`（不是 `━━━━━`）
- [ ] V7 股票在獨立區塊，不在主列表

---

**MVT 完成後**：

1. **刪除測試程式碼**
   - 移除 `if __name__ == '__main__':` 及測試資料
   - 確認刪除乾淨（用 `grep "MVT 測試" scan_all_versions.py` 檢查）

2. **確認通過後才進入 Phase 2**
   - MVT 目的是確認函數邏輯正確
   - Phase 2 才接真實 API

---

### Phase 2: 測試

- [ ] 2.1 本地執行 `python scan_all_versions.py`
  - ✅ 接真實 API
  - ✅ 產生真實結果
  - ⏱️ 等待 1-2 分鐘

- [ ] 2.2 檢查輸出檔案
  - `scan_result_all_versions.txt` 存在
  - `scan_result_v9_lite.txt` 存在
  - `candidates.json` 存在

- [ ] 2.3 格式對比
  - 與 Zeabur 20:30 結果比較
  - emoji 正確
  - 版本標籤正確
  - 分隔線正確

- [ ] 2.4 邏輯驗證
  - V7 狙擊股出現
  - 豐泰 9910 出現
  - 全過股排前面

### Phase 3: 更新 scheduler.py

- [ ] 3.1 修改呼叫邏輯
  ```python
  # 改前
  subprocess.run([sys.executable, 'scan_20260106.py'])
  subprocess.run([sys.executable, 'compare_versions_v7.py', latest_candidate])

  # 改後
  subprocess.run([sys.executable, 'scan_all_versions.py'])
  ```

- [ ] 3.2 修改結果檔案路徑
  ```python
  # 改前
  result_file = 'scan_result_lite.txt'

  # 改後
  result_file = 'scan_result_v9_lite.txt'
  ```

- [ ] 3.3 移除 compare_versions_v7.py 呼叫

### Phase 4: Git 更新

- [ ] 4.1 Git commit
  ```bash
  git add scan_all_versions.py scheduler.py
  git commit -m "統一選股系統：格式統一 + 修復 V7 遺漏"
  git push
  ```

- [ ] 4.2 刪除舊檔案
  ```bash
  git rm compare_versions_v7.py
  git commit -m "移除 compare_versions_v7.py（功能已併入 scan_all_versions.py）"
  git push
  ```

### Phase 5: Zeabur 驗證

- [ ] 5.1 等待 Zeabur 部署完成

- [ ] 5.2 等待下次排程（20:30）

- [ ] 5.3 檢查 LINE 推送格式
  - 與本地結果一致
  - V7 狙擊股出現
  - 格式正確

- [ ] 5.4 如果 Zeabur 推送失敗
  - 檢查 Zeabur logs
  - 回報使用者
  - 必要時執行緊急回滾（見下方）

---

## 🚨 緊急回滾程序

**如果重構後出問題（Zeabur 推送失敗、格式錯誤等）**：

### 方法 1：Git 回滾（推薦）

```bash
# 查看最近 3 個 commit
git log --oneline -3

# 回滾到重構前的 commit
git reset --hard <重構前的commit-hash>

# 強制推送（覆蓋遠端）
git push --force
```

### 方法 2：備份還原

```bash
cd d:\claude-project\STOCK_HUNTER

# 從備份還原所有檔案
cp BACKUP_20260126/scan_all_versions.py .
cp BACKUP_20260126/compare_versions_v7.py .
cp BACKUP_20260126/scheduler.py .

# commit 還原
git add .
git commit -m "回滾：還原重構前版本"
git push
```

### 方法 3：手動修復

```bash
# 如果只是小問題，直接用 compare_versions_v7.py
# 修改 scheduler.py 改回呼叫舊版

# Line 56-61 改回：
compare_result = subprocess.run(
    [sys.executable, os.path.join(SCRIPT_DIR, 'compare_versions_v7.py'), latest_candidate],
    capture_output=True,
    text=True,
    timeout=60
)

# Line 75 改回：
result_file = os.path.join(SCRIPT_DIR, 'scan_result_lite.txt')
```

**回滾後通知使用者**：
```
已緊急回滾到重構前版本。
原因：[說明問題]
Zeabur 將在下次部署後恢復正常。
```

---

## 🔧 程式碼範例

### generate_v9_lite_card() 偽代碼

```python
def generate_v9_lite_card(all_stocks_with_score, v4_set, v5_set, v6_set, v6s_set, v7_set, v8_set, v9_set, date_str):
    """產生 V9 小卡（LINE 推送用）"""

    # 建立版本標籤函數（主列表用，只含 V4/V5/V6/V6*/V8）
    # 注意：V7/V9 在專屬區塊顯示，不在主列表
    def get_version_label(ticker):
        versions = []
        if ticker in v4_set: versions.append('V4')
        if ticker in v5_set: versions.append('V5')
        if ticker in v6_set: versions.append('V6')
        if ticker in v6s_set: versions.append('V6*')
        if ticker in v8_set: versions.append('V8')  # V8 也算進主列表

        if len(versions) >= 4:
            return '⟨全過⟩'
        elif len(versions) > 0:
            return '⟨' + ' '.join(versions) + '⟩'
        else:
            return ''

    # 合併所有通過版本的股票
    all_tickers = {}
    for s in all_stocks_with_score:
        ticker = s['ticker']
        # 只要通過任一版本就加入（不管評分）
        if ticker in v4_set or ticker in v5_set or ticker in v6_set or ticker in v6s_set or ticker in v7_set or ticker in v8_set or ticker in v9_set:
            all_tickers[ticker] = s

    # 計算版本數（用於排序）
    def count_versions(s):
        ticker = s['ticker']
        count = 0
        if ticker in v4_set: count += 1
        if ticker in v5_set: count += 1
        if ticker in v6_set: count += 1
        if ticker in v6s_set: count += 1
        if ticker in v7_set: count += 1
        if ticker in v8_set: count += 1  # V8 也算
        # V9 不單獨計算（V9 ⊂ V7，已經在 v7_set 計算過）
        return count

    # 排序：版本數 > 評分 > 法人買超
    sorted_stocks = sorted(
        all_tickers.values(),
        key=lambda x: (count_versions(x), x.get('score', 0), x.get('inst_5day', 0)),
        reverse=True
    )

    lines = []
    lines.append(f"📊 {date_str} 選股")
    lines.append("")

    # 主列表：順勢股（通過 V4/V5/V6/V6* 或 V8）
    for s in sorted_stocks:
        ticker = s['ticker']

        # V7 only 跳過，稍後在 V7 區塊顯示
        is_v7_only = (ticker in v7_set and
                      ticker not in v4_set and
                      ticker not in v5_set and
                      ticker not in v6_set and
                      ticker not in v6s_set and
                      ticker not in v8_set)  # 也要排除 V8
        if is_v7_only:
            continue

        # V8 only 也跳過，稍後在 V8 區塊顯示
        is_v8_only = (ticker in v8_set and
                      ticker not in v4_set and
                      ticker not in v5_set and
                      ticker not in v6_set and
                      ticker not in v6s_set and
                      ticker not in v7_set)
        if is_v8_only:
            continue

        # 格式化輸出
        name = s.get('name', '')[:4]
        price = s['price']
        label = get_version_label(ticker)

        # emoji（依版本數）
        vcnt = count_versions(s)
        emoji = '🏆' if vcnt >= 4 else ('⭐' if vcnt >= 2 else '📋')

        # 法人資訊
        buy_days = s.get('buy_days', 0)
        inst_leader = '外資' if s.get('foreign_5day', 0) > s.get('trust_5day', 0) else '投信'
        inst_info = f"{inst_leader}連{buy_days}買" if buy_days >= 2 else f"法人+{s.get('inst_5day', 0)}張"

        # 題材（YoY）
        yoy = s.get('revenue_yoy', 0)
        news = f"YoY+{yoy:.0f}%" if yoy > 10 else (f"YoY+{yoy:.1f}%" if yoy > 0 else "")

        # ATR 計算
        atr = s.get('atr', price * 0.03)
        entry_low = round(price - 0.5 * atr)
        stop = round(price - 2 * atr)
        target = round(price + 2 * atr)

        # 股性標籤（🐰兔子=活潑, 🐢烏龜=穩健）
        atr_pct = (atr / price * 100) if price > 0 else 0
        personality = '🐰' if atr_pct > 3 else '🐢'

        # 輸出
        lines.append(f"{emoji} {name} {ticker} ${price:.0f} {label}{personality}")
        if news:
            lines.append(f"   {inst_info}｜{news}")
        else:
            lines.append(f"   {inst_info}")
        lines.append(f"   💵{entry_low}~{price:.0f}｜🛡️{stop}｜🎯{target}")
        lines.append("")

    # V7 狙擊區塊（含 V9 標示）
    v7_only_stocks = [s for s in all_stocks_with_score
                      if s['ticker'] in v7_set and
                      s['ticker'] not in v4_set and
                      s['ticker'] not in v5_set and
                      s['ticker'] not in v6_set and
                      s['ticker'] not in v6s_set and
                      s['ticker'] not in v8_set]  # 排除 V8

    if v7_only_stocks:
        lines.append("─── V7 狙擊 ───")
        lines.append("")

        for s in v7_only_stocks:
            name = s.get('name', '')[:4]
            ticker = s['ticker']
            price = s['price']
            rsi = s.get('rsi', 50)
            ma10 = s.get('ma10', 0)
            ma20 = s.get('ma20', 0)
            support = min(ma10, ma20) if ma10 > 0 and ma20 > 0 else price * 0.97

            # V9 標示：V9 = V7 + KD 金叉，所以 V9 一定也是 V7
            if ticker in v9_set:
                label = "⟨V7 V9⟩"  # 同時通過 V7 和 V9
                kd_mark = " KD✓"
            else:
                label = "⟨V7⟩"
                kd_mark = ""

            lines.append(f"🎯 {name} {ticker} ${price:.0f} {label}RSI{rsi:.0f}{kd_mark}")
            lines.append(f"   💵{support:.0f}~{price:.0f}")
            lines.append("")

    # V8 量縮區塊（獨立維度）
    v8_only_stocks = [s for s in all_stocks_with_score
                      if s['ticker'] in v8_set and
                      s['ticker'] not in v4_set and
                      s['ticker'] not in v5_set and
                      s['ticker'] not in v6_set and
                      s['ticker'] not in v6s_set and
                      s['ticker'] not in v7_set]

    if v8_only_stocks:
        lines.append("─── V8 量縮 ───")
        lines.append("")

        for s in v8_only_stocks:
            name = s.get('name', '')[:4]
            ticker = s['ticker']
            price = s['price']
            # V8 特有資訊：連續幾天站穩 MA20 且量縮
            volume_shrink_days = s.get('volume_shrink_days', 3)

            lines.append(f"🔋 {name} {ticker} ${price:.0f} ⟨V8⟩")
            lines.append(f"   連{volume_shrink_days}天量縮｜站穩MA20")
            lines.append("")

    return '\n'.join(lines)
```

---

## 📞 使用者確認事項

**在執行前，請使用者確認**：

1. ✅ 評分系統保持 10 分制？（含投信加分）
2. ✅ 顯示用版本標籤 `⟨全過⟩`，不顯示評分？
3. ✅ 移除評分篩選門檻（評分 0 分也顯示）？
4. ✅ V7 區塊用 `─── V7 狙擊 ───`？
5. ✅ 刪除 `compare_versions_v7.py`？

**如果使用者說「GO」或「執行」，代表全部確認，開始執行。**

---

## 🔒 防失憶驗證機制

**⚠️ 重要：避免「以為做了但實際沒做」**

### 執行過程中，每完成一個 Phase 必須：

**Phase 1 完成後**：
```bash
# 驗證：generate_v9_lite_card() 是否真的改了
grep -n "def generate_v9_lite_card" scan_all_versions.py
grep -n "⟨全過⟩" scan_all_versions.py
grep -n "─── V7 狙擊 ───" scan_all_versions.py

# 必須看到：
# - 函數存在
# - 有 "⟨全過⟩" 字串
# - 有 "─── V7 狙擊 ───" 字串
```

**Phase 2 完成後**：
```bash
# 驗證：檔案真的產生了
ls -lh scan_result_v9_lite.txt
ls -lh scan_result_all_versions.txt
ls -lh data/raw/*_candidates.json

# 驗證：內容正確
head -20 scan_result_v9_lite.txt

# 必須看到：
# - 檔案存在且有內容 (> 0 bytes)
# - 第一行是 "📊 YYYY-MM-DD 選股"
# - 有 ⟨全過⟩ 或 ⟨V5 V6*⟩ 標籤
# - 有 "─── V7 狙擊 ───" (如果有 V7 股票)
```

**Phase 3 完成後**：
```bash
# 驗證：scheduler.py 真的改了
grep -n "scan_all_versions.py" scheduler.py
grep -n "scan_result_v9_lite.txt" scheduler.py
grep -n "compare_versions_v7.py" scheduler.py

# 必須看到：
# - 有 scan_all_versions.py 呼叫
# - 有 scan_result_v9_lite.txt 路徑
# - 沒有 compare_versions_v7.py 呼叫
```

**Phase 4 完成後**：
```bash
# 驗證：Git commit 真的 push 了
git log --oneline -3
git status

# 必須看到：
# - 最新 commit 包含 "統一選股系統" 字樣
# - working tree clean（沒有未 commit 的檔案）
```

### 最終驗證清單（全部打勾才算完成）

**檔案變更**：
- [ ] scan_all_versions.py 已修改（generate_v9_lite_card 函數）
- [ ] scheduler.py 已修改（呼叫 scan_all_versions.py）
- [ ] compare_versions_v7.py 已刪除（git rm）

**測試結果**：
- [ ] scan_result_v9_lite.txt 產生成功
- [ ] 格式與 Zeabur 20:30 一致（版本標籤、分隔線）
- [ ] V7 狙擊股出現（如：廣達 2382）
- [ ] 豐泰 9910 出現（不被評分篩選）

**Git 狀態**：
- [ ] 已 commit（git log 看得到）
- [ ] 已 push（git status 顯示 clean）
- [ ] 分支是 main/master

**輸出驗證**：
```bash
# 執行這個命令，截圖給使用者
cat scan_result_v9_lite.txt | head -30

# 使用者會看到實際輸出，確認格式正確
```

### Claude 自我檢查（防止幻覺）

**每完成一個 Phase，Claude 必須**：
1. 用 `Read` 工具讀取剛修改的檔案
2. 用 `Bash` 執行驗證命令
3. 截圖輸出給使用者確認
4. **不能只說「我已經改好了」，必須用工具驗證**

**如果工具回傳錯誤（如：檔案不存在、格式不對）**：
- ❌ 不能忽略
- ✅ 必須修正後重新驗證
- ✅ 向使用者報告問題

---

## 🚀 周日重構執行流程（給新 Claude 看）

**使用者會這樣開始**：
```
使用者：「@REFACTOR_SPEC.md 按照這個規格書執行重構」
```

**新 Claude 的第一步**：
1. 用 `Read` 工具讀取 `d:\claude-project\STOCK_HUNTER\REFACTOR_SPEC.md`
2. 閱讀完整規格書
3. 問使用者：「我已讀完規格書，確認要執行重構嗎？」
4. 使用者回答：「GO」

**然後按照 Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 執行**

**每完成一個 Phase**：
- 執行該 Phase 的驗證命令
- 用 `Bash` 工具顯示驗證結果
- 向使用者報告：「Phase X 完成，驗證通過」

**最後**：
- 執行「最終驗證清單」
- 輸出 `cat scan_result_v9_lite.txt | head -30` 給使用者確認
- 等使用者說「確認無誤」才算完成

---

## 📝 變更記錄

| 日期 | 版本 | 變更內容 |
|------|------|---------|
| 2026-01-24 02:15 | v1.5 | 新增三大補充：(1) 不要複製 compare_versions_v7.py 警告、(2) 新 Claude 遇到問題時處理流程、(3) 最小可行測試 (MVT) |
| 2026-01-24 01:34 | v1.4 | 加入 Gemini 3 補丁：Imports 檢查、保留完整報告、sys.executable 規範 |
| 2026-01-24 01:17 | v1.3 | 新增 V7 vs BASE 誤解說明、修正 count_versions()、偽代碼加入🐰🐢 |
| 2026-01-24 01:07 | v1.2 | 補強 V8 區塊、V9 顯示規則、嚴禁事項清單、Windows PowerShell 語法、格式對照表 |
| 2026-01-23 23:30 | v1.1 | 新增防失憶驗證機制、周日執行流程 |
| 2026-01-23 | v1.0 | 初版規格書 |

---

**檔案位置**：`d:\claude-project\STOCK_HUNTER\REFACTOR_SPEC.md`

**下次執行時**：
1. 新開 Claude Code session
2. 第一句話：`@REFACTOR_SPEC.md 按照這個規格書執行重構`
3. 等待 Claude 讀完規格書並確認
4. 說「GO」開始執行
