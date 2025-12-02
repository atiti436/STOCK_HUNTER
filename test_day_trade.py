import sys
import os

# Add current directory to path to import stock_hunter_v2
sys.path.append(os.getcwd())

from stock_hunter_v2 import calculate_cdp, analyze_day_trade_potential

def test_calculate_cdp():
    print("Testing calculate_cdp...")
    # Test case: High=100, Low=90, Close=95
    # CDP = (100+90+190)/4 = 95
    # AH = 95 + 10 = 105
    # NH = 190 - 90 = 100
    # NL = 190 - 100 = 90
    # AL = 95 - 10 = 85
    
    result = calculate_cdp(100, 90, 95)
    
    assert result['CDP'] == 95.0, f"Expected CDP 95.0, got {result['CDP']}"
    assert result['AH'] == 105.0, f"Expected AH 105.0, got {result['AH']}"
    assert result['NH'] == 100.0, f"Expected NH 100.0, got {result['NH']}"
    assert result['NL'] == 90.0, f"Expected NL 90.0, got {result['NL']}"
    assert result['AL'] == 85.0, f"Expected AL 85.0, got {result['AL']}"
    
    print("✅ calculate_cdp passed!")

def test_analyze_day_trade_potential():
    print("Testing analyze_day_trade_potential...")
    
    # Case 1: Low volume (Ratio 1.5)
    stock_data_low_vol = {
        'price': 100,
        'today_volume': 1500,
        'avg_volume_5d': 1000
    }
    result = analyze_day_trade_potential(stock_data_low_vol)
    assert result is None, "Expected None for low volume"
    
    # Case 2: High volume (Ratio 2.5)
    stock_data_high_vol = {
        'price': 100,
        'today_volume': 2500,
        'avg_volume_5d': 1000
    }
    result = analyze_day_trade_potential(stock_data_high_vol)
    
    assert result is not None, "Expected result for high volume"
    assert result['is_candidate'] is True
    assert result['volume_ratio'] == 2.5
    assert 'cdp' in result
    
    print("✅ analyze_day_trade_potential passed!")

if __name__ == "__main__":
    try:
        test_calculate_cdp()
        test_analyze_day_trade_potential()
        print("\n🎉 All tests passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
