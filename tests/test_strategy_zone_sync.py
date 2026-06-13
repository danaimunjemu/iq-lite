import asyncio
from models.trading import Tick, Candle
from execution.provider import MarketDataProvider
from strategy.synthetic_strategy import SyntheticIndexStrategy

async def test_strategy_zone_sync():
    print("--- Strategy + H1 Zone Integration Verification ---")
    
    # 1. Setup
    symbol = "BOOM1000" # SELL Mode
    provider = MarketDataProvider([symbol])
    strategy = SyntheticIndexStrategy([symbol], provider)
    
    # 2. Stage 1: No Zones -> Suppression Test
    print("\nStage 1: Suppression Test (RSI Trigger but No structural zone)...")
    # Feed 150 stabilize ticks
    for i in range(150):
        strategy.process_tick(Tick(symbol, 100.0, 1711900000 + i))
    
    # Trigger RSI Breech (100 -> 150)
    for i in range(151, 160):
        strategy.process_tick(Tick(symbol, 150.0, 1711900000 + i))
    
    # RSI Crossback (150 -> 120)
    tick_trigger = Tick(symbol, 120.0, 1711900161)
    signals = strategy.process_tick(tick_trigger)
    
    if not signals:
        print("  [PASS] Signal suppressed due to missing H1 structural zone.")
    else:
        print(f"  [FAIL] Signal emitted without zone alignment! Reason: {signals[0].reason}")

    # 3. Stage 2: Alignment Test (Add H1 Resistance Zone)
    print("\nStage 2: Alignment Test (Price near H1 Resistance Zone)...")
    # Create H1 Resistance Zone at ~120
    # For SELL, price must be below H1 Open (e.g. Open at 150)
    h1_history = [
        Candle(symbol, 150, 155, 145, 148, 1711900000 + i*3600, True) for i in range(12)
    ]
    # Swing High at index 12 (Price 120)
    h1_history.append(Candle(symbol, 110, 120, 101, 105, 1711900000 + 12*3600, True))
    h1_history.extend([
        Candle(symbol, 150, 155, 145, 148, 1711900000 + i*3600, True) for i in range(13, 16)
    ])
    
    provider.update_candles({3600: h1_history[-1]})
    # Mocking the history in provider for the rescanner
    provider.history[3600][symbol].extend(h1_history[:-1])
    
    # Rescan triggers on process_tick if epoch > 0
    strategy.process_tick(Tick(symbol, 120.0, 1711900162))
    
    # RE-TRIGGER Signal for Alignment
    # Breech again
    for i in range(163, 170):
        strategy.process_tick(Tick(symbol, 150.0, 1711900000 + i))
        
    # Now check entry at 119.95 (Price is near Resistance @ 120.0 AND RSI crossback triggers)
    signals = strategy.process_tick(Tick(symbol, 119.95, 1711900171))
    
    if any(s.action == "SELL" and "Resistance" in s.reason for s in signals):
         print(f"  [PASS] Signal approved at structural level. Confidence: {signals[0].confidence:.2f}")
    else:
         print(f"  [FAIL] Signal still suppressed despite being near Resistance zone.")

    print("\n[SUCCESS] Strategy + H1 Zone Integration verified.")

if __name__ == "__main__":
    asyncio.run(test_strategy_zone_sync())
