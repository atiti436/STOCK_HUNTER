# GitHub Actions 自動選股推送設定教學

## 📋 功能說明

每天台灣晚上 9 點自動執行選股，並透過 Line BOT 推送結果到你的 Line。

## 🔧 設定步驟

### 1. 確認 ZEABUR Line BOT 已部署

你的 Line BOT 應該已經在 ZEABUR 上運行，網址類似：
```
https://your-app.zeabur.app
```

### 2. 更新 ZEABUR 上的 Line BOT

需要將最新的 `stock_hunter_v3.py` 部署到 ZEABUR（包含新增的 `/push_scan_result` API）

**方法 A：透過 Git 推送**
```bash
cd d:\claude-project\STOCK_HUNTER
git add stock_hunter_v3.py
git commit -m "新增 Line BOT 推送 API"
git push
```

**方法 B：ZEABUR 自動部署**
- 如果你的 ZEABUR 已連結 GitHub，推送後會自動部署

### 3. 設定 GitHub Secrets

前往你的 GitHub 專案：
1. 點選 **Settings** → **Secrets and variables** → **Actions**
2. 點選 **New repository secret**
3. 新增以下 Secret：

| Name | Value | 說明 |
|------|-------|------|
| `LINEBOT_URL` | `https://your-app.zeabur.app` | 你的 ZEABUR Line BOT 網址 |

⚠️ **注意**：網址結尾不要加 `/`

### 4. 測試手動觸發

1. 前往 GitHub 專案 → **Actions** 頁籤
2. 點選左側 **Daily Stock Screening**
3. 點選右側 **Run workflow** → **Run workflow**
4. 等待執行完成（約 1-2 分鐘）
5. 檢查你的 Line 是否收到推送

### 5. 確認定時任務

設定完成後，GitHub Actions 會：
- **每天晚上 9 點**（台北時間）自動執行
- 週一到週五執行（週末休市不執行）
- 你也可以隨時手動觸發

## 📊 運作流程

```
GitHub Actions (每天 21:00)
  ↓
執行 scan_v3.py (選股)
  ↓
產生 scan_result_v3.txt
  ↓
執行 scripts/push_to_linebot.py (讀取結果)
  ↓
POST 到 ZEABUR Line BOT /push_scan_result
  ↓
Line BOT 推送訊息到你的 Line
```

## 🔍 疑難排解

### 問題 1：Line 沒收到訊息

**檢查項目**：
1. GitHub Actions 是否執行成功？（前往 Actions 頁籤查看）
2. `LINEBOT_URL` Secret 是否設定正確？
3. ZEABUR Line BOT 是否正常運行？（訪問網址檢查）

**測試方法**：
```bash
# 本地測試推送腳本
cd d:\claude-project\STOCK_HUNTER
set LINEBOT_URL=https://your-app.zeabur.app
python scripts/push_to_linebot.py
```

### 問題 2：GitHub Actions 執行失敗

查看 Actions 執行記錄，常見錯誤：
- FinMind API 暫時無法連線 → 等待下次執行
- `LINEBOT_URL` 未設定 → 檢查 GitHub Secrets

### 問題 3：ZEABUR Line BOT 502 錯誤

可能原因：
- ZEABUR 服務暫時重啟
- Line BOT 程式碼有錯誤

解決方法：
- 檢查 ZEABUR 部署記錄
- 查看 ZEABUR 執行 logs

## 📝 維護建議

### 每週檢查

1. 前往 GitHub Actions 查看執行記錄
2. 確認每天都有成功執行
3. 如果連續失敗，檢查 FinMind API 或 ZEABUR 狀態

### 調整執行時間

修改 `.github/workflows/daily_update.yml` 中的 cron 時間：

```yaml
schedule:
  # 台灣晚上 8 點 (UTC 12:00)
  - cron: '0 12 * * 1-5'
```

Cron 時間計算：
- 台灣時間 - 8 小時 = UTC 時間
- 例如：21:00 → 13:00 UTC

## ✅ 設定完成檢查清單

- [ ] ZEABUR Line BOT 已更新（包含 `/push_scan_result` API）
- [ ] GitHub Secret `LINEBOT_URL` 已設定
- [ ] 手動觸發測試成功
- [ ] Line 收到測試訊息
- [ ] 確認定時任務設定正確

---

最後更新：2025-12-31
