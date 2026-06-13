import csv
from features.indicators import FeatureGenerator
from analytics.probability import SpikeProbabilityModel
from strategy.strategies import HybridTradingStrategy
from models.trading import Tick

def test_hybrid_sim():
    symbol = "CRASH1000"
    print(f"--- Simulating Hybrid Strategy for {symbol} ---")
    
    # 1. Setup
    feature_gen = FeatureGenerator(window_size=100)
    prob_model = SpikeProbabilityModel(avg_ticks_between_spikes=1000)
    # Test with lax RSI to verify MA and Prob
    strategy = HybridTradingStrategy(symbol=symbol, prob_threshold=0.2, rsi_oversold=100.0)

    # 2. Run over CSV data
    csv_path = "ticks_data.csv"
    signals_found = 0
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
            prob_model.update(features)
            prob = prob_model.probability_of_spike(n_ticks=10)
            
            # Generate Signal
            signal = strategy.generate_signal(features, prob)
            
            if signal.action != "HOLD":
                signals_found += 1
                if signals_found <= 10:
                    print(f"[{signal.timestamp}] {signal.action} at {signal.price} | Conf: {signal.confidence} | RSI: {features['rsi_14']:.2f} | Risk: {signal.spike_risk:.2f}")

    print(f"\nSimulation complete. Total signals generated: {signals_found}")

if __name__ == "__main__":
    test_hybrid_sim()
