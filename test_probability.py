import asyncio
import json
from ingestion.probability import SpikeProbabilityModel

def test_probability():
    # Avg gap of 500 ticks for a hypothetical index
    model = SpikeProbabilityModel(avg_ticks_between_spikes=500)
    
    scenarios = [
        {"name": "Fresh State (No Volatility, Just Spiked)", 
         "features": {"z_score": 0.1, "ticks_since_spike": 1, "volatility": 0.001, "symbol": "BOOM 1000", "momentum": 0}},
        
        {"name": "Building Pressure (Halfway to Avg Gap)", 
         "features": {"z_score": 0.5, "ticks_since_spike": 250, "volatility": 0.002, "symbol": "BOOM 1000", "momentum": 0.1}},
        
        {"name": "High Pressure (Overdue + Volatility)", 
         "features": {"z_score": 2.5, "ticks_since_spike": 600, "volatility": 0.005, "symbol": "BOOM 1000", "momentum": 0.5}},
    ]

    print(f"{'Scenario':<40} | {'P(10 ticks)':<12} | {'Risk Level'}")
    print("-" * 70)

    for s in scenarios:
        model.update(s["features"])
        summary = model.get_summary(n_ticks=10)
        print(f"{s['name']:<40} | {summary['probability']:<12.2%} | {summary['risk_level']}")

if __name__ == "__main__":
    test_probability()
