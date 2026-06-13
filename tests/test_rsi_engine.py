import csv
import logging
from features.indicators import FeatureGenerator
from ingestion.rsi_engine import RSISignalEngine, State
from models.trading import Tick

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_rsi_sim():
    # Use Crash 1000 for Buy testing
    symbol = "CRASH1000"
    print(f"--- Simulating RSI Signal Engine for {symbol} ---")
    
    # 1. Setup
    feature_gen = FeatureGenerator(window_size=100)
    # Thresholds are 15/85
    engine = RSISignalEngine(symbols=[symbol])

    # 2. Run over CSV data
    csv_path = "ticks_data.csv"
    signals_found = 0
    ticks_processed = 0
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
            
            # Detect Signal
            signal = engine.process_features(features)
            
            if signal:
                signals_found += 1
                print(f"[{signal.timestamp}] {signal.action} Confirmed at {signal.price} | Reason: {signal.reason}")

            ticks_processed += 1
            if ticks_processed % 500 == 0:
                print(f"  Processed {ticks_processed} ticks... RSI_MA={features.get('rsi_ma_5', 50.0):.2f} | State={engine.states[symbol].name}")

    print(f"\nSimulation complete. Total signals generated: {signals_found}")

if __name__ == "__main__":
    test_rsi_sim()
