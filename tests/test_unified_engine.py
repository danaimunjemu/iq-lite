import csv
import logging
from strategy.base_strategy import UnifiedSignalEngine
from models.trading import Tick

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_unified_engine_sim():
    symbols = ["CRASH1000", "BOOM1000"]
    print(f"--- Simulating Unified Signal Engine for {symbols} ---")
    
    # 1. Setup
    engine = UnifiedSignalEngine(symbols=symbols, window_size=100)
    
    # 2. Run over CSV data
    csv_path = "ticks_data.csv"
    signals_generated = 0
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if row['symbol'] not in symbols:
                continue
                
            tick = Tick(
                symbol=row['symbol'],
                price=float(row['price']),
                epoch=int(row['epoch'])
            )
            
            # Process tick through the entire pipeline
            signal = engine.process_tick(tick)
            
            if signal:
                signals_generated += 1
                print(f"\n[SIGNAL {signals_generated}] {signal.symbol} | {signal.action} @ {signal.price}")
                print(f"  Confidence: {signal.confidence:.2f}")
                print(f"  Spike Risk: {signal.spike_risk:.4f}")
                print(f"  Reason: {signal.reason}")
                
            if signals_generated >= 5: # Limit for test output
                break

    print(f"\nSimulation complete.")
    print(f"Total Unified Signals Generated: {signals_generated}")

if __name__ == "__main__":
    test_unified_engine_sim()
