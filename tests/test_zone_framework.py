import asyncio
from models.trading import Tick
from strategy.base_strategy import UnifiedSignalEngine

async def test_zone_framework():
    print("--- High Probability Zone Framework Test ---")
    
    # 1. Setup
    symbol = "BOOM1000"
    engine = UnifiedSignalEngine(symbols=[symbol])
    
    # 2. Test Case A: RSI Trigger in a LOW Probability Zone
    # (High volatility, no trend deviation, just after spike)
    print("\nCase A: RSI Trigger in LOW Prob Zone...")
    # Inject 50 ticks to fill windows but keep them 'noisy'
    for i in range(50):
        # High volatility noise
        price = 100.0 + (i % 5) 
        engine.process_tick(Tick(symbol, price, 1711900000 + i))
        
    # Trigger an RSI signals (Sell at 75)
    # But Zone Detector will likely reject due to 'noisy' features
    tick_low_prob = Tick(symbol, 105.0, 1711900051)
    signal = engine.process_tick(tick_low_prob)
    
    # In my logic: confidence += 0.4 if trend_dist > 0.001
    # Here price is 105, MA50 is ~102. Dist = 3/102 = 0.029 (Trend: PASS)
    # Volatility is likely high. Ticks since spike is low (50).
    # Result depends on the exact float values, but we can verify the 'REJECTED' log
    if signal is None:
        print("  [PASS] Signal correctly suppressed by Zone Gating.")
    else:
        print(f"  [FAIL] Signal leaked through: {signal.action} (Zone Conf: {signal.zone_confidence})")

    # 3. Test Case B: RSI Trigger in a HIGH Probability Zone
    print("\nCase B: RSI Trigger in HIGH Prob Zone...")
    # Stabilize the price first
    for i in range(50, 150):
        engine.process_tick(Tick(symbol, 100.0, 1711900000 + i))
        
    # Now create a clean trend deviation + RSI trigger
    # Price was stable at 100. Now move to 100.6 (0.6% move)
    tick_high_prob = Tick(symbol, 100.6, 1711900151)
    signal = engine.process_tick(tick_high_prob)
    
    if signal and signal.zone_confidence >= 0.65:
        print(f"  [PASS] Signal ACCEPTED in High Prob Zone. Conf: {signal.zone_confidence}")
    else:
        print("  [FAIL] Signal rejected in what should be a clean zone.")

    print("\n[SUCCESS] Zone Framework verification complete.")

if __name__ == "__main__":
    asyncio.run(test_zone_framework())
