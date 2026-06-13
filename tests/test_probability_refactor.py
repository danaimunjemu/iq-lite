import logging
from analytics.probability import probability_of_spike, SpikeProbabilityModel

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_probability_refactor():
    print("--- Testing Spike Probability Refactor ---")
    
    # 1. Base Case (Just after spike, calm, neutral momentum)
    ctx_base = {
        "ticks_since_spike": 10,
        "return_std": 0.0001,
        "avg_volatility": 0.0001,
        "momentum": 0.0,
        "symbol": "CRASH1000"
    }
    
    prob_base = probability_of_spike(10, ctx_base)
    print(f"Base Case (10 ticks since spike): {prob_base}")
    
    # 2. Overdue Case (2000 ticks since spike)
    ctx_overdue = ctx_base.copy()
    ctx_overdue["ticks_since_spike"] = 2000
    prob_overdue = probability_of_spike(10, ctx_overdue)
    print(f"Overdue Case (2000 ticks since spike): {prob_overdue}")
    
    # 3. Volatility Case (High return_std)
    ctx_vol = ctx_base.copy()
    ctx_vol["return_std"] = 0.0005 # 5x average
    prob_vol = probability_of_spike(10, ctx_vol)
    print(f"Volatile Case (5x avg volatility): {prob_vol}")
    
    # 4. Momentum Case (Downward for Crash)
    ctx_mom = ctx_base.copy()
    ctx_mom["momentum"] = -1.5 # Negative for Crash
    prob_mom = probability_of_spike(10, ctx_mom)
    print(f"Negative Momentum Case (Crash Trend): {prob_mom}")
    
    # 5. Combined Case (Extreme Pressure)
    ctx_ext = {
        "ticks_since_spike": 1500,
        "return_std": 0.0008,
        "avg_volatility": 0.0001,
        "momentum": -2.0,
        "symbol": "CRASH1000"
    }
    prob_ext = probability_of_spike(10, ctx_ext)
    print(f"Combined Extreme Case: {prob_ext}")
    
    # Assertion Checks
    assert prob_overdue > prob_base, "Probability should increase as time passes"
    assert prob_vol > prob_base, "Probability should increase with volatility"
    assert prob_mom > prob_base, "Probability should increase with directional momentum"
    assert prob_ext > prob_overdue, "Combined factors should result in higher probability"
    assert 0 <= prob_ext <= 1.0, "Probability must be between 0 and 1"

    print("\nAll probability refactor tests passed!")

if __name__ == "__main__":
    test_probability_refactor()
