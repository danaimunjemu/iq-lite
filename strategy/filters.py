import logging
from typing import List, Dict, Any, Union
from models.trading import TradeSignal
from analytics.probability import probability_of_spike

logger = logging.getLogger(__name__)

def trend_filter(
    signal: TradeSignal, 
    price_history: List[float], 
    ma_history: List[float], 
    lookback: int = 5,
    use_ema: bool = True
) -> bool:
    """
    Directional trend filter for Boom/Crash trades.
    
    Rules:
    - Crash 1000: Only BUY if Price > MA consistently for 'lookback' ticks.
    - Boom 1000: Only SELL if Price < MA consistently for 'lookback' ticks.
    """
    if len(price_history) < lookback or len(ma_history) < lookback:
        logger.debug(f"Trend filter: not enough history ({len(price_history)})")
        return False
        
    recent_prices = price_history[-lookback:]
    recent_mas = ma_history[-lookback:]
    
    symbol = signal.symbol.upper()
    action = signal.action.upper()
    
    if action == "HOLD":
        return True
        
    # 1. Crash 1000 (BUY Drift)
    if "CRASH" in symbol:
        if action == "BUY":
            # All recent prices must be above their respective MA values
            is_confirmed = all(p > m for p, m in zip(recent_prices, recent_mas))
            if not is_confirmed:
                logger.debug(f"[{symbol}] BUY rejected: price not consistently above MA{lookback}")
            return is_confirmed
            
    # 2. Boom 1000 (SELL Drift)
    elif "BOOM" in symbol:
        if action == "SELL":
            # All recent prices must be below their respective MA values
            is_confirmed = all(p < m for p, m in zip(recent_prices, recent_mas))
            if not is_confirmed:
                logger.debug(f"[{symbol}] SELL rejected: price not consistently below MA{lookback}")
            return is_confirmed
            
    # Default to True for other symbols or if no specific rule matches
    return True

def volatility_filter(
    current_std: float, 
    avg_volatility: float, 
    multiplier: float = 2.0
) -> bool:
    """
    Blocks trades when the current return-based standard deviation 
    is significantly higher than the baseline volatility.
    """
    if avg_volatility == 0:
        return True # Avoid blocking everything if we don't have enough data
        
    threshold = avg_volatility * multiplier
    is_safe = current_std <= threshold
    
    if not is_safe:
        logger.debug(f"Volatility filter: Rejected (Current={current_std:.6f} > Limit={threshold:.6f})")
        
    return is_safe

def is_trade_safe(
    context: Dict[str, Any], 
    holding_time: int = 20, 
    prob_threshold: float = 0.20
) -> bool:
    """
    Final Safety Gate: Projects risk over the trade's expected duration.
    
    Checks:
    1. Spike Survival: Prob(spike in next N ticks) < threshold.
    2. Overdue Pressure: Ticks since spike < 1.5x average.
    """
    ticks_since = context.get("ticks_since_spike", 0)
    
    # 1. Overdue Pressure Check (Statistically High Risk Zone)
    if ticks_since > 1500:
        logger.debug(f"Spike filter: Rejected (Index overdue: {ticks_since} ticks)")
        return False
        
    # 2. Probability Survival Check
    prob = probability_of_spike(holding_time, context)
    if prob > prob_threshold:
        logger.debug(f"Spike filter: Rejected (Prob {prob:.2f} > Threshold {prob_threshold:.2f})")
        return False
        
    return True
