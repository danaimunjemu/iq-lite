import logging
from execution.exit_manager import TradeExitManager
from models.trading import TradeSignal

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_exit_logic():
    print("--- Testing Trade Duration & Risk Control ---")
    
    # 1. Setup
    mgr = TradeExitManager(max_ticks=20, risk_threshold=0.30)
    symbol = "CRASH1000"
    
    # 2. Register Trade (BUY @ RSI 15)
    sig = TradeSignal(symbol=symbol, action="BUY", price=5400.0, epoch=1000, probability=0.5, reason="RSI Reversal")
    mgr.register_trade(sig, current_rsi=15.2)
    
    # 3. Simulate Ticks
    
    # Case A: Ticks passing (Duration)
    for i in range(15):
        features = {"rsi_14": 45.0, "spike_risk": 0.12}
        res = mgr.evaluate_exit(symbol, features)
        assert res is None, f"Premature exit at tick {i}"
        
    # Case B: Spike Risk Increase (Emergency Exit)
    features_risk = {"rsi_14": 50.0, "spike_risk": 0.31} # Above 0.30
    res_risk = mgr.evaluate_exit(symbol, features_risk)
    print(f"Risk Exit Triggered: {res_risk}")
    assert "High Spike Risk" in res_risk
    
    # Reset for next case
    mgr.register_trade(sig, current_rsi=15.2)
    
    # Case C: RSI Momentum Exhaustion (Profit Taking)
    features_rsi = {"rsi_14": 72.5, "spike_risk": 0.10} # Above 70 (Overbought)
    res_rsi = mgr.evaluate_exit(symbol, features_rsi)
    print(f"RSI Exit Triggered: {res_rsi}")
    assert "Momentum Exhaustion" in res_rsi
    
    # Case D: Max Duration reached
    mgr.register_trade(sig, current_rsi=15.2)
    for i in range(21):
        features_dur = {"rsi_14": 50.0, "spike_risk": 0.10}
        res_dur = mgr.evaluate_exit(symbol, features_dur)
        if res_dur: break
        
    print(f"Duration Exit Triggered: {res_dur}")
    assert "Max duration reached" in res_dur

    print("\nAll trade duration control tests passed!")

if __name__ == "__main__":
    test_exit_logic()
