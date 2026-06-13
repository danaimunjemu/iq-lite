from analytics.performance import PerformanceAnalytics

def test_poker_analytics():
    print("--- Performance Analytics Test ---")
    
    # 1. Setup synthetic trades: 4 wins, 1 loss
    # Net PnL = (4 * 10) - 10 = 30
    trades = [
        {'pnl': 10.0}, {'pnl': 10.0}, {'pnl': 10.0}, {'pnl': 10.0},
        {'pnl': -10.0}
    ]
    
    analytics = PerformanceAnalytics(trades, initial_balance=100.0)
    metrics = analytics.calculate_all()
    
    print("Verification Results:")
    print(f"  Expected Win Rate: 0.8 | Actual: {metrics['win_rate']}")
    print(f"  Expected Profit Factor: 4.0 | Actual: {metrics['profit_factor']}")
    print(f"  Expected Expectancy: 6.0 | Actual: {metrics['expectancy']}")
    print(f"  Max Drawdown: {metrics['max_drawdown']} (Expecting $10.0)")
    
    # 2. Add an interpretation
    advice = analytics.generate_interpretation(metrics)
    print(f"\nTrading Advice: {advice}")

if __name__ == "__main__":
    test_poker_analytics()
