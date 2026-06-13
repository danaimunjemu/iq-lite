import csv
import os
from backtesting.engine import BacktestEngine
from models.trading import Tick

class MockSignal:
    symbol = "TEST"
    price = 1000.0
    action = "BUY"
    epoch = 1711900000
    size = 0.1
    spike_risk = 0.01
    confidence = 0.9
    reason = "Mock"

def diagnostic():
    engine = BacktestEngine("TEST", initial_balance=1000.0)
    engine.risk_mgr.max_daily_loss = 20.0
    
    # 1. Start trade
    engine._open_position(MockSignal())
    print(f"Trade opened: {engine.active_trade}")
    
    # 2. Process a crash tick
    tick = Tick("TEST", 500.0, 1711900100)
    engine._process_tick(tick)
    
    print(f"Active trade after tick: {engine.active_trade}")
    print(f"Daily PNL: {engine.risk_mgr.daily_pnl}")
    print(f"Kill switch: {engine.risk_mgr.is_kill_switch_active}")
    print(f"Kill reason: {engine.risk_mgr.kill_reason}")

if __name__ == "__main__":
    diagnostic()
