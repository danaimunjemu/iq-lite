import asyncio
from models.trading import Tick
from features.candles import CandleAggregator

def test_candle_aggregator():
    print("--- CandleAggregator Test ---")
    
    # 1. Setup (M5 and H1)
    aggregator = CandleAggregator(intervals=[300, 3600])
    symbol = "TEST"
    
    # 2. Simulate ticks crossing M5 boundary
    print("Simulating ticks for M5 boundary (300s)...")
    base_epoch = 1711900000
    
    # Tick 1: Start
    aggregator.update(Tick(symbol, 100.0, base_epoch))
    
    # Tick 2: 301s later (Crosses M5)
    closed = aggregator.update(Tick(symbol, 101.0, base_epoch + 301))
    print(f"  Closed after 301s: {list(closed.keys())}")
    assert 300 in closed
    assert 3600 not in closed
    
    # Tick 3: 3601s later (Crosses H1 and another M5)
    print("Simulating ticks for H1 boundary (3600s)...")
    closed = aggregator.update(Tick(symbol, 102.0, base_epoch + 3601))
    print(f"  Closed after 3601s: {list(closed.keys())}")
    assert 300 in closed
    assert 3600 in closed
    
    # Tick 4: 7201s later (Crosses H1 and M5 again)
    print("Simulating ticks for H1 boundary again (7200s)...")
    closed = aggregator.update(Tick(symbol, 103.0, base_epoch + 7201))
    print(f"  Closed after 7201s: {list(closed.keys())}")
    assert 300 in closed
    assert 3600 in closed

    # 3. Verify Incremental Updates
    print("\nVerifying Incremental Updates (get_current_candle)...")
    aggregator.update(Tick(symbol, 105.0, base_epoch + 7300))
    current_m5 = aggregator.get_current_candle(symbol, 300)
    print(f"  Current High (M5): {current_m5.high}")
    assert current_m5.high == 105.0
    
    aggregator.update(Tick(symbol, 110.0, base_epoch + 7350))
    current_h1 = aggregator.get_current_candle(symbol, 3600)
    print(f"  Current High (H1): {current_h1.high}")
    assert current_h1.high == 110.0

    print("\n[SUCCESS] CandleAggregator multi-timeframe logic verified.")

if __name__ == "__main__":
    test_candle_aggregator()
