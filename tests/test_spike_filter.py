import logging
from strategy.filters import is_trade_safe

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_spike_filter():
    print("--- Testing Spike-Aware Trade Filter ---")
    
    # 1. Safe Case (Recent spike, calm market)
    ctx_safe = {
        "ticks_since_spike": 100,
        "return_std": 0.0001,
        "avg_volatility": 0.0001,
        "momentum": 0.0,
        "symbol": "CRASH1000"
    }
    safe_result = is_trade_safe(ctx_safe, holding_time=20)
    print(f"Safe Case (100 ticks since): {'PASS' if safe_result else 'FAIL'}")
    
    # 2. Overdue Case (1600 ticks since spike)
    ctx_overdue = ctx_safe.copy()
    ctx_overdue["ticks_since_spike"] = 1600
    overdue_result = is_trade_safe(ctx_overdue, holding_time=20)
    print(f"Overdue Case (1600 ticks since): {'PASS' if overdue_result else 'REJECTED'}")
    
    # 3. High Probability Case (High instability)
    ctx_high_risk = ctx_safe.copy()
    ctx_high_risk["return_std"] = 0.0012 # Very high instability
    risk_result = is_trade_safe(ctx_high_risk, holding_time=30) # Longer holding duration
    print(f"High Risk Case (Volatile): {'PASS' if risk_result else 'REJECTED'}")
    
    # Assertions
    assert safe_result == True
    assert overdue_result == False # Rejected due to 1500 cap
    assert risk_result == False # Rejected due to probability
    
    print("\nAll spike-aware filter tests passed!")

if __name__ == "__main__":
    test_spike_filter()
