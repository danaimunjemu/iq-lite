import logging
from datetime import datetime
from typing import Dict, Any, List
from models.trading import BankrollState

logger = logging.getLogger(__name__)

class BankrollManager:
    """
    Manages trading capital using poker-style bankroll management.
    Ensures risk is limited to a fixed percentage of current balance.
    """
    def __init__(self, initial_balance: float = 1000.0, risk_per_trade: float = 0.01):
        self.balance = initial_balance
        self.risk_per_trade = risk_per_trade  # e.g., 0.01 = 1%
        self.history: List[BankrollState] = []
        
        # Track initial state
        self._record_state()

    def _record_state(self):
        state = BankrollState(
            balance=self.balance,
            equity=self.balance,  # Simplified: equity = balance for now
            risk_amount=self.balance * self.risk_per_trade,
            timestamp=datetime.now()
        )
        self.history.append(state)

    def calculate_position_size(
        self, 
        entry_price: float, 
        sl_price: float, 
        spike_prob: float = 0.0,
        prob_threshold: float = 0.20
    ) -> float:
        """
        Calculates ADAPTIVE lot size based on probability and SL distance.
        The risk multiplier scales linearly as probability approaches the threshold.
        """
        if spike_prob >= prob_threshold:
            logger.info(f"Position sizing: Unsafe risk ({spike_prob:.2f} >= {prob_threshold:.2f}). LOT SIZE 0.0")
            return 0.0
            
        sl_distance = abs(entry_price - sl_price)
        if sl_distance == 0:
            logger.warning("Stop loss distance is zero. Cannot calculate size.")
            return 0.0
            
        # 1. Base Risk Amount
        base_risk_amount = self.balance * self.risk_per_trade
        
        # 2. Risk Multiplier (Scales inversely with probability)
        # Multiplier = (threshold - current) / threshold
        # e.g. (20-10)/20 = 0.5 (Half Risk)
        risk_multiplier = (prob_threshold - spike_prob) / prob_threshold
        
        effective_risk_amount = base_risk_amount * max(0, risk_multiplier)
        
        # 3. Position Size Calculation
        position_size = effective_risk_amount / sl_distance
        
        # Round to 2 decimal places for practicality
        return round(position_size, 2)

    def update_balance(self, pnl: float):
        """
        Updates the balance after a trade and records the new state.
        """
        self.balance += pnl
        self._record_state()
        logger.info(f"Balance updated: {self.balance:.2f} (PnL: {pnl:+.2f})")

    def get_summary(self) -> Dict[str, Any]:
        """
        Returns a summary of the current bankroll status.
        """
        if not self.history:
            return {}
            
        initial = self.history[0].balance
        current = self.balance
        total_profit = current - initial
        return {
            "current_balance": round(current, 2),
            "initial_balance": round(initial, 2),
            "total_profit": round(total_profit, 2),
            "profit_percent": round((total_profit / initial) * 100, 2),
            "risk_per_trade_amount": round(current * self.risk_per_trade, 2),
            "trade_count": len(self.history) - 1
        }
