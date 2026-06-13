from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

@dataclass
class ZoneResult:
    """Standardized output for the High Probability Zone framework."""
    symbol: str
    is_high_probability: bool
    confidence_score: float # 0.0 to 1.0
    active_factors: List[str] = field(default_factory=list)

class ZoneDetector(ABC):
    """Base class for all context-aware zone detectors."""
    @abstractmethod
    def evaluate(self, features: Dict[str, Any]) -> ZoneResult:
        pass

class HybridZoneDetector(ZoneDetector):
    """
    Combines Trend, Volatility, and Spike Context to score trading zones.
    """
    def __init__(self, confidence_threshold: float = 0.65):
        self.confidence_threshold = confidence_threshold

    def evaluate(self, features: Dict[str, Any]) -> ZoneResult:
        symbol = features.get("symbol", "UNKNOWN")
        confidence = 0.0
        factors = []
        
        # 1. Trend Filter (40% Weight)
        # We look for price being on the 'correct' side of EMA50
        price = features.get("price", 0.0)
        ema_50 = features.get("ema_50", 0.0)
        ma_50 = features.get("ma_50", 0.0)
        
        # Trend is 'Up' if price > ema_50, 'Down' if price < ema_50
        # For Boom/Crash, we prioritize the trend that favors the strategy
        # Here we just check for 'Strong Trend' (distance from MA)
        trend_dist = abs(price - ma_50) / ma_50 if ma_50 > 0 else 0
        if trend_dist > 0.001: # 0.1% deviation from MA
            confidence += 0.40
            factors.append("TREND_CONFIRMED")
            
        # 2. Volatility Gating (30% Weight)
        # Low return variance implies a stable "High Probability" zone
        ret_std = features.get("return_std", 1.0)
        avg_vol = features.get("avg_volatility", 1.0)
        if ret_std < avg_vol * 1.5: # Volatility is within 1.5x average
            confidence += 0.30
            factors.append("VOLATILITY_STABLE")
            
        # 3. Spike Recovery Context (30% Weight)
        # Poisson recovery: high prob if time since last spike is significant
        # or if we are in a 'cool down' period after a spike
        ticks_since = features.get("ticks_since_spike", 0)
        if ticks_since > 50: # Avoid the immediate chaos after a spike
            confidence += 0.30
            factors.append("SPIKE_COOLDOWN_COMPLETE")
            
        is_high_prob = confidence >= self.confidence_threshold
        
        return ZoneResult(
            symbol=symbol,
            is_high_probability=is_high_prob,
            confidence_score=round(confidence, 2),
            active_factors=factors
        )
