
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from FinMind.data import DataLoader
from src.config import FINMIND_TOKENS

class FinMindFetcher:
    def __init__(self):
        self.token_index = 0
        self.tokens = FINMIND_TOKENS
        
    def get_token(self):
        return self.tokens[self.token_index % len(self.tokens)]
        
    def rotate_token(self):
        self.token_index += 1
        num = (self.token_index % len(self.tokens)) + 1
        print(f"[TOKEN] Limit reached. Rotating to Token #{num}")
        time.sleep(1) # Cool down
        
    def fetch_with_retry(self, func, *args, **kwargs):
        """通用的重試機制裝飾器"""
        max_retries = len(self.tokens)
        
        for attempt in range(max_retries):
            try:
                dl = DataLoader()
                dl.login_by_token(api_token=self.get_token())
                return func(dl, *args, **kwargs)
                
            except Exception as e:
                error_msg = str(e).lower()
                is_rate_limit = ('429' in error_msg or 'rate limit' in error_msg)
                
                if is_rate_limit and attempt < max_retries - 1:
                    self.rotate_token()
                    continue
                
                if attempt == max_retries - 1:
                    print(f"[ERROR] API failed after {max_retries} attempts: {e}")
                    raise e
        return None

    def get_daily_snapshot(self, date_str=None):
        """抓取今日收盤價 (批次)"""
        def _fetch(dl):
            target_date = date_str if date_str else datetime.now().strftime('%Y-%m-%d')
            # 嘗試抓取今日資料
            # 若今日是假日或收盤前，可能無資料，邏輯由上層處理日期判斷
            return dl.taiwan_stock_daily(
                start_date=target_date,
                end_date=target_date
            )
        return self.fetch_with_retry(_fetch)
        
    def get_history_batch(self, days=20):
        """
        批次抓取全市場歷史資料 (最近 N 天)
        用於計算 MA, RSI, 漲幅等
        """
        def _fetch(dl):
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            # 全市場抓取 (stock_id='')
            # 注意：FinMind batch API 可能有延遲，需注意
            return dl.taiwan_stock_daily(
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )
        return self.fetch_with_retry(_fetch)

    def get_institutional_data(self, days=10):
        """批次抓取法人資料"""
        def _fetch(dl):
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            return dl.taiwan_stock_institutional_investors(
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )
        return self.fetch_with_retry(_fetch)
        
    def get_pe_data(self):
        """
        從證交所 API 抓取本益比
        """
        try:
            date_str = datetime.now().strftime('%Y%m%d')
            url = f'https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d?date={date_str}&response=json'
            
            # 簡單重試
            for _ in range(3):
                res = requests.get(url, timeout=10)
                if res.status_code == 200:
                    data = res.json()
                    if data.get('stat') == 'OK':
                        return self._parse_twse_pe(data)
                time.sleep(2)
                
            return {}
        except Exception as e:
            print(f"[ERROR] TWSE PE fetch failed: {e}")
            return {}

    def _parse_twse_pe(self, data):
        """解析證交所 PE 資料"""
        # 格式: ["2330", "台積電", "24.5", ...]
        # 欄位依據 BWIBBU_d 變動，通常 index 0=代號, 2=本益比
        pe_map = {}
        for row in data.get('data', []):
            try:
                ticker = row[0]
                pe_str = row[4] # 第5欄通常是本益比，需確認 API 回傳
                # BWIBBU_d: 證券代號,證券名稱,殖利率,股利年度,本益比,股價淨值比,財報年/季
                # 0:Ticker, 1:Name, 2:Yield, 3:Year, 4:PE, 5:PB, 6:Fiscal
                
                # 處理 '-' 或異常值
                if pe_str == '-' or not pe_str:
                    continue
                pe = float(pe_str.replace(',', ''))
                pe_map[ticker] = pe
            except:
                continue
        return pe_map
        
    def get_revenue_batch(self, tickers):
        """
        [Monthly Job] 逐檔抓取營收資料
        因為沒有 Batch API，必須一個一個抓
        """
        results = {}
        count = 0
        total = len(tickers)
        
        print(f"[FETCHER] Starting sequential revenue fetch for {total} stocks...")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=400) # 抓一年多算 YoY
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        for ticker in tickers:
            try:
                def _fetch(dl):
                    return dl.taiwan_stock_month_revenue(
                        stock_id=ticker,
                        start_date=start_str,
                        end_date=end_str
                    )
                df = self.fetch_with_retry(_fetch)
                if df is not None and not df.empty:
                    results[ticker] = df
                    
                count += 1
                if count % 10 == 0:
                    print(f"   Progress: {count}/{total}")
                    time.sleep(0.5) # Avoid strict rate limit
                    
            except Exception as e:
                print(f"   [ERROR] Failed for {ticker}: {e}")
                
        return results

    def get_financial_batch(self):
        """批次抓取財報 (Gross Margin, Operating Margin)"""
        def _fetch(dl):
            # 抓取最近一季
            # 簡化邏輯：直接抓最近 4 個月範圍的季報
            # FinMind API 支援 start_date='2024Q3' 格式
            
            # 推算最近季度
            now = datetime.now()
            # 簡單推算：現在是 1月 -> 去年 Q3 or Q4
            year = now.year
            q = (now.month - 1) // 3
            if q == 0: # 1,2,3月 -> 去年 Q4 (還沒出) -> 去年 Q3
                target_q = f"{year-1}Q3"
            else:
                target_q = f"{year}Q{q}"
                
            return dl.taiwan_stock_financial_statement(
                stock_id='', # All
                start_date=target_q
            )
        return self.fetch_with_retry(_fetch)
