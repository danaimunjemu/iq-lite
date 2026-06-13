import math
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

def probability_of_spike(n_ticks: int, context: Dict[str, Any]) -> float:
    """
    Calculates the probability of at least one spike in the next N ticks.
    
    Formula: P = 1 - e^(-lambda_eff * n_ticks)
    
    Context Keys:
    - ticks_since_spike: int (default 0)
    - return_std: float (current volatility, default 0.0)
    - avg_volatility: float (baseline volatility, default 0.0001)
    - momentum: float (recent price trend, default 0.0)
    - symbol: str (e.g., 'CRASH1000' or 'BOOM1000')
    """
    base_lambda = 0.001  # 1/1000 for Crash/Boom 1000
    
    ticks_since = context.get("ticks_since_spike", 0)
    curr_vol = context.get("return_std", 0.0)
    avg_vol = context.get("avg_volatility", 0.0001)
    mom = context.get("momentum", 0.0)
    symbol = context.get("symbol", "").upper()

    # 1. Time Factor (Pressure build-up)
    # Reaches 2.0x base at 1000 ticks since last spike
    f_time = 1.0 + (ticks_since / 1000.0)
    
    # 2. Volatility Factor (Instability)
    # Baseline ratio (e.g. 2.0 if curr_vol is twice the avg)
    vol_ratio = (curr_vol / avg_vol) if avg_vol > 0 else 1.0
    f_vol = 1.0 + (vol_ratio * 0.5)
    
    # 3. Momentum Factor (Directional Bias)
    f_mom = 1.0
    if "CRASH" in symbol and mom < 0:
        # Downward momentum increases crash probability
        f_mom = 1.5
    elif "BOOM" in symbol and mom > 0:
        # Upward momentum increases boom probability
        f_mom = 1.5

    # Calculate Effective Lambda
    lambda_eff = base_lambda * f_time * f_vol * f_mom
    
    # Safety cap (max probability of 0.1 per tick)
    lambda_eff = min(lambda_eff, 0.1)
    
    prob = 1.0 - math.exp(-lambda_eff * n_ticks)
    return round(prob, 4)

class SpikeProbabilityModel:
    """Refactored Spike Probability Engine."""
    def __init__(self, avg_ticks_between_spikes: int = 1000):
        self.avg_gap = avg_ticks_between_spikes
        self.context: Dict[str, Any] = {}

    def update(self, features: Dict[str, Any]):
        """Store the latest context features."""
        self.context = features

    def calculate(self, n_ticks: int = 10) -> float:
        """Call the standalone probability function with saved context."""
        return probability_of_spike(n_ticks, self.context)

    def get_summary(self, n_ticks: int = 10) -> Dict[str, Any]:
        prob = self.calculate(n_ticks)
        return {
            "n_ticks": n_ticks,
            "probability": prob,
            "risk_level": self._get_risk_level(prob),
            "ticks_since": self.context.get("ticks_since_spike", 0)
        }

    def _get_risk_level(self, prob: float) -> str:
        if prob < 0.1: return "Low"
        if prob < 0.3: return "Medium"
        if prob < 0.5: return "High"
        return "Extreme"
