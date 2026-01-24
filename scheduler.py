#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定時排程器 - 使用 APScheduler 每日執行掃描推送
整合到 line_relay.py 一起啟動
"""

import os
import subprocess
import sys
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# 取得腳本所在目錄（解決 cwd 問題）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def log(msg):
    """帶時間戳的 log"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[SCHEDULER] [{timestamp}] {msg}", flush=True)

def run_daily_scan():
    """每日掃描任務"""
    log("=" * 50)
    log("🚀 開始執行每日掃描任務")
    log("=" * 50)
    
    try:
        # Step 1: 執行完整掃描（含所有版本）
        log("🔍 執行 scan_all_versions.py...")
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPT_DIR, 'scan_all_versions.py')],
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0:
            log("✅ 掃描完成")
            lines = result.stdout.strip().split('\n')
            for line in lines[-3:]:
                log(f"   {line}")
        else:
            log(f"❌ 掃描失敗: {result.stderr[:200]}")
            return
        
        # Step 2: 推送到 LINE（改用 HTTP API）
        log("📤 推送到 LINE...")
        try:
            import requests

            # 讀取 V9 lite 格式
            result_file = os.path.join(SCRIPT_DIR, 'scan_result_v9_lite.txt')
            if not os.path.exists(result_file):
                log("❌ 找不到 scan_result_v9_lite.txt")
                return
            
            if os.path.exists(result_file):
                with open(result_file, 'r', encoding='utf-8') as f:
                    message = f.read()
                
                linebot_url = os.environ.get('LINEBOT_URL', 'http://localhost:8080')
                response = requests.post(
                    f"{linebot_url}/push_scan_result",
                    json={"message": message},
                    timeout=30
                )
                
                if response.status_code == 200:
                    log("✅ LINE 推送成功")
                else:
                    log(f"❌ LINE 推送失敗: {response.status_code}")
            else:
                log(f"❌ 找不到結果檔案: {result_file}")
        except Exception as e:
            log(f"❌ LINE 推送異常: {e}")
        
        log("🎉 每日任務完成！")
        log("=" * 50)
        
    except subprocess.TimeoutExpired:
        log("❌ 任務超時")
    except Exception as e:
        log(f"❌ 任務異常: {e}")

def start_scheduler():
    """啟動排程器"""
    scheduler = BackgroundScheduler(timezone='Asia/Taipei')
    
    # 每天 20:30 執行（台灣時間）
    scheduler.add_job(
        run_daily_scan,
        trigger=CronTrigger(hour=20, minute=30, day_of_week='mon-fri'),
        id='daily_stock_scan',
        name='每日股票掃描',
        replace_existing=True
    )
    
    scheduler.start()
    log("✅ 排程器已啟動")
    log("⏰ 每日 20:30（週一到週五）執行掃描")
    
    # 列出所有任務
    for job in scheduler.get_jobs():
        log(f"   任務: {job.name}, 下次執行: {job.next_run_time}")
    
    return scheduler

if __name__ == '__main__':
    # 測試用：直接執行會立即跑一次
    log("🧪 測試模式：立即執行一次掃描任務")
    run_daily_scan()
