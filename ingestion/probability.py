import math
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class SpikeProbabilityModel:
    """Estimates the probability of a spike occurring within the next N ticks."""
    def __init__(self, avg_ticks_between_spikes: int = 1000):
        # Base rate (lambda per tick)
        self.base_lambda = 1.0 / avg_ticks_between_spikes
        self.avg_gap = avg_ticks_between_spikes
        
        # State for adjustments
        self.current_adj_lambda = self.base_lambda
        self.last_features: Dict[str, Any] = {}

    def update(self, features: Dict[str, Any]):
        """
        Updates the internal state and adjusts lambda based on current features.
        Required features: 'z_score', 'ticks_since_spike', 'volatility', 'momentum'
        """
        self.last_features = features
        
        z_score = abs(features.get("z_score", 0))
        ticks_since = features.get("ticks_since_spike", 0)
        volatility = features.get("volatility", 0)
        momentum = features.get("momentum", 0)
        symbol = features.get("symbol", "").upper()

        # 1. Time Adjustment Factor (f_time)
        # Pressure increases as we approach the average gap
        f_time = 1.0 + (ticks_since / self.avg_gap)
        
        # 2. Volatility Adjustment Factor (f_vol)
        # High Z-score / volatility often precedes a spike
        f_vol = 1.0 + (z_score * 0.2) + (volatility * 10.0)
        
        # 3. Momentum Adjustment Factor (f_moment)
        # Check if price is moving in the 'correct' direction for the index type
        f_moment = 1.0
        if "BOOM" in symbol and momentum > 0:
            f_moment = 1.2
        elif "CRASH" in symbol and momentum < 0:
            f_moment = 1.2

        # Final Adjusted Lambda
        self.current_adj_lambda = self.base_lambda * f_time * f_vol * f_moment
        
        # Cap to avoid unrealistically high probabilities per tick
        self.current_adj_lambda = min(self.current_adj_lambda, 0.1)

    def probability_of_spike(self, n_ticks: int) -> float:
        """
        Calculates P(X >= 1) for the next N ticks using the adjusted Poisson rate.
        P = 1 - e^(-lambda * N)
        """
        if n_ticks <= 0:
            return 0.0
            
        prob = 1.0 - math.exp(-self.current_adj_lambda * n_ticks)
        return round(prob, 4)

    def get_summary(self, n_ticks: int = 10) -> Dict[str, Any]:
        """Provides a human-readable summary of the current forecast."""
        prob = self.probability_of_spike(n_ticks)
        
        risk_level = "Low"
        if prob > 0.4: risk_level = "Medium"
        if prob > 0.7: risk_level = "High"
        if prob > 0.9: risk_level = "Extreme"
        
        return {
            "n_ticks": n_ticks,
            "probability": prob,
            "risk_level": risk_level,
            "current_rate": round(self.current_adj_lambda, 6),
            "ticks_since_last": self.last_features.get("ticks_since_spike", 0)
        }
