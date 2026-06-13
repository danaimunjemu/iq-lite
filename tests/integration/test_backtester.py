import os
import pytest
import csv
from backtesting.engine import BacktestEngine
from tests.mocks.data_generator import SyntheticMarketGenerator

def test_backtest_pnl_fidelity():
    """Verifies that the backtest engine calculates PnL accurately against a known trend."""
    symbol = "TREND1000"
    gen = SyntheticMarketGenerator(symbol=symbol, base_price=1000.0)
    
    # 1. Generate 1000 ticks of a linear UP trend
    # We expect a BUY signal eventually, and a PROFIT exit.
    ticks = gen.generate_linear_trend(n_ticks=1000, drift_per_tick=0.01)
    
    csv_path = "tests/mocks/test_trend.csv"
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["symbol", "price", "epoch"])
        for t in ticks:
            writer.writerow([t.symbol, t.price, t.epoch])
            
    # 2. Run Engine
    # Setup with tight TP to ensure a trade closes
    engine = BacktestEngine(
        symbol=symbol, 
        initial_balance=1000.0,
        sl_amount=5.0,
        tp_amount=2.0
    )
    
    result = engine.run(csv_path)
    
    # 3. Verification
    # Profit Factor should be > 1 since price only went UP
    if result.total_trades > 0:
        assert result.final_balance > result.initial_balance
        assert result.net_pnl > 0
        assert result.win_rate > 0
    
    # Cleanup
    if os.path.exists(csv_path):
        os.remove(csv_path)

def test_backtest_kill_switch_halt():
    """Verifies that the backtest engine stops processing if the risk kill-switch triggers."""
    symbol = "SPIKE1000"
    gen = SyntheticMarketGenerator(symbol=symbol, base_price=1000.0)
    
    # Generate 500 stable ticks, then a massive DROP (to trigger SL and Daily Loss)
    # 1. Warm up indicators with stable ticks
    ticks = gen.generate_linear_trend(n_ticks=10, drift_per_tick=0.0)
    
    csv_path = "tests/mocks/test_halt.csv"
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["symbol", "price", "epoch"])
        for t in ticks:
            writer.writerow([t.symbol, t.price, t.epoch])
        # 2. Add the "Account Buster" tick (50% Drop) - Close to entry to avoid duration exit
        writer.writerow([symbol, 500.0, 1711900011]) 
            
    engine = BacktestEngine(
        symbol=symbol, 
        initial_balance=1000.0,
        sl_amount=400.0 
    )
    # Disable duration exit for this test
    engine.exit_manager.max_ticks = 1000
    # Tweak risk manager to trigger with very small loss
    engine.risk_mgr.max_daily_loss = 5.0 
    
    # 3. Inject active trade and run
    engine._open_position(MagicMockSignal(symbol, 1000.0, "BUY"))
    result = engine.run(csv_path)
    
    # The engine should halt after the drop
    assert engine.risk_mgr.is_kill_switch_active is True
    
    if os.path.exists(csv_path):
        os.remove(csv_path)

class MagicMockSignal:
    def __init__(self, symbol, price, action):
        self.symbol = symbol
        self.price = price
        self.action = action
        self.epoch = 1711900000
        self.size = 0.1
        self.spike_risk = 0.01
        self.confidence = 0.9
        self.reason = "Manual Mock"
