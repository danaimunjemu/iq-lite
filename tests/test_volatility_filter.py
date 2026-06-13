import csv
import logging
from features.indicators import FeatureGenerator
from strategy.filters import volatility_filter
from models.trading import Tick

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_volatility_sim():
    symbol = "CRASH1000"
    print(f"--- Simulating Volatility Filter for {symbol} ---")
    
    # 1. Setup
    feature_gen = FeatureGenerator(window_size=100)
    
    # 2. Run over CSV data
    csv_path = "ticks_data.csv"
    ticks_processed = 0
    blocks_found = 0
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['symbol'] != symbol:
                continue
                
            tick = Tick(
                symbol=row['symbol'],
                price=float(row['price']),
                epoch=int(row['epoch'])
            )
            
            # Process tick
            features = feature_gen.process_tick(tick)
            
            # Current Volatility vs Avg
            curr_std = features.get("return_std", 0.0)
            avg_vol = features.get("avg_volatility", 0.0)
            
            # Check Filter (Multiplier = 3.0 for better sensitivity check)
            is_safe = volatility_filter(curr_std, avg_vol, multiplier=3.0)
            
            if not is_safe:
                blocks_found += 1
                if blocks_found % 50 == 0:
                    print(f"[{tick.timestamp}] BLOCKED entry: Vol={curr_std:.6f} > Avg={avg_vol:.6f}")

            ticks_processed += 1

    print(f"\nSimulation complete.")
    print(f"Total Ticks Processed: {ticks_processed}")
    print(f"Total Blocked Windows: {blocks_found}")

if __name__ == "__main__":
    test_volatility_sim()
