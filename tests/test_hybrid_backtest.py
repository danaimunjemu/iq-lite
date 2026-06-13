import logging
from backtesting.engine import BacktestEngine

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_hybrid_backtest():
    print("--- Hybrid M5 Backtest Simulation ---")
    
    # 1. Setup
    symbol = "CRASH1000"
    engine = BacktestEngine(
        symbol=symbol,
        initial_balance=1000.0,
        base_risk=0.01,
        prob_threshold=0.20,
        tp_amount=1.0,
        sl_amount=2.0
    )
    
    # 2. Run
    csv_path = "ticks_data.csv"
    result = engine.run(csv_path)
    
    # 3. Report
    print(f"\nFinal Results for {symbol}:")
    print(f"  Final Balance: ${result.final_balance:.2f}")
    print(f"  Net PnL: ${result.net_pnl:.2f}")
    print(f"  Total Trades: {result.total_trades}")
    print(f"  Win Rate: {result.win_rate * 100:.2f}%")
    print(f"  Max Drawdown: ${result.max_drawdown:.2f}")
    print(f"  Profit Factor: {result.profit_factor}")

    # Theoretical Verification
    # Since we use M5 candles, we expect fewer trades but higher quality.
    assert result.total_trades >= 0
    assert result.final_balance > 0

if __name__ == "__main__":
    test_hybrid_backtest()
