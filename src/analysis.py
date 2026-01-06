
# 技術指標計算模組
# 包含 RSI, MA, 乖離率, 停損停利計算

def calculate_rsi(prices, period=14):
    """
    計算 RSI (相對強弱指標)
    prices: 收盤價列表 (最新在前) [100, 99, ...]
    """
    if len(prices) < period + 1:
        return 50  # 資料不足
    
    # 反轉讓舊的在前計算
    prices_rev = list(reversed(prices[:period + 1]))
    gains = []
    losses = []
    
    for i in range(1, len(prices_rev)):
        change = prices_rev[i] - prices_rev[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
            
    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0
    
    if avg_loss == 0:
        return 100
        
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 1)

def calculate_ma(prices, days=20):
    """計算移動平均 MA"""
    if len(prices) < days:
        return None
    return sum(prices[:days]) / days

def calculate_deviation(price, ma):
    """計算乖離率 (%)"""
    if not ma or ma == 0:
        return 0
    return (price - ma) / ma * 100

def calculate_stop_loss(close_price, ma10, ma20):
    """
    動態停損策略 (v3.4/v4.0 規格)
    - 乖離 > 5% (噴出) -> 守 MA10
    - 乖離 < 5% (起漲) -> 守 MA20
    - 底線 -> -7%
    """
    if not ma20:
        return round(close_price * 0.93, 2), "底線-7%"
        
    bias = calculate_deviation(close_price, ma20)
    
    if bias > 5:
        # 噴出股，守緊一點
        tech_stop = ma10 if ma10 else close_price * 0.95
        note = "守MA10"
    else:
        # 起漲股，給點空間
        tech_stop = ma20
        note = "守MA20"
        
    hard_stop = close_price * 0.93
    final_stop = max(tech_stop, hard_stop)
    
    return round(final_stop, 2), note

def calculate_batch_profit(price):
    """分批停利計算"""
    return {
        'batch_1': {'price': round(price * 1.04, 1), 'pct': 4, 'note': '保本先跑'},
        'batch_2': {'price': round(price * 1.07, 1), 'pct': 7, 'note': '主要目標'},
        'batch_3': {'price': round(price * 1.10, 1), 'pct': 10, 'note': '賺更多'},
    }

def calculate_5day_stats(prices_data):
    """
    計算 5 日漲幅與均量
    prices_data: [(date, close, volume), ...]
    """
    if len(prices_data) < 5:
        return None, None
        
    latest_close = prices_data[0][1]
    prev_5_close = prices_data[4][1]
    
    if prev_5_close == 0:
        change_pct = 0
    else:
        change_pct = ((latest_close - prev_5_close) / prev_5_close) * 100
        
    volumes = [p[2] for p in prices_data[:5]]
    avg_vol = sum(volumes) / len(volumes)
    
    return round(change_pct, 2), round(avg_vol, 0)
