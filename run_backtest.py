import sys
from ingestion.backtester import BacktestEngine

def run_sim(symbol: str, csv_path: str):
    print(f"--- Quant Backtest Simulation: {symbol} ---")
    
    # 1. Setup Engine
    # Initial Balance: $1,000 | Risk: 1% | TP: 0.5 points | SL: 2.0 points
    engine = BacktestEngine(
        symbol=symbol,
        initial_balance=1000.0,
        risk_per_trade=0.01,
        prob_threshold=0.15,
        tp_amount=0.5,
        sl_amount=2.0
    )

    # 2. Run
    result = engine.run(csv_path)

    # 3. Report
    report = result.to_dict()
    print("\n--- Backtest Performance Report ---")
    for k, v in report.items():
        print(f"  {k.replace('_', ' ').title().replace('Pnl', 'PnL')}: {v}")
    
    # Print a few sample trades if any
    if engine.trades_history:
        print(f"\n--- Sample Trades (First 3) ---")
        for t in engine.trades_history[:3]:
            print(f"  Entry: {t['entry_price']:.3f} | Exit: {t['exit_price']:.3f} | Size: {t['size']:.1f} | PnL: {t['pnl']:.2f} | Reason: {t['exit_reason']}")

if __name__ == "__main__":
    csv_file = "ticks_data.csv"
    run_sim("CRASH1000", csv_file)
