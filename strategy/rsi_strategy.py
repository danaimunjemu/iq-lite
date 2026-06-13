import logging
from enum import Enum
from typing import Dict, Any, Optional, List
from models.trading import TradeSignal
from features.zones import ZoneResult

logger = logging.getLogger(__name__)

class Side(Enum):
    BOOM = "BOOM"
    CRASH = "CRASH"

class State(Enum):
    IDLE = "IDLE"
    BREECHED = "BREECHED"

class RSISignalEngine:
    """
    State-aware RSI signal detector for Boom/Crash 1000.
    Logic:
    - Boom (Sell): RSI_MA crosses > 85 (Breeched), then back below 85 (Confirmed).
    - Crash (Buy): RSI_MA crosses < 15 (Breeched), then back above 15 (Confirmed).
    - ONLY emits signals if in a High Probability Zone.
    """
    def __init__(self, symbols: List[str]):
        self.states = {s: State.IDLE for s in symbols}
        self.threshold_high = 85.0
        self.threshold_low = 15.0

    def process_features(self, features: Dict[str, Any], zone: Optional[ZoneResult] = None) -> Optional[TradeSignal]:
        symbol = features.get("symbol")
        if symbol not in self.states:
            return None
            
        rsi_ma = features.get("rsi_ma_5", 50.0)
        current_state = self.states[symbol]
        price = features.get("price", 0.0)
        epoch = features.get("epoch", 0)
        
        signal = None
        
        # 1. Logic for Boom (Sell Signal)
        if "BOOM" in symbol.upper():
            if current_state == State.IDLE:
                if rsi_ma > self.threshold_high:
                    self.states[symbol] = State.BREECHED
                    logger.debug(f"[{symbol}] RSI_MA Breeched High (Sell Setup): {rsi_ma:.2f}")
            elif current_state == State.BREECHED:
                if rsi_ma < self.threshold_high:
                    # Confirmed Crossback
                    self.states[symbol] = State.IDLE # Reset to IDLE
                    
                    # Context Guard
                    if zone and zone.is_high_probability:
                        signal = TradeSignal(
                            symbol=symbol,
                            action="SELL",
                            price=price,
                            epoch=epoch,
                            probability=zone.confidence_score,
                            reason=f"RSI Crossback below {self.threshold_high} in High Prob Zone"
                        )
                        logger.info(f"[{symbol}] SELL Signal Confirmed (Zone Conf: {zone.confidence_score})")
                    else:
                        logger.info(f"[{symbol}] RSI Crossback ignored: Low Probability Zone")

        # 2. Logic for Crash (Buy Signal)
        elif "CRASH" in symbol.upper():
            if current_state == State.IDLE:
                if rsi_ma < self.threshold_low:
                    self.states[symbol] = State.BREECHED
                    logger.debug(f"[{symbol}] RSI_MA Breeched Low (Buy Setup): {rsi_ma:.2f}")
            elif current_state == State.BREECHED:
                if rsi_ma > self.threshold_low:
                    # Confirmed Crossback
                    self.states[symbol] = State.IDLE # Reset to IDLE
                    
                    # Context Guard
                    if zone and zone.is_high_probability:
                        signal = TradeSignal(
                            symbol=symbol,
                            action="BUY",
                            price=price,
                            epoch=epoch,
                            probability=zone.confidence_score,
                            reason=f"RSI Crossback above {self.threshold_low} in High Prob Zone"
                        )
                        logger.info(f"[{symbol}] BUY Signal Confirmed (Zone Conf: {zone.confidence_score})")
                    else:
                        logger.info(f"[{symbol}] RSI Crossback ignored: Low Probability Zone")

        return signal
