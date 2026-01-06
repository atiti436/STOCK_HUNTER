
# 篩選邏輯模組
from src.config import SCREENING_CRITERIA as CFG

class StockFilter:
    @staticmethod
    def is_excluded(ticker):
        """排除金融、營建、ETF"""
        if ticker.startswith(('28', '58')): return True # 金融
        if ticker.startswith('25'): return True # 營建
        if ticker.startswith('00'): return True # ETF
        return False
        
    @staticmethod
    def check_basic_criteria(ticker, price, volume, pe):
        """
        基本面初篩 (價格、PE、成交量)
        回傳: (Passed, Reason)
        """
        if StockFilter.is_excluded(ticker):
            return False, "Excluded Category"
            
        if not (CFG['price_min'] <= price <= CFG['price_max']):
            return False, f"Price {price} out of range"
            
        if volume < CFG['volume_min']:
            return False, f"Low Volume {volume}"
            
        # PE 為 None 時視為通過 (可能虧損或 API 沒抓到，留給後面財報檢查或人工判斷)
        # 但 SPEC 說 PE < 35，若無 PE 通常是不賺錢
        if pe is not None and pe > CFG['pe_max']:
            return False, f"High PE {pe}"
            
        return True, ""
        
    @staticmethod
    def check_technical_criteria(price, change_pct, ma20, rsi, vol_5day_avg, volume):
        """技術面篩選"""
        # 1. 股價必須在月線之上 (趨勢多頭)
        if ma20 and price < ma20:
            return False, "Price < MA20"
            
        # 2. RSI 不過熱
        if rsi > CFG['rsi_max']:
            return False, f"RSI Overheated {rsi}"
            
        # 3. 量能放大 (今日量 > 5日均量)
        if vol_5day_avg and volume <= vol_5day_avg:
            return False, "Volume shrinking"
            
        # 4. 漲幅限制 (不要追漲太多的) - 從 SPEC 看是 5日 < 10%
        # 但 scan_v4.py 也有單日漲幅限制 -2~5%
        if not (-2 <= change_pct <= 5):
             # 再次確認 SPEC: 今日漲幅 -2% ~ +5%
             return False, f"Daily change {change_pct}% out of range"
             
        return True, ""
        
    @staticmethod
    def check_chip_criteria(inst_data):
        """
        籌碼面篩選 (法人動向)
        inst_data: [{date, total, ...}, ...] 最新在前
        """
        if not inst_data or len(inst_data) < 5:
            return False, "Insufficient Inst Data"
            
        # 1. 5日累積買超
        buy_5day = sum(d['total'] for d in inst_data[:5])
        if buy_5day < CFG['inst_5day_min']:
            return False, f"Inst 5-day buy {buy_5day} too low"
            
        # 2. 連續買超 >= 2 天 (最新的 2 天)
        # scan_v4.py 邏輯: 5天內買超天數? 不，SPEC 說連續買超 >= 2
        # 我們嚴格遵守 SPEC: 連續買超 >= 2
        if inst_data[0]['total'] <= 0 or inst_data[1]['total'] <= 0:
            return False, "Not consecutive buying (2 days)"
            
        # 3. 1月累積 > -10000 (避免大逃殺)
        # 這裡假設 inst_data 夠長，若不夠就用全部
        buy_month = sum(d['total'] for d in inst_data[:20]) 
        if buy_month < CFG['inst_1month_min']:
            return False, "Inst month heavy sell"
            
        return True, ""

    @staticmethod
    def check_revenue_criteria(revenue_data):
        """
        營收篩選
        revenue_data: {'yoy': 12.5, ...}
        """
        if not revenue_data:
            return False, "No revenue data"
            
        yoy = revenue_data.get('yoy', 0)
        if yoy <= 0:
            return False, f"Revenue YoY {yoy}% <= 0"
            
        return True, ""
