import time
from datetime import datetime, timedelta
from risk.manager import RiskManager

def test_risk_scenarios():
    print("--- Trading Risk Management Simulation ---")
    
    # 1. Initialize Risk Manager with strict limits
    risk_mgr = RiskManager(
        max_daily_loss=100.0, 
        max_drawdown=200.0, 
        max_trades_per_hour=5
    )
    print("Initial State: OK to trade\n")

    # Scenario A: Frequency Breach (Hour)
    print("Scenario A: Rapid Trading Breach")
    for i in range(6):
        can_trade, reason = risk_mgr.can_trade()
        if can_trade:
            risk_mgr.record_trade(pnl=5.0, current_balance=1005.0)
            print(f"  Attempt {i+1}: Success (PNL +5)")
        else:
            print(f"  Attempt {i+1}: BLOCKED - {reason}")
    print("")

    # Scenario B: Daily Loss Breach
    print("Scenario B: Daily Loss Limit Breach")
    risk_mgr.record_trade(pnl=-110.0, current_balance=900.0)
    can_trade, reason = risk_mgr.can_trade()
    print(f"  After -$110 Loss: Can Trade? {can_trade} | Reason: {reason}\n")

    # Scenario C: Reset and Drawdown Breach
    print("Scenario C: Peak-to-Trough Drawdown Breach")
    risk_mgr.reset_kill_switch()
    risk_mgr.peak_balance = 2000.0   # Simulate a high point
    risk_mgr.record_trade(pnl=-250.0, current_balance=1750.0)
    can_trade, reason = risk_mgr.can_trade()
    print(f"  After Drawdown of $250: Can Trade? {can_trade} | Reason: {reason}\n")

    # 4. Final State
    state = risk_mgr.get_state()
    print("--- Final Risk Status ---")
    for k, v in state.to_dict().items():
        print(f"{k.replace('_', ' ').title()}: {v}")

if __name__ == "__main__":
    test_risk_scenarios()
