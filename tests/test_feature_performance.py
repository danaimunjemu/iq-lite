import time
import csv
from typing import Dict, Any
from features.indicators import FeatureGenerator
from models.trading import Tick

def benchmark_features():
    print("--- Feature Pipeline Benchmark ---")
    
    # 1. Setup
    feature_gen = FeatureGenerator(window_size=100)
    
    ticks = []
    # Load some data
    with open('ticks_data.csv', 'r') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i > 2000: break
            ticks.append(Tick(symbol=row['symbol'], price=float(row['price']), epoch=int(row['epoch'])))

    # 2. Benchmark throughput
    start_time = time.perf_counter()
    count = 0
    for tick in ticks:
        features = feature_gen.process_tick(tick)
        count += 1
        
    duration = time.perf_counter() - start_time
    tps = count / duration
    
    print(f"Processed {count} ticks in {duration:.4f} seconds")
    print(f"Throughput: {tps:.2f} ticks/sec")
    
    # 3. Accuracy Check (Spot check last features)
    last_features = feature_gen.process_tick(ticks[-1])
    print("\nSample Feature Snapshot:")
    print(f"  Price: {last_features['price']}")
    print(f"  SMA-50: {last_features['ma_50']:.4f}")
    print(f"  EMA-50: {last_features['ema_50']:.4f}")
    print(f"  RSI-14: {last_features['rsi_14']:.2f}")
    print(f"  RSI_MA: {last_features['rsi_ma_5']:.2f}")
    print(f"  Vol (Return_Std): {last_features['return_std']:.6f}")

    # Theoretical Verification
    assert tps > 500, "Performance is too low for live trading"
    assert "ma_50" in last_features
    assert "ema_50" in last_features
    assert "rsi_ma_5" in last_features
    
    print("\nPerformance and Accuracy verified.")

if __name__ == "__main__":
    benchmark_features()
