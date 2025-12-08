#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Manpan 情報網 v4.1 - MVP 版本
整合 FEEDBACK1 + FEEDBACK2 + 專業審查建議
適用：Google Colab / 本地 Python 執行

作者：Claude Code
版本：v4.1 Final
日期：2025-12-01
"""

import random
import sys
from datetime import datetime, timedelta

# 修正 Windows 編碼問題
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ============================================================
# 配置區（所有閾值集中管理）
# ============================================================
CONFIG = {
    # Guardian 1: 市場熔斷
    "ma60_period": 60,
    "limit_down_threshold": 100,

    # Guardian 2: 流動性
    "min_turnover": 50_000_000,  # 5000 萬台幣
    "volume_spike_ratio": 5,

    # Guardian 3: 籌碼
    "foreign_consecutive_days": 3,
    "foreign_buy_ratio": 0.05,  # 5%
    "trust_consecutive_days": 3,
    "trust_buy_ratio": 0.03,    # 3%

    # Guardian 4: 技術
    "bias_threshold_bull": 0.30,  # 多頭允許 30%
    "bias_threshold_bear": 0.15,  # 空頭/盤整 15%
    "news_negative_threshold": -0.3,

    # Guardian 5: 出場
    "stop_loss": -0.08,           # -8%
    "holding_days_min": 3,
    "trailing_profit_trigger": 0.10,
    "trailing_stop_ratio": 0.10,
    "take_profit": 0.30,          # +30%

    # Guardian 6: 倉位
    "high_confidence_allocation": 0.15,   # 15%
    "medium_confidence_allocation": 0.08, # 8%
    "high_confidence_score": 3,
}

# ============================================================
# Mock Data 生成
# ============================================================

def generate_market_data(scenario="bull"):
    """
    生成市場數據

    Args:
        scenario: "bull" (多頭) 或 "bear" (空頭)

    Returns:
        dict: 市場數據
    """
    if scenario == "bull":
        return {
            "index_name": "台灣加權指數 (TAIEX)",
            "current_price": 17500,
            "ma60": 17200,
            "limit_down_count": 35,  # 正常範圍
            "date": datetime.now().strftime("%Y-%m-%d"),
            "scenario": "多頭格局"
        }
    else:  # bear
        return {
            "index_name": "台灣加權指數 (TAIEX)",
            "current_price": 16800,
            "ma60": 17200,
            "limit_down_count": 120,  # 恐慌
            "date": datetime.now().strftime("%Y-%m-%d"),
            "scenario": "空頭格局（觸發熔斷）"
        }


def generate_stock_candidates():
    """
    生成 5 支測試股票
    涵蓋所有測試情境：完美、流動性陷阱、過熱、籌碼背離、爆量

    Returns:
        list: 股票清單
    """
    stocks = [
        # Stock A - 完美買點
        {
            "id": "2330",
            "name": "台積電",
            "price": 580,
            "ma20": 565,
            "ma60": 550,
            "ma120": 520,
            "avg_volume_5d": 25000,
            "avg_turnover_5d": 145_000_000,  # 1.45 億（Pass）
            "today_volume": 28000,
            "news_score": 0.7,  # 正面新聞
            "chips": {
                "foreign": {
                    "buy_days": 5,
                    "today_amount": 150_000_000,
                    "today_ratio": 0.08
                },
                "trust": {
                    "buy_days": 4,
                    "today_amount": 50_000_000,
                    "today_ratio": 0.03
                },
                "dealer": {
                    "buy_days": 1,
                    "today_amount": 10_000_000,
                    "today_ratio": 0.01
                }
            },
            "total_turnover_today": 1_800_000_000
        },

        # Stock B - 流動性陷阱
        {
            "id": "9999",
            "name": "殭屍股",
            "price": 15,
            "ma20": 14.5,
            "ma60": 14,
            "ma120": 13,
            "avg_volume_5d": 200,
            "avg_turnover_5d": 3_000_000,  # 300 萬（Fail）
            "today_volume": 250,
            "news_score": 0.2,
            "chips": {
                "foreign": {"buy_days": 2, "today_amount": 500_000, "today_ratio": 0.04},
                "trust": {"buy_days": 1, "today_amount": 200_000, "today_ratio": 0.02},
                "dealer": {"buy_days": 0, "today_amount": -100_000, "today_ratio": -0.01}
            },
            "total_turnover_today": 3_500_000
        },

        # Stock C - 技術過熱
        {
            "id": "3324",
            "name": "雙鴻",
            "price": 720,
            "ma20": 680,
            "ma60": 520,
            "ma120": 450,
            "avg_volume_5d": 8000,
            "avg_turnover_5d": 80_000_000,
            "today_volume": 9000,
            "news_score": 0.5,
            "chips": {
                "foreign": {"buy_days": 3, "today_amount": 30_000_000, "today_ratio": 0.06},
                "trust": {"buy_days": 3, "today_amount": 15_000_000, "today_ratio": 0.03},
                "dealer": {"buy_days": 2, "today_amount": 5_000_000, "today_ratio": 0.01}
            },
            "total_turnover_today": 500_000_000
        },

        # Stock D - 籌碼背離
        {
            "id": "2603",
            "name": "長榮",
            "price": 150,
            "ma20": 148,
            "ma60": 145,
            "ma120": 140,
            "avg_volume_5d": 15000,
            "avg_turnover_5d": 200_000_000,
            "today_volume": 16000,
            "news_score": -0.1,
            "chips": {
                "foreign": {"buy_days": 0, "today_amount": -50_000_000, "today_ratio": -0.05},
                "trust": {"buy_days": 0, "today_amount": -20_000_000, "today_ratio": -0.02},
                "dealer": {"buy_days": 2, "today_amount": 5_000_000, "today_ratio": 0.01}
            },
            "total_turnover_today": 1_000_000_000
        },

        # Stock E - 爆量警示
        {
            "id": "2454",
            "name": "聯發科",
            "price": 1020,
            "ma20": 1000,
            "ma60": 980,
            "ma120": 950,
            "avg_volume_5d": 5000,
            "avg_turnover_5d": 51_000_000,
            "today_volume": 28000,  # 量比 5.6x
            "news_score": 0.3,
            "chips": {
                "foreign": {"buy_days": 1, "today_amount": 20_000_000, "today_ratio": 0.03},
                "trust": {"buy_days": 0, "today_amount": -5_000_000, "today_ratio": -0.01},
                "dealer": {"buy_days": 1, "today_amount": 3_000_000, "today_ratio": 0.01}
            },
            "total_turnover_today": 600_000_000
        }
    ]

    return stocks


def generate_portfolio():
    """
    生成 5 筆持倉數據
    涵蓋所有出場情境：續抱、硬停損、移動停利、技術停損、獲利了結

    Returns:
        list: 持倉清單
    """
    base_date = datetime.now()

    holdings = [
        # Holding A - 獲利續抱
        {
            "stock_id": "2317",
            "stock_name": "鴻海",
            "cost_price": 100,
            "current_price": 115,
            "buy_date": (base_date - timedelta(days=21)).strftime("%Y-%m-%d"),
            "holding_days": 21,
            "max_price_since_buy": 120,
            "ma20": 110
        },

        # Holding B - 硬停損
        {
            "stock_id": "2603",
            "stock_name": "長榮",
            "cost_price": 100,
            "current_price": 91,
            "buy_date": (base_date - timedelta(days=6)).strftime("%Y-%m-%d"),
            "holding_days": 6,
            "max_price_since_buy": 102,
            "ma20": 95
        },

        # Holding C - 移動停利
        {
            "stock_id": "2330",
            "stock_name": "台積電",
            "cost_price": 500,
            "current_price": 560,
            "buy_date": (base_date - timedelta(days=47)).strftime("%Y-%m-%d"),
            "holding_days": 47,
            "max_price_since_buy": 630,
            "ma20": 580
        },

        # Holding D - 技術停損
        {
            "stock_id": "2454",
            "stock_name": "聯發科",
            "cost_price": 1000,
            "current_price": 970,
            "buy_date": (base_date - timedelta(days=11)).strftime("%Y-%m-%d"),
            "holding_days": 11,
            "max_price_since_buy": 1010,
            "ma20": 980
        },

        # Holding E - 獲利了結
        {
            "stock_id": "3711",
            "stock_name": "日月光",
            "cost_price": 100,
            "current_price": 135,
            "buy_date": (base_date - timedelta(days=91)).strftime("%Y-%m-%d"),
            "holding_days": 91,
            "max_price_since_buy": 138,
            "ma20": 130
        }
    ]

    return holdings


# ============================================================
# 六大守護者
# ============================================================

def guardian_1_market_check(market_data):
    """
    Guardian 1: 市場熔斷檢查

    條件：
    1. 指數 < MA60（空頭格局）
    2. 跌停家數 > 100（恐慌氣氛）

    任一條件成立 → 觸發熔斷

    Args:
        market_data: 市場數據

    Returns:
        dict: {"status": "SAFE"/"DANGER", "action": str, "reason": str}
    """
    below_ma60 = market_data['current_price'] < market_data['ma60']
    panic_mode = market_data['limit_down_count'] > CONFIG['limit_down_threshold']

    if below_ma60 or panic_mode:
        reason_parts = []
        if below_ma60:
            diff = ((market_data['current_price'] - market_data['ma60']) / market_data['ma60'] * 100)
            reason_parts.append(f"指數 < MA60 ({diff:+.1f}%)")
        if panic_mode:
            reason_parts.append(f"跌停 {market_data['limit_down_count']} 支 (> {CONFIG['limit_down_threshold']})")

        return {
            "status": "DANGER",
            "action": "HALT_ALL_BUYING",
            "reason": " & ".join(reason_parts)
        }

    diff = ((market_data['current_price'] - market_data['ma60']) / market_data['ma60'] * 100)
    return {
        "status": "SAFE",
        "action": "ALLOW_BUYING",
        "reason": f"指數 > MA60 ({diff:+.1f}%), 跌停 {market_data['limit_down_count']} 支"
    }


def guardian_2_liquidity_check(stock):
    """
    Guardian 2: 流動性檢查

    使用成交金額（而非成交量）避免誤判

    Args:
        stock: 股票數據

    Returns:
        dict: {"pass": bool, "reason": str, "warning": str (可選)}
    """
    turnover_pass = stock['avg_turnover_5d'] >= CONFIG['min_turnover']

    # 爆量偵測
    volume_ratio = stock['today_volume'] / stock['avg_volume_5d'] if stock['avg_volume_5d'] > 0 else 0
    abnormal_spike = volume_ratio > CONFIG['volume_spike_ratio']

    if not turnover_pass:
        return {
            "pass": False,
            "reason": f"流動性不足（日均 {stock['avg_turnover_5d']/1e6:.1f}M < 50M）",
            "warning": None
        }

    result = {
        "pass": True,
        "reason": f"日均成交額 {stock['avg_turnover_5d']/1e6:.0f}M",
        "warning": None
    }

    if abnormal_spike:
        result["warning"] = f"⚠️ 異常爆量（量比 {volume_ratio:.1f}x）"

    return result


def guardian_3_chips_consensus(stock):
    """
    Guardian 3: 籌碼共識評分

    評分範圍：-3 到 +3

    加分：
    - 外資連 3 日買超 + 佔比 > 5%：+2
    - 投信連 3 日買超 + 佔比 > 3%：+2
    - 三大法人當日同步買超：+1

    扣分：
    - 外資投信雙賣超（佔比 > 3%/2%）：-3

    Args:
        stock: 股票數據

    Returns:
        dict: {"score": int, "level": str, "reasons": list}
    """
    foreign = stock['chips']['foreign']
    trust = stock['chips']['trust']
    dealer = stock['chips']['dealer']

    score = 0
    reasons = []

    # === 加分條件 ===

    # 1. 外資強力買超
    if foreign['buy_days'] >= CONFIG['foreign_consecutive_days'] and \
       foreign['today_ratio'] > CONFIG['foreign_buy_ratio']:
        score += 2
        reasons.append(f"外資連 {foreign['buy_days']} 日買超 (佔比 {foreign['today_ratio']:.1%})")

    # 2. 投信強力買超
    if trust['buy_days'] >= CONFIG['trust_consecutive_days'] and \
       trust['today_ratio'] > CONFIG['trust_buy_ratio']:
        score += 2
        reasons.append(f"投信連 {trust['buy_days']} 日買超 (佔比 {trust['today_ratio']:.1%})")

    # 3. 三大法人同步買超
    all_buying = (foreign['today_ratio'] > 0 and
                  trust['today_ratio'] > 0 and
                  dealer['today_ratio'] > 0)
    if all_buying:
        score += 1
        reasons.append("三大法人同步買超")

    # === 扣分條件 ===

    # 4. 外資投信雙賣超
    both_selling = (foreign['today_ratio'] < -CONFIG['foreign_buy_ratio'] and
                    trust['today_ratio'] < -CONFIG['trust_buy_ratio'])
    if both_selling:
        score -= 3
        reasons.append(f"外資投信雙賣超（警示）")

    # === 評級 ===
    if score >= 3:
        level = "STRONG_CONSENSUS"
    elif score > 0:
        level = "MODERATE"
    elif score == 0:
        level = "NEUTRAL"
    else:
        level = "AVOID"

    return {
        "score": score,
        "level": level,
        "reasons": reasons if reasons else ["無明顯法人動向"]
    }


def guardian_4_technical_check(stock):
    """
    Guardian 4: 技術面 + 新聞情緒檢查

    乖離率基準：MA60（比 MA20 穩定）
    多頭格局允許較高乖離（30%）
    空頭/盤整嚴格（15%）

    Args:
        stock: 股票數據

    Returns:
        dict: {"pass": bool, "reason": str, "bias": float, "trend": str}
    """
    # 計算乖離率（vs MA60）
    bias_60 = (stock['price'] - stock['ma60']) / stock['ma60']

    # 判斷多空格局
    is_bullish = (stock['ma20'] > stock['ma60'] > stock['ma120'])

    # 過熱判斷
    if is_bullish:
        threshold = CONFIG['bias_threshold_bull']
        trend = "多頭"
    else:
        threshold = CONFIG['bias_threshold_bear']
        trend = "空頭/盤整"

    overheated = bias_60 > threshold

    # 新聞情緒檢查（MVP 用 Mock）
    news_negative = stock.get('news_score', 0) < CONFIG['news_negative_threshold']

    # 回傳結果
    if overheated:
        return {
            "pass": False,
            "reason": f"技術過熱（乖離 {bias_60:.1%} > {threshold:.0%}）",
            "bias": bias_60,
            "trend": trend
        }

    if news_negative:
        return {
            "pass": False,
            "reason": f"負面新聞（分數 {stock['news_score']:.2f}）",
            "bias": bias_60,
            "trend": trend
        }

    return {
        "pass": True,
        "reason": f"乖離率 {bias_60:.1%}（{trend}格局）",
        "bias": bias_60,
        "trend": trend
    }


def guardian_5_exit_strategy(position, market_status):
    """
    Guardian 5: 出場策略（五層檢查）

    優先級：
    1. 大盤熔斷
    2. 硬停損（持有 >= 3 天，-8%）
    3. 技術停損（破 MA20 且虧損）
    4. 移動停利（獲利 > 10% 後，從高點回落 > 10%）
    5. 獲利了結（+30%）

    Args:
        position: 持倉數據
        market_status: "SAFE" 或 "DANGER"

    Returns:
        dict: {"action": "SELL"/"HOLD", "reason": str, "type": str}
    """
    current = position['current_price']
    cost = position['cost_price']
    max_high = position['max_price_since_buy']
    holding_days = position['holding_days']

    # 計算指標
    pnl_ratio = (current - cost) / cost
    drawdown_from_peak = (max_high - current) / max_high if max_high > 0 else 0
    highest_profit = (max_high - cost) / cost if cost > 0 else 0

    # === 第 1 層：大盤熔斷 ===
    if market_status == "DANGER":
        return {
            "action": "SELL",
            "reason": f"🚨 大盤熔斷，強制出場（損益 {pnl_ratio:+.1%}）",
            "type": "MARKET_CRASH",
            "pnl": pnl_ratio
        }

    # === 第 2 層：硬停損 ===
    if holding_days >= CONFIG['holding_days_min'] and pnl_ratio <= CONFIG['stop_loss']:
        return {
            "action": "SELL",
            "reason": f"✂️ 硬停損 {CONFIG['stop_loss']:.0%}（目前 {pnl_ratio:+.1%}）",
            "type": "STOP_LOSS",
            "pnl": pnl_ratio
        }

    # === 第 3 層：技術停損 ===
    if current < position['ma20'] and pnl_ratio < 0:
        return {
            "action": "SELL",
            "reason": f"📉 跌破月線且虧損（{pnl_ratio:+.1%}）",
            "type": "TECH_BREAK",
            "pnl": pnl_ratio
        }

    # === 第 4 層：移動停利 ===
    if highest_profit > CONFIG['trailing_profit_trigger'] and \
       drawdown_from_peak > CONFIG['trailing_stop_ratio']:
        return {
            "action": "SELL",
            "reason": f"📊 移動停利（高點 {max_high} → 現價 {current}，回落 {drawdown_from_peak:.1%}）",
            "type": "TRAILING_STOP",
            "pnl": pnl_ratio
        }

    # === 第 5 層：獲利了結 ===
    if pnl_ratio >= CONFIG['take_profit']:
        return {
            "action": "SELL",
            "reason": f"🎯 獲利達標 +{CONFIG['take_profit']:.0%}（目前 {pnl_ratio:+.1%}）",
            "type": "TAKE_PROFIT",
            "pnl": pnl_ratio
        }

    # === 續抱 ===
    return {
        "action": "HOLD",
        "reason": f"持有中（損益 {pnl_ratio:+.1%}，高點 {max_high}）",
        "type": "HOLD",
        "pnl": pnl_ratio
    }


def guardian_6_position_sizing(chips_score):
    """
    Guardian 6: 倉位配置

    根據籌碼評分決定買入比例

    Args:
        chips_score: Guardian 3 的評分

    Returns:
        dict: {"allocation": float, "confidence": str, "description": str}
    """
    if chips_score >= CONFIG['high_confidence_score']:
        return {
            "allocation": CONFIG['high_confidence_allocation'],
            "confidence": "HIGH",
            "description": "🔥 強力買入"
        }
    elif chips_score > 0:
        return {
            "allocation": CONFIG['medium_confidence_allocation'],
            "confidence": "MEDIUM",
            "description": "⚡ 適度買入"
        }
    else:
        return {
            "allocation": 0,
            "confidence": "NONE",
            "description": "🚫 不交易"
        }


# ============================================================
# 主流程
# ============================================================

def analyze_watchlist(stocks, market_status):
    """
    分析候選股票清單

    執行順序：Guardian 2 → 4 → 3 → 6

    Args:
        stocks: 股票清單
        market_status: "SAFE" 或 "DANGER"

    Returns:
        list: 分析結果
    """
    results = []

    for stock in stocks:
        result = {
            "stock": stock,
            "liquidity": None,
            "technical": None,
            "chips": None,
            "position": None,
            "final_decision": None
        }

        # Guardian 2: 流動性
        liquidity = guardian_2_liquidity_check(stock)
        result['liquidity'] = liquidity

        if not liquidity['pass']:
            result['final_decision'] = {
                "action": "REJECT",
                "reason": liquidity['reason'],
                "stage": "LIQUIDITY"
            }
            results.append(result)
            continue

        # Guardian 4: 技術面
        technical = guardian_4_technical_check(stock)
        result['technical'] = technical

        if not technical['pass']:
            result['final_decision'] = {
                "action": "REJECT",
                "reason": technical['reason'],
                "stage": "TECHNICAL"
            }
            results.append(result)
            continue

        # Guardian 3: 籌碼
        chips = guardian_3_chips_consensus(stock)
        result['chips'] = chips

        # Guardian 6: 倉位
        position = guardian_6_position_sizing(chips['score'])
        result['position'] = position

        if position['allocation'] == 0:
            result['final_decision'] = {
                "action": "REJECT",
                "reason": f"籌碼評分不足（{chips['score']} 分）",
                "stage": "CHIPS"
            }
        else:
            result['final_decision'] = {
                "action": "BUY",
                "reason": f"{position['description']}（評分 {chips['score']} 分）",
                "allocation": position['allocation'],
                "stage": "APPROVED"
            }

        results.append(result)

    return results


def check_portfolio(holdings, market_status):
    """
    檢查持倉，執行 Guardian 5

    Args:
        holdings: 持倉清單
        market_status: "SAFE" 或 "DANGER"

    Returns:
        list: 出場動作清單
    """
    actions = []

    for holding in holdings:
        action = guardian_5_exit_strategy(holding, market_status)
        actions.append({
            "holding": holding,
            "action": action
        })

    return actions


# ============================================================
# 輸出報告
# ============================================================

def print_report(market_data, market_check, analysis_results, portfolio_actions):
    """
    輸出完整分析報告

    Args:
        market_data: 市場數據
        market_check: Guardian 1 結果
        analysis_results: 候選股票分析結果
        portfolio_actions: 持倉動作清單
    """
    print("=" * 60)
    print("📊 Manpan 情報網 v4.1 - 每日分析報告")
    print("=" * 60)
    print(f"執行時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"測試場景：{market_data['scenario']}")
    print("=" * 60)
    print()

    # === 市場狀態 ===
    print("🌍 市場狀態檢查 (Guardian 1)")
    print("-" * 60)

    status_icon = "🟢" if market_check['status'] == "SAFE" else "🔴"
    status_text = "安全 (SAFE)" if market_check['status'] == "SAFE" else "危險 (DANGER)"

    print(f"狀態：{status_icon} {status_text}")
    print(f"指數：{market_data['index_name']} {market_data['current_price']:,} 點")
    print(f"季線：{market_data['ma60']:,} 點")
    print(f"跌停：{market_data['limit_down_count']} 支")
    print(f"結論：{market_check['reason']}")

    if market_check['status'] == "DANGER":
        print("⚠️  【系統熔斷】停止所有買入操作")
    else:
        print("✅ 允許買入操作")

    print()
    print("=" * 60)

    # === 候選股票分析 ===
    if market_check['status'] == "SAFE":
        print("🔍 候選股票分析 (Guardian 2-4-3-6)")
        print("-" * 60)
        print()

        for idx, result in enumerate(analysis_results, 1):
            stock = result['stock']
            print(f"[{idx}] {stock['id']} {stock['name']}")
            print("─" * 40)

            # 流動性
            liq = result['liquidity']
            liq_icon = "✅" if liq['pass'] else "🚫"
            print(f"{liq_icon} 流動性：{'PASS' if liq['pass'] else 'FAIL'}")
            print(f"   └─ {liq['reason']}")
            if liq.get('warning'):
                print(f"   └─ {liq['warning']}")

            if not liq['pass']:
                print(f"結論：🚫 淘汰（流動性不足）")
                print("─" * 40)
                print()
                continue

            # 技術面
            tech = result['technical']
            tech_icon = "✅" if tech['pass'] else "🚫"
            print(f"{tech_icon} 技術面：{'PASS' if tech['pass'] else 'FAIL'}")
            print(f"   └─ {tech['reason']}")

            if not tech['pass']:
                print(f"結論：🚫 淘汰（{tech['reason']}）")
                print("─" * 40)
                print()
                continue

            # 籌碼
            chips = result['chips']
            if chips['level'] == "STRONG_CONSENSUS":
                chips_icon = "🔥"
            elif chips['level'] == "MODERATE":
                chips_icon = "⚡"
            elif chips['level'] == "NEUTRAL":
                chips_icon = "➖"
            else:
                chips_icon = "🚫"

            print(f"{chips_icon} 籌碼面：{chips['level']} (評分 {chips['score']:+d})")
            for reason in chips['reasons']:
                print(f"   └─ {reason}")

            # 最終決策
            decision = result['final_decision']
            if decision['action'] == "BUY":
                print(f"💰 建議倉位：{decision['allocation']:.0%}")
                print(f"結論：{decision['reason']}")
            else:
                print(f"結論：🚫 淘汰（{decision['reason']}）")

            print("─" * 40)
            print()
    else:
        print("🚫 市場熔斷中，跳過候選股票分析")
        print()

    # === 持倉健檢 ===
    print("=" * 60)
    print("📦 持倉健檢 (Guardian 5)")
    print("-" * 60)
    print()

    for idx, item in enumerate(portfolio_actions, 1):
        holding = item['holding']
        action = item['action']

        pnl_icon = "📈" if action['pnl'] > 0 else "📉"

        print(f"[{idx}] {holding['stock_id']} {holding['stock_name']}")
        print(f"   成本：{holding['cost_price']} → 現價：{holding['current_price']} ({action['pnl']:+.1%})")

        if action['action'] == "SELL":
            print(f"   狀態：{action['reason']}")
        else:
            print(f"   狀態：✅ {action['reason']}")

        print()

    # === 執行摘要 ===
    print("=" * 60)
    print("📊 執行摘要")
    print("-" * 60)

    if market_check['status'] == "SAFE":
        approved = [r for r in analysis_results if r['final_decision']['action'] == "BUY"]
        rejected = [r for r in analysis_results if r['final_decision']['action'] == "REJECT"]

        print(f"✅ 通過篩選：{len(approved)} 支")
        for r in approved:
            stock = r['stock']
            print(f"   - {stock['id']} {stock['name']} (建議 {r['final_decision']['allocation']:.0%})")

        print()
        print(f"🚫 淘汰：{len(rejected)} 支")
        for r in rejected:
            stock = r['stock']
            print(f"   - {stock['id']} {stock['name']} ({r['final_decision']['reason']})")
    else:
        print("🔴 市場熔斷，暫停買入")

    print()
    print("📦 持倉動作：")

    hold_count = sum(1 for item in portfolio_actions if item['action']['action'] == "HOLD")
    sell_count = sum(1 for item in portfolio_actions if item['action']['action'] == "SELL")

    print(f"   - 續抱：{hold_count} 支")
    print(f"   - 賣出：{sell_count} 支")

    if sell_count > 0:
        print()
        print("   賣出明細：")
        for item in portfolio_actions:
            if item['action']['action'] == "SELL":
                holding = item['holding']
                action = item['action']
                print(f"   - {holding['stock_id']} {holding['stock_name']} ({action['type']})")

    print()
    print("=" * 60)
    print("報告結束")
    print("=" * 60)


# ============================================================
# 主程式
# ============================================================

def main():
    """
    主程式流程

    可切換測試場景：
    - "bull": 多頭市場（SAFE）
    - "bear": 空頭市場（DANGER）
    """

    # === 選擇測試場景 ===
    # 修改這裡切換場景
    SCENARIO = "bull"  # "bull" 或 "bear"

    # 1. 生成 Mock Data
    market_data = generate_market_data(SCENARIO)
    stocks = generate_stock_candidates()
    portfolio = generate_portfolio()

    # 2. Guardian 1: 市場檢查
    market_check = guardian_1_market_check(market_data)

    # 3. 分析候選股票（只有 SAFE 時執行）
    if market_check['status'] == "SAFE":
        analysis_results = analyze_watchlist(stocks, market_check['status'])
    else:
        analysis_results = []

    # 4. 持倉健檢（無論 SAFE 或 DANGER 都執行）
    portfolio_actions = check_portfolio(portfolio, market_check['status'])

    # 5. 輸出報告
    print_report(market_data, market_check, analysis_results, portfolio_actions)

    # 6. 測試提示
    print()
    print("💡 測試提示：")
    print(f"   當前場景：{SCENARIO}")
    print("   若要測試空頭場景，請修改 main() 中的 SCENARIO = \"bear\"")
    print()


if __name__ == "__main__":
    main()
