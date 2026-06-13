import csv
from models.trading import Tick
from features.indicators import FeatureGenerator
from analytics.probability import SpikeProbabilityModel
from strategy.base_strategy import TradingSignalGenerator

def run_simulation(symbol: str, csv_path: str):
    print(f"--- Simulating Signals for {symbol} ---")
    
    # Initialize components
    feature_gen = FeatureGenerator(window_size=50)
    prob_model = SpikeProbabilityModel(avg_ticks_between_spikes=1000)
    signal_gen = TradingSignalGenerator(symbol, prob_threshold=0.15, tp_amount=0.5, sl_amount=2.0)
    
    active_trade = None
    
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
            
            # 1. Generate Features
            features = feature_gen.process_tick(tick)
            
            # 2. Update Probability
            prob_model.update(features)
            prob = prob_model.probability_of_spike(n_ticks=10)
            
            # 3. Handle Active Trade
            if active_trade:
                exit_reason = signal_gen.check_exit(
                    entry_price=active_trade['entry_price'],
                    current_price=tick.price,
                    probability=prob
                )
                if exit_reason:
                    profit = 0
                    if symbol.startswith("CRASH"):
                        profit = tick.price - active_trade['entry_price']
                    else:
                        profit = active_trade['entry_price'] - tick.price
                        
                    print(f"[{tick.timestamp}] EXIT {active_trade['action']} at {tick.price:.3f} | Reason: {exit_reason} | Profit: {profit:.4f}")
                    active_trade = None
            
            # 4. Generate Signal (if no active trade)
            if not active_trade:
                signal = signal_gen.generate_signal(features, prob)
                if signal.action != "HOLD":
                    print(f"[{tick.timestamp}] SIGNAL: {signal.action} at {tick.price:.3f} | Prob: {prob:.4f} | {signal.reason}")
                    active_trade = {
                        'action': signal.action,
                        'entry_price': tick.price,
                        'timestamp': tick.timestamp
                    }

if __name__ == "__main__":
    # Test with CRASH1000
    run_simulation("CRASH1000", "ticks_data.csv")
