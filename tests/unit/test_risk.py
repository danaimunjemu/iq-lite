import pytest
from datetime import datetime, timedelta
from risk.manager import RiskManager

def test_risk_daily_loss_kill_switch():
    """Verifies that a breach in daily loss triggers the permanent kill switch."""
    risk_mgr = RiskManager(max_daily_loss=100.0)
    
    # Simulate a -$110 Loss
    risk_mgr.record_trade(pnl=-110.0, current_balance=890.0)
    
    can_trade, reason = risk_mgr.can_trade()
    assert can_trade is False
    assert "Daily loss limit reached" in reason
    assert risk_mgr.is_kill_switch_active is True

def test_risk_frequency_limit_hour():
    """Verifies that trading frequency per hour is strictly enforced."""
    risk_mgr = RiskManager(max_trades_per_hour=3)
    
    # Record 3 trades within the last hour
    now = datetime.now()
    risk_mgr.trade_timestamps = [
        now - timedelta(minutes=10),
        now - timedelta(minutes=20),
        now - timedelta(minutes=30)
    ]
    
    can_trade, reason = risk_mgr.can_trade()
    assert can_trade is False
    assert "Max hourly trade frequency reached" in reason

def test_drawdown_tracking():
    """Verifies that peak-to-trough drawdown is correctly calculated and triggers gating."""
    risk_mgr = RiskManager(max_drawdown=200.0)
    risk_mgr.peak_balance = 1000.0
    
    # 1. PNL -150 -> $850 Balance (DD: 150)
    risk_mgr.record_trade(pnl=-150.0, current_balance=850.0)
    assert risk_mgr.current_drawdown == 150.0
    assert risk_mgr.can_trade()[0] is True
    
    # 2. PNL -60 -> $790 Balance (DD: 210 -> BREACH)
    risk_mgr.record_trade(pnl=-60.0, current_balance=790.0)
    assert risk_mgr.current_drawdown == 210.0
    assert risk_mgr.is_kill_switch_active is True

def test_manual_reset_kill_switch():
    """Verifies that a kill-switch requires a manual reset before trading can resume."""
    risk_mgr = RiskManager(max_daily_loss=50.0)
    risk_mgr.record_trade(pnl=-60.0, current_balance=940.0)
    
    assert risk_mgr.is_kill_switch_active is True
    
    risk_mgr.reset_kill_switch()
    assert risk_mgr.is_kill_switch_active is False
    assert risk_mgr.daily_pnl == 0.0
