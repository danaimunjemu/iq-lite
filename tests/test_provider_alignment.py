import asyncio
from models.trading import Tick, Candle
from execution.provider import MarketDataProvider

def test_provider_alignment():
    print("--- MarketDataProvider Alignment Test ---")
    
    # 1. Setup
    symbol = "TEST"
    provider = MarketDataProvider(symbols=[symbol])
    base_epoch = 1711900000
    
    # 2. Simulate ticks and candles
    print("Simulating data stream...")
    
    # Tick 1: Minute 0
    provider.update_tick(Tick(symbol, 100.0, base_epoch))
    
    # Tick 2: Minute 4 (Within M5 boundary)
    provider.update_tick(Tick(symbol, 101.0, base_epoch + 240))
    
    # Verify: Latest M5 should be empty
    assert provider.get_latest_m5(symbol) is None
    print("  M5 Guard: PASS (No candle before first cross)")
    
    # Tick 3: Minute 5 (Crosses M5)
    # Orchestrator would emit a closed candle here
    closed_m5 = Candle(symbol, 100.0, 101.0, 99.0, 100.5, base_epoch, is_closed=True)
    provider.update_candles({300: closed_m5})
    provider.update_tick(Tick(symbol, 100.6, base_epoch + 300))
    
    # Verify: Latest M5 should be the one at base_epoch
    latest_m5 = provider.get_latest_m5(symbol)
    assert latest_m5 is not None
    assert latest_m5.epoch == base_epoch
    print(f"  M5 Sync: PASS (Epoch {latest_m5.epoch} detected)")
    
    # 3. Alignment Check
    print("Verifying Alignment logic...")
    # Tick 4: Minute 9 (4 minutes after last candle cross)
    provider.update_tick(Tick(symbol, 102.0, base_epoch + 540))
    assert provider.is_aligned(symbol) is True
    print("  Alignment (9m absolute / 4m offset): PASS (True)")
    
    # Tick 5: Minute 16 (11 minutes after last candle - exceeds 600s threshold)
    provider.update_tick(Tick(symbol, 103.0, base_epoch + 960))
    assert provider.is_aligned(symbol) is False
    print("  Alignment (16m absolute / 11m offset): PASS (False - Alert Triggered)")

    print("\n[SUCCESS] MarketDataProvider alignment verified.")

if __name__ == "__main__":
    test_provider_alignment()
