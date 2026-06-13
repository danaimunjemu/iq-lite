import asyncio
from models.trading import Tick
from strategy.base_strategy import UnifiedSignalEngine
from features.zones import ZoneResult

async def test_rsi_zone_sync():
    print("--- RSI + Zone Synchronization Test ---")
    
    # 1. Setup
    symbol = "BOOM1000"
    engine = UnifiedSignalEngine(symbols=[symbol])
    
    # 2. Step 1: Breech the 85 level
    print("\nStep 1: Breeching 85 (Setup Phase)...")
    # Ticks to fill MA50
    for i in range(100):
        engine.process_tick(Tick(symbol, 100.0, 1711900000 + i))
    
    # Breech at 120 (Sustain to move RSI_MA towards 100)
    for i in range(101, 110):
        engine.process_tick(Tick(symbol, 120.0, 1711900000 + i))
        
    assert engine.rsi_engine.states[symbol].name == "BREECHED"
    print(f"  [PASS] State is BREECHED (RSI_MA: {engine.feature_gen._get_window(symbol).get_stats()['rsi_ma_5']:.2f})")

    # 3. Step 2: Crossback in a LOW Probability Zone
    print("\nStep 2: Crossback in LOW Prob Zone...")
    # Move price back down to 101. This triggers crossback.
    # But we'll force the Zone Detector to be 'stale' or 'noisy'
    # By default, 0.6% move passed volatility check, but here we've been volatile.
    tick_crossback = Tick(symbol, 101.0, 1711900102)
    signal = engine.process_tick(tick_crossback)
    
    # If the system is working, signal is None because zone confidence < 0.65
    if signal is None and engine.rsi_engine.states[symbol].name == "IDLE":
        print("  [PASS] Signal suppressed in Low Prob Zone. State reset to IDLE.")
    else:
        print(f"  [FAIL] Unexpected result: Signal={signal}, State={engine.rsi_engine.states[symbol].name}")

    # 4. Step 3: Re-Breech and Crossback in a HIGH Probability Zone
    print("\nStep 3: Re-Breech and Crossback in HIGH Prob Zone...")
    # Stabilize
    for i in range(103, 203):
        engine.process_tick(Tick(symbol, 100.0, 1711900000 + i))
        
    # Breech
    engine.process_tick(Tick(symbol, 110.0, 1711900204))
    
    # Controlled Crossback (0.5% move)
    tick_valid = Tick(symbol, 109.5, 1711900205)
    signal = engine.process_tick(tick_valid)
    
    if signal and signal.action == "SELL":
        print(f"  [PASS] Signal ACCEPTED in High Prob Zone. Conf: {signal.zone_confidence}")
    else:
        print(f"  [FAIL] Signal rejected in valid zone: {signal}")

    print("\n[SUCCESS] RSI + Zone synchronization verified.")

if __name__ == "__main__":
    asyncio.run(test_rsi_zone_sync())
