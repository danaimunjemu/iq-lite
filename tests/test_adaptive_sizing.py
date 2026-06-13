import logging
from models.bankroll import BankrollManager

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_adaptive_sizing():
    print("--- Testing Adaptive Position Sizing ---")
    
    # 1. Setup
    manager = BankrollManager(initial_balance=1000.0, risk_per_trade=0.01) # 1% = $10
    entry = 5400.0
    sl = 5390.0 # $10 distance
    
    # CASE A: Perfect Safety (0.0 prob)
    # Risk = $10, Size = 10 / 10 = 1.0
    size_a = manager.calculate_position_size(entry, sl, spike_prob=0.0, prob_threshold=0.20)
    print(f"CASE A (0% Prob): Lot Size = {size_a}")
    
    # CASE B: Moderate Risk (0.10 prob / 0.20 threshold = 50% risk)
    # Risk = $5, Size = 5 / 10 = 0.5
    size_b = manager.calculate_position_size(entry, sl, spike_prob=0.10, prob_threshold=0.20)
    print(f"CASE B (10% Prob): Lot Size = {size_b}")
    
    # CASE C: High Risk (0.15 prob / 0.20 threshold = 25% risk)
    # Risk = $2.5, Size = 2.5 / 10 = 0.25
    size_c = manager.calculate_position_size(entry, sl, spike_prob=0.15, prob_threshold=0.20)
    print(f"CASE C (15% Prob): Lot Size = {size_c}")
    
    # CASE D: Unsafe (0.21 prob)
    # Lot Size = 0.0
    size_d = manager.calculate_position_size(entry, sl, spike_prob=0.21, prob_threshold=0.20)
    print(f"CASE D (21% Prob): Lot Size = {size_d}")
    
    # Assertions
    assert size_a == 1.0, f"Expected 1.0, got {size_a}"
    assert size_b == 0.5, f"Expected 0.5, got {size_b}"
    assert size_c == 0.25, f"Expected 0.25, got {size_c}"
    assert size_d == 0.0, f"Expected 0.0, got {size_d}"
    
    print("\nAll adaptive sizing tests passed!")

if __name__ == "__main__":
    test_adaptive_sizing()
