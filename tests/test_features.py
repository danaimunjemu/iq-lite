import asyncio
import json
from models.trading import Tick
from features.indicators import FeatureGenerator

async def test_features():
    generator = FeatureGenerator(window_size=10)
    
    # Simulate a steady price trend then a spike
    prices = [10.0, 10.1, 10.2, 10.1, 10.0, 10.2, 10.1, 10.0, 10.1, 10.2, 25.0] # Spike at the end
    symbol = "BOOM_TEST"
    
    print(f"{'Ticks Since':<12} | {'Price':<8} | {'Z-Score':<8} | {'Is Spike':<8}")
    print("-" * 50)
    
    for i, price in enumerate(prices):
        tick = Tick(symbol=symbol, price=price, epoch=1700000000 + i)
        features = generator.process_tick(tick)
        
        print(f"{features['ticks_since_spike']:<12} | "
              f"{features['price']:<8} | "
              f"{features['z_score']:<8.2f} | "
              f"{features['is_spike']}")

if __name__ == "__main__":
    asyncio.run(test_features())
