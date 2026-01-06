
import pickle
import os
from datetime import datetime

class DataCache:
    """通用資料快取類別"""
    
    @staticmethod
    def save(data, filepath):
        """儲存資料到 pickle"""
        try:
            cache_obj = {
                'data': data,
                'timestamp': datetime.now(),
                'version': '1.0'
            }
            # 確保目錄存在
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, 'wb') as f:
                pickle.dump(cache_obj, f)
            return True
        except Exception as e:
            print(f"[CACHE] Save failed: {e}")
            return False

    @staticmethod
    def load(filepath, max_age_days=None):
        """
        讀取 pickle 資料
        max_age_days: 如果不為 None，檢查快取是否過期
        """
        if not os.path.exists(filepath):
            return None
            
        try:
            with open(filepath, 'rb') as f:
                cache_obj = pickle.load(f)
                
            if max_age_days is not None:
                cache_time = cache_obj.get('timestamp')
                if not cache_time:
                    return None
                    
                age = (datetime.now() - cache_time).days
                if age > max_age_days:
                    print(f"[CACHE] Cache expired (age: {age} days > {max_age_days})")
                    return None
                    
            return cache_obj.get('data')
            
        except Exception as e:
            print(f"[CACHE] Load failed: {e}")
            return None

class RevenueCache:
    """營收資料快取 (月度更新)"""
    def __init__(self, filepath):
        self.filepath = filepath
        
    def save(self, data):
        return DataCache.save(data, self.filepath)
        
    def load(self):
        # 營收資料效期較長，設為 35 天 (每月更新)
        return DataCache.load(self.filepath, max_age_days=35)
