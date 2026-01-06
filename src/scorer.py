
# 評分系統模組 (v4.0 邏輯)

def calculate_score(stock_info, inst_data, ma20):
    """
    計算總分 (0-7 分)
    
    參數:
        stock_info: {price, volume, change_pct, avg_volume, ...}
        inst_data: 法人資料 list
        ma20: 月線價格
        
    回傳: (score, reasons_list)
    """
    score = 0
    reasons = []
    
    price = stock_info.get('price', 0)
    change_pct = stock_info.get('change_pct', 0)
    volume = stock_info.get('volume', 0)
    avg_vol = stock_info.get('avg_volume', 0)
    
    # === 1. 籌碼面 (最高 4 分) ===
    # 計算 5 日買超
    buy_5day = sum(d['total'] for d in inst_data[:5]) if inst_data else 0
    
    # [基礎分] 有買超
    if buy_5day > 0:
        score += 1
        reasons.append("法人買超")
        
    # [力道分] 
    if buy_5day > 5000:
        score += 2
        reasons.append(f"強力買超({buy_5day//1000}K)")
    elif buy_5day > 1000:
        score += 1
        reasons.append(f"中度買超({buy_5day//1000}K)")
        
    # [時機分] 剛買 1-3 天
    # 這裡計算「最近 5 天有幾天買超」
    buy_days_cnt = sum(1 for d in inst_data[:5] if d['total'] > 0)
    if 1 <= buy_days_cnt <= 3:
        score += 1
        reasons.append(f"剛買{buy_days_cnt}天")
        
    # === 2. 動能面 (最高 2 分) ===
    
    # [量能] 量比價先
    if avg_vol > 0 and volume > avg_vol:
        score += 1
        reasons.append("量增")
        
    # [漲幅] 剛起漲 (0-4%)
    if 0 < change_pct <= 4:
        score += 1
        reasons.append("剛起漲")
        
    # === 3. 安全面 (最高 1 分) ===
    
    # [乖離] 離月線不遠 (< 8%)
    if ma20 and ma20 > 0:
        bias = (price - ma20) / ma20 * 100
        if bias < 8:
            score += 1
            reasons.append("位階安全")
            
    return score, reasons

def determine_inst_leader(inst_data):
    """判斷誰是主力 (外資 vs 投信)"""
    if not inst_data or len(inst_data) < 5:
        return "無"
        
    recent = inst_data[:5]
    foreign = sum(d['foreign'] for d in recent)
    trust = sum(d['trust'] for d in recent)
    
    if foreign <= 0 and trust <= 0:
        return "無"
        
    if trust > foreign * 1.5:
        return "投信"
    elif foreign > trust * 1.5:
        return "外資"
    else:
        return "土洋"
