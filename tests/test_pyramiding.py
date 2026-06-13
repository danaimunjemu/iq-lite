import asyncio
from models.trading import Position, Tick
from ingestion.pyramiding import PyramidingEngine

def test_pyramiding():
    print("--- Position Scaling (Pyramiding) Engine Test ---")
    
    # 1. Setup
    symbol = "BOOM1000"
    engine = PyramidingEngine(max_positions=3, scale_factor=0.5)
    
    # Initial Position: BUY at 100.0, Size 0.1
    pos1 = Position(symbol, "BUY", 100.0, 0.1, 1711900000)
    
    # 2. Test Case A: Profitable and Aligned
    print("\nCase A: Profitable (10 pts) and Aligned...")
    tick_win = Tick(symbol, 110.0, 1711900100)
    features_win = {"ma_50": 105.0, "spike_risk": 0.05}
    
    signal = engine.scale_position(symbol, tick_win, [pos1], features_win)
    assert signal is not None
    assert signal.action == "BUY"
    assert signal.size == 0.05 # 50% of 0.1
    print(f"  [PASS] Scale-In generated: {signal.size} lots")

    # 3. Test Case B: In Loss
    print("\nCase B: In Loss (5 pts)...")
    tick_loss = Tick(symbol, 95.0, 1711900101)
    features_loss = {"ma_50": 98.0, "spike_risk": 0.05}
    
    signal = engine.scale_position(symbol, tick_loss, [pos1], features_loss)
    assert signal is None
    print("  [PASS] Scaling suppressed due to PnL.")

    # 4. Test Case C: Trend Mismatch (in profit but below MA50)
    print("\nCase C: Trend Mismatch (Profit 5 pts, but Price < MA50)...")
    tick_mismatch = Tick(symbol, 105.0, 1711900102)
    features_mismatch = {"ma_50": 108.0, "spike_risk": 0.05}
    
    signal = engine.scale_position(symbol, tick_mismatch, [pos1], features_mismatch)
    assert signal is None
    print("  [PASS] Scaling suppressed due to Trend Mismatch.")

    # 5. Test Case D: Max Positions Reached
    print("\nCase D: Max Positions Reached...")
    pos2 = Position(symbol, "BUY", 110.0, 0.05, 1711900103)
    pos3 = Position(symbol, "BUY", 115.0, 0.025, 1711900104)
    tick_limit = Tick(symbol, 120.0, 1711900105)
    
    signal = engine.scale_position(symbol, tick_limit, [pos1, pos2, pos3], features_win)
    assert signal is None
    print("  [PASS] Scaling suppressed due to Max Positions Limit.")

    print("\n[SUCCESS] PyramidingEngine logic verified.")

if __name__ == "__main__":
    test_pyramiding()
