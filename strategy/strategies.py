import logging
from typing import Dict, Any, Optional
from models.trading import TradeSignal

logger = logging.getLogger(__name__)

class HybridTradingStrategy:
    """
    Hybrid Trading Strategy for Crash/Boom indices.
    Combines: 
    1. Trend filtering (SMA 50)
    2. Entry timing (RSI 14)
    3. Risk management (Spike Probability)
    """
    def __init__(
        self, 
        symbol: str, 
        prob_threshold: float = 0.2, 
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0
    ):
        self.symbol = symbol.upper()
        self.prob_threshold = prob_threshold
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        
        if "CRASH" in self.symbol:
            self.index_type = "CRASH"
            self.drift_action = "BUY"
        elif "BOOM" in self.symbol:
            self.index_type = "BOOM"
            self.drift_action = "SELL"
        else:
            self.index_type = "UNKNOWN"
            self.drift_action = "HOLD"

    def calculate_confidence(self, rsi: float, prob: float) -> float:
        """
        Calculates a confidence score (0.0 to 1.0) based on RSI depth 
        and safety margin from the spike probability threshold.
        """
        # 1. Probability Safety Margin (0.0 - 0.5)
        # Margin is higher when prob is further below threshold
        prob_margin = max(0, self.prob_threshold - prob) / self.prob_threshold
        prob_score = prob_margin * 0.5
        
        # 2. RSI Depth Score (0.0 - 0.5)
        rsi_score = 0.0
        if self.index_type == "CRASH" and rsi < self.rsi_oversold:
            # More oversold = higher confidence
            rsi_score = (self.rsi_oversold - rsi) / self.rsi_oversold * 0.5
        elif self.index_type == "BOOM" and rsi > self.rsi_overbought:
            # More overbought = higher confidence
            rsi_score = (rsi - self.rsi_overbought) / (100 - self.rsi_overbought) * 0.5
            
        return round(min(1.0, prob_score + rsi_score), 4)

    def generate_signal(self, features: Dict[str, Any], probability: float) -> TradeSignal:
        price = features.get("price", 0.0)
        epoch = features.get("epoch", 0)
        ma_50 = features.get("ma_50", 0.0)
        rsi_14 = features.get("rsi_14", 50.0)
        
        # Modular Checks
        is_trend_ok = False
        is_timing_ok = False
        is_risk_ok = (probability < self.prob_threshold)
        
        # 1. Trend Filter
        if self.index_type == "CRASH":
            is_trend_ok = (price > ma_50)
        elif self.index_type == "BOOM":
            is_trend_ok = (price < ma_50)
            
        # 2. Entry Timing
        if self.index_type == "CRASH":
            is_timing_ok = (rsi_14 < self.rsi_oversold)
        elif self.index_type == "BOOM":
            is_timing_ok = (rsi_14 > self.rsi_overbought)

        # Signal Logic
        action = "HOLD"
        reason_parts = []
        
        if not is_risk_ok: reason_parts.append(f"High risk ({probability:.2f})")
        if not is_trend_ok: reason_parts.append(f"Trend filtered (MA50={ma_50:.2f})")
        if not is_timing_ok: reason_parts.append(f"Timing wait (RSI={rsi_14:.1f})")
        
        confidence = 0.0
        if is_risk_ok and is_trend_ok and is_timing_ok:
            action = self.drift_action
            confidence = self.calculate_confidence(rsi_14, probability)
            reason_parts.append("Hybrid criteria met")
            
        return TradeSignal(
            symbol=self.symbol,
            action=action,
            price=price,
            epoch=epoch,
            probability=probability,
            reason=" | ".join(reason_parts),
            confidence=confidence,
            spike_risk=probability
        )
