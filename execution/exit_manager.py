import logging
from typing import Dict, Any, Tuple, Optional
from models.trading import TradeSignal

logger = logging.getLogger(__name__)

class TradeExitManager:
    """
    Manages active trade states and evaluates exit conditions based on
    Duration, Dynamic Risk (Spike Prob), and Momentum (RSI).
    """
    def __init__(self, max_ticks: int = 50, risk_threshold: float = 0.35):
        self.max_ticks = max_ticks
        self.risk_threshold = risk_threshold
        # Tracks {symbol: {entry_epoch, entry_rsi, action, ticks_elapsed}}
        self.active_trades: Dict[str, Dict[str, Any]] = {}

    def register_trade(self, signal: TradeSignal, current_rsi: float):
        """Registers a new trade to be monitored."""
        self.active_trades[signal.symbol] = {
            "entry_epoch": signal.epoch,
            "entry_rsi": current_rsi,
            "action": signal.action, # BUY or SELL
            "ticks_elapsed": 0
        }
        logger.info(f"[{signal.symbol}] Monitoring trade exit for {signal.action} (Entry RSI: {current_rsi:.2f})")

    def evaluate_exit(self, symbol: str, features: Dict[str, Any]) -> Optional[str]:
        """
        Evaluates if an active trade should be closed based on multiple criteria.
        Returns the reason for exit if True, else None.
        """
        if symbol not in self.active_trades:
            return None
            
        trade = self.active_trades[symbol]
        trade["ticks_elapsed"] += 1
        
        current_rsi = features.get("rsi_14", 50.0)
        spike_prob = features.get("spike_risk", 0.0)
        
        # 1. Max Duration Check
        if trade["ticks_elapsed"] >= self.max_ticks:
            self.close_trade(symbol)
            return f"Max duration reached ({self.max_ticks} ticks)"
            
        # 2. Dynamic Risk Check (Spike Probability Surge)
        if spike_prob >= self.risk_threshold:
            self.close_trade(symbol)
            return f"Emergency Exit: High Spike Risk ({spike_prob:.2f} >= {self.risk_threshold:.2f})"
            
        # 3. Momentum Exhaustion Check (RSI Reversal)
        # For Crash (BUY): Exit if RSI reaches 70 (Overbought)
        # For Boom (SELL): Exit if RSI reaches 30 (Oversold)
        if trade["action"] == "BUY" and current_rsi >= 70:
            self.close_trade(symbol)
            return f"Momentum Exhaustion: RSI Overbought ({current_rsi:.2f})"
        elif trade["action"] == "SELL" and current_rsi <= 30:
            self.close_trade(symbol)
            return f"Momentum Exhaustion: RSI Oversold ({current_rsi:.2f})"
            
        return None

    def close_trade(self, symbol: str):
        """Clears the trade state for a symbol."""
        if symbol in self.active_trades:
            del self.active_trades[symbol]
            logger.info(f"[{symbol}] Trade monitoring stopped (Closed).")
