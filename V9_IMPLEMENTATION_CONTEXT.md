# V9 Implementation Context (for AI Resume)

> [!CAUTION]
> **🚨 版本定義不一致！** 詳見 [`HANDOFF_V7_ISSUE.md`](./HANDOFF_V7_ISSUE.md)
> - `scan_20260106.py` 的 V7 = 量縮蓄勢
> - `scan_all_versions.py` 的 V7 = Daily Dip
> - 用戶尚未決定如何統一

## 任務目標
整理 V7/V8/V9 版本定義，確保人機理解一致

## 版本定義（2026-01-23 確認）

### V7 Daily Dip（回檔狙擊）✅ 已驗證
```python
# 找「強勢股回檔到支撐」
- 今日跌 -4%~0%           # 必須有跌
- 接近 MA10/MA20（乖離<2%） # 回到均線支撐
- 均線多頭 MA10 > MA20
- 法人5日 > 500
- RSI < 70
- 5日漲幅 -5%~5%          # 橫盤或小回檔
```
**實績**：1/16、1/20 各選出 3 檔，包含聯茂連續出現 ✅

### V8 量縮蓄勢（實驗中）📝 待驗證
```python
# 找「多頭整理縮量」
1. 連續 3 天 Close > MA20   # 站穩均線
2. 連續 3 天 Volume < MA(Volume,20) * 0.8  # 量縮整理
```
**問題**：聯茂無法被選到（量沒有連續縮 3 天）

### V9 = V7 + KD 確認
```python
# V7 通過後，加上 KD 觸發
- K > D AND K_prev <= D_prev  # 剛金叉
- K >= 80 → 排除（過熱）
- K <= 50 → Ideal（低檔翻揚）
```


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
