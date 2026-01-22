# V9 Implementation Context (for AI Resume)

## 任務目標
在 `scan_20260106.py` 實作 V9 MVP 版本

## 核心規範（來自 CC3.txt）

### V7 極簡版（量縮蓄勢）
```python
# 只有 2 個條件
1. 連續 3 天 Close > MA20
2. 連續 3 天 Volume < MA(Volume,20) * 0.8
```

### V9 嚴格版（KD 觸發）
```python
# Trigger（抓第一天金叉）
K > D AND K_prev <= D_prev AND K > K_prev

# Position Filter
K >= 80 → 排除
K <= 50 → Ideal
50 < K < 80 → OK
```

### KD 規格
- 標準 KD(9,3,3) 公式
- RSV 方法（9日）

## 漏斗流程
```
Universe (~1700 檔)
  ↓ BASE（現有硬門檻）
After BASE (50-100 檔估)
  ↓ V7 篩選
After V7 (? 檔)
  ↓ V9 篩選
After V9 (? 檔)
Excluded HighK (? 檔)
```

## 輸出要求

### candidates.json 股票欄位
```json
{
  "ticker": "2330",
  "K_value": 45.2,
  "D_value": 42.8,
  "K_zone": "Ideal",
  ...
}
```

### candidates.json 檔案層級
```json
{
  "v9_spec": "MVP-20260122",
  "kd_version": "KD(9,3,3)",
  "stocks": [...]
}
```

### Console 漏斗計數
```
Universe: 1700
After BASE: 65
After V7: 12
After V9: 5
Excluded HighK: 3
```

## 關鍵檔案
- **修改**：`d:\claude-project\STOCK_HUNTER\scan_20260106.py`
- **測試**：執行後檢查 `data/raw/YYYY-MM-DD_HHMM_candidates.json`

## 注意事項
1. ✅ BASE = 現有硬門檻（不改）
2. ✅ 在候選池產生後、存檔前計算 KD
3. ✅ V7/V9 都是 Optional（這版只驗證核心邏輯）
4. ✅ 需要抓 9 天歷史資料計算 KD
5. ✅ K >= 80 必須排除（嚴格）

## 驗證清單
- [ ] 漏斗計數正確印出
- [ ] candidates.json 有 K_value, D_value, K_zone
- [ ] V9 結果無 K >= 80 股票
- [ ] 版本標記正確
