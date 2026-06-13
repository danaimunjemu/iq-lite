import math
from models.bankroll import BankrollManager

def simulate_trades():
    print("--- Poker-Style Bankroll Management Simulation ---")
    
    # 1. Initialize with $10,000 and 2% risk
    manager = BankrollManager(initial_balance=10000, risk_per_trade=0.02)
    print(f"Initial Balance: ${manager.balance}")
    print(f"Risk Per Trade: {manager.risk_per_trade * 100}% (${manager.balance * manager.risk_per_trade})\n")

    # 2. Winning Streak Scenario
    print("Scenario 1: 5 Consecutive Wins (Reward:Risk = 2:1)")
    sl_distance = 1.0  # SL is 1.0 points away
    for i in range(5):
        size = manager.calculate_position_size(entry_price=10.0, sl_price=9.0)
        risk_amount = manager.balance * manager.risk_per_trade
        # Profit = 2 * Risk (Reward:Risk = 2:1)
        profit = 2 * risk_amount
        manager.update_balance(profit)
        print(f"  Win {i+1}: Size={size} | New Balance=${manager.balance:.2f} | New Risk=${manager.balance * manager.risk_per_trade:.2f}")

    # 3. Losing Streak Scenario
    print("\nScenario 2: 5 Consecutive Losses")
    for i in range(5):
        size = manager.calculate_position_size(entry_price=10.0, sl_price=9.0)
        risk_amount = - (manager.balance * manager.risk_per_trade)
        manager.update_balance(risk_amount)
        print(f"  Loss {i+1}: Size={size} | New Balance=${manager.balance:.2f} | New Risk=${manager.balance * manager.risk_per_trade:.2f}")

    # 4. Final Summary
    summary = manager.get_summary()
    print("\n--- Final Summary ---")
    for k, v in summary.items():
        print(f"{k.replace('_', ' ').title()}: {v}")

if __name__ == "__main__":
    simulate_trades()
