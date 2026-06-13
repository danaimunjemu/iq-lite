import csv
import logging
from features.indicators import FeatureGenerator
from strategy.filters import trend_filter
from models.trading import Tick, TradeSignal

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_trend_sim():
    # Use Crash 1000 for BUY testing
    # Use Boom 1000 for SELL testing
    symbols = ["CRASH1000", "BOOM1000"]
    print(f"--- Simulating Trend Filter for {symbols} ---")
    
    # 1. Setup
    feature_gen = FeatureGenerator(window_size=100)
    
    # Data Storage for History
    history = {s: {"price": [], "ma": []} for s in symbols}
    
    # 2. Run over CSV data
    csv_path = "ticks_data.csv"
    signals_processed = 0
    signals_passed = 0
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            s_name = row['symbol']
            if s_name not in symbols:
                continue
                
            tick = Tick(
                symbol=s_name,
                price=float(row['price']),
                epoch=int(row['epoch'])
            )
            
            # Process tick to get features
            features = feature_gen.process_tick(tick)
            ma_val = features.get("ema_50", 0.0)
            
            # Update history
            history[s_name]["price"].append(tick.price)
            history[s_name]["ma"].append(ma_val)
            
            # 3. Simulate a mock Signal periodically
            if len(history[s_name]["price"]) > 60:  # Need 50 for MA + 5 for lookback
                signals_processed += 1
                
                # Mock Signal
                action = "BUY" if "CRASH" in s_name else "SELL"
                mock_signal = TradeSignal(
                    symbol=s_name,
                    action=action,
                    price=tick.price,
                    epoch=tick.epoch,
                    probability=0.01, # Low risk
                    reason="Test Entry"
                )
                
                # Apply Filter
                passed = trend_filter(
                    signal=mock_signal,
                    price_history=history[s_name]["price"],
                    ma_history=history[s_name]["ma"],
                    lookback=5
                )
                
                if passed:
                    signals_passed += 1
                    if signals_passed % 200 == 0:
                        print(f"[{tick.timestamp}] Signal PASSED Filter for {s_name}: Price={tick.price:.2f} | MA={ma_val:.2f}")

    print(f"\nSimulation complete.")
    print(f"Total Signals Processed: {signals_processed}")
    print(f"Total Signals Passed: {signals_passed}")
    print(f"Total Signals Filtered: {signals_processed - signals_passed}")

if __name__ == "__main__":
    test_trend_sim()
