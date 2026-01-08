#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zeabur Cron Job 入口
每日 20:30 自動執行掃描 + 推送 LINE

設定方式：
1. Zeabur 專案 → Settings → Cron Jobs
2. 新增 Cron: 30 12 * * 1-5 (UTC 12:30 = 台灣 20:30，週一到週五)
3. Command: python zeabur_cron.py

環境變數需求：
- FINMIND_TOKEN: FinMind API Token
- LINEBOT_URL: Zeabur LINE Bot URL (例如 https://xxx.zeabur.app)
"""

import os
import sys
import subprocess
from datetime import datetime

def log(msg):
    """帶時間戳的 log"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {msg}", flush=True)

def check_env():
    """檢查必要環境變數"""
    required = ['LINEBOT_URL']
    missing = [var for var in required if not os.environ.get(var)]
    
    if missing:
        log(f"❌ 缺少環境變數: {', '.join(missing)}")
        return False
    
    log("✅ 環境變數檢查通過")
    return True

def run_scan():
    """執行選股掃描"""
    log("🔍 開始執行選股掃描...")
    
    try:
        result = subprocess.run(
            [sys.executable, 'scan_20260106.py'],
            capture_output=True,
            text=True,
            timeout=300  # 5 分鐘超時
        )
        
        if result.returncode == 0:
            log("✅ 掃描完成")
            # 顯示最後幾行輸出
            lines = result.stdout.strip().split('\n')
            for line in lines[-5:]:
                log(f"   {line}")
            return True
        else:
            log(f"❌ 掃描失敗 (exit code: {result.returncode})")
            log(f"   錯誤: {result.stderr[:500]}")
            return False
            
    except subprocess.TimeoutExpired:
        log("❌ 掃描超時 (>5分鐘)")
        return False
    except Exception as e:
        log(f"❌ 掃描異常: {e}")
        return False

def run_push():
    """推送結果到 LINE"""
    log("📤 開始推送到 LINE...")
    
    try:
        result = subprocess.run(
            [sys.executable, 'scripts/push_to_linebot.py'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            log("✅ LINE 推送成功")
            return True
        else:
            log(f"❌ LINE 推送失敗")
            log(f"   {result.stderr[:200]}")
            return False
            
    except Exception as e:
        log(f"❌ 推送異常: {e}")
        return False

def main():
    log("=" * 50)
    log("🚀 Zeabur Cron Job 啟動")
    log("=" * 50)
    
    # 檢查環境變數
    if not check_env():
        sys.exit(1)
    
    # 執行掃描
    if not run_scan():
        log("⚠️ 掃描失敗，嘗試推送錯誤訊息...")
        # 即使掃描失敗也可以推送錯誤通知
    
    # 推送結果
    success = run_push()
    
    log("=" * 50)
    if success:
        log("🎉 Cron Job 完成")
    else:
        log("⚠️ Cron Job 部分失敗")
    log("=" * 50)
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
