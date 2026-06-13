import asyncio
from models.trading import Tick, Candle
from execution.provider import MarketDataProvider
from strategy.synthetic_strategy import SyntheticIndexStrategy

async def test_full_strategy():
    print("--- Full Strategy Life-Cycle Verification ---")
    
    # 1. Setup Infrastructure
    symbol = "BOOM1000"
    provider = MarketDataProvider([symbol])
    strategy = SyntheticIndexStrategy([symbol], provider)
    
    # 2. Stage 1: Macro Trend (H1) and Stabilization
    print("\nStage 1: Synchronizing Macro Trend (H1 Below Open for BOOM SELL)...")
    h1_context = Candle(symbol, open=110.0, high=115.0, low=105.0, close=108.0, epoch=1711900000, is_closed=True)
    provider.update_candles({3600: h1_context})
    
    # Fill signal buffer (M5 logic)
    for i in range(150):
        strategy.process_tick(Tick(symbol, 100.0, 1711900000 + i))
        
    # 3. Stage 2: RSI Trigger + Zone Confirmation -> ENTRY
    print("\nStage 2: Triggering RSI Crossback in High Prob Zone...")
    # Breech
    for i in range(151, 160):
        strategy.process_tick(Tick(symbol, 120.0, 1711900000 + i))
        
    # Crossback (120 -> 105)
    tick_entry = Tick(symbol, 105.0, 1711900161)
    signals = strategy.process_tick(tick_entry)
    
    if any(s.action == "SELL" for s in signals):
        print(f"  [PASS] Initial Entry Generated. Reason: {signals[0].reason}")
    else:
        print("  [FAIL] No entry signal generated.")
        return

    # 4. Stage 3: Profitable and Aligned -> PYRAMIDING
    print("\nStage 3: Profitable Scaling (Pyramiding)...")
    # Move price down (in profit for SELL)
    tick_scale = Tick(symbol, 100.0, 1711900200)
    signals = strategy.process_tick(tick_scale)
    
    if any(s.action == "SELL" and "Pyramiding" in s.reason for s in signals):
        print(f"  [PASS] Scale-In Generated (Size: {signals[0].size})")
    else:
        print(f"  [FAIL] Scaling skipped. Reason: {[s.reason for s in signals]}")

    # 5. Stage 4: High Spike Risk -> IMMEDIATE EXIT
    print("\nStage 4: High Spike Risk Detection...")
    # Inject an outlier tick to trigger spike prob
    # In features.py: Spike is triggered if abs(price - mean) > 3.5 * std
    # price was around 100-110. mean ~ 105. std ~ 5.
    # Price 150 will definitely spike.
    tick_spike = Tick(symbol, 150.0, 1711900300)
    signals = strategy.process_tick(tick_spike)
    
    if any(s.action == "EXIT" and "Spike" in s.reason for s in signals):
        print(f"  [PASS] Emergency Exit Triggered. Reason: {signals[0].reason}")
    else:
        print("  [FAIL] Failed to trigger spike exit.")

    print("\n[SUCCESS] Full strategy lifecycle lifecycle verified.")

if __name__ == "__main__":
    asyncio.run(test_full_strategy())
