import logging
from typing import List, Optional, Dict, Any
from models.trading import Position, TradeSignal, Tick

logger = logging.getLogger(__name__)

class PyramidingEngine:
    """
    Handles position scaling (pyramiding) for a trading system.
    Rules:
    - Add to winners (Total Unrealized PnL > 0)
    - Align with Trend (Price vs MA50)
    - Diminishing Size (Each new scale-in is smaller)
    - Max Positions Cap
    """
    def __init__(self, max_positions: int = 4, scale_factor: float = 0.5):
        self.max_positions = max_positions
        self.scale_factor = scale_factor

    def scale_position(self, 
                       symbol: str, 
                       tick: Tick, 
                       existing_positions: List[Position], 
                       features: Dict[str, Any]) -> Optional[TradeSignal]:
        """
        Calculates if a new scaling position should be opened.
        """
        # 1. Filter positions for this symbol
        symbol_positions = [p for p in existing_positions if p.symbol == symbol]
        if not symbol_positions:
            return None
            
        # 2. Check Constraints
        if len(symbol_positions) >= self.max_positions:
            logger.debug(f"[{symbol}] Max positions ({self.max_positions}) reached. Skipping scale-in.")
            return None

        # 3. Analyze Side and Trend alignment
        # All positions for a single symbol should be on the same side in this strategy
        side = symbol_positions[0].side.upper()
        price = tick.price
        ma_50 = features.get("ma_50", 0.0)
        
        if side == "BUY" and price < ma_50:
            logger.debug(f"[{symbol}] Price below MA50. Skipping BUY scale-in.")
            return None
        elif side == "SELL" and price > ma_50:
            logger.debug(f"[{symbol}] Price above MA50. Skipping SELL scale-in.")
            return None

        # 4. Check Unrealized PnL (Must be profitable)
        total_pnl = sum(p.get_unrealized_pnl(price) for p in symbol_positions)
        if total_pnl <= 0:
            logger.debug(f"[{symbol}] PnL is negative ({total_pnl:.2f}). Skipping scale-in.")
            return None

        # 5. Risk Filter (Spike Risk)
        # We reuse the prob logic from features
        spike_risk = features.get("spike_risk", 0.0) # Provided by Signal Engine or similar
        if spike_risk > 0.20:
            logger.debug(f"[{symbol}] Spike risk too high ({spike_risk:.2f}). Skipping scale-in.")
            return None

        # 6. Calculate New Position Size (Diminishing)
        # Sequence: Initial(1.0) -> Scale1(0.5) -> Scale2(0.25) ...
        last_size = symbol_positions[-1].size
        new_size = last_size * self.scale_factor
        
        # 7. Generate Scale-In Signal
        logger.info(f"[{symbol}] Pyramiding: Scaling {side} (Pos #{len(symbol_positions)+1}) with size {new_size:.4f}")
        
        return TradeSignal(
            symbol=symbol,
            action=side, # Follow same direction
            price=price,
            epoch=tick.epoch,
            size=new_size,
            probability=1.0 - spike_risk,
            reason=f"Pyramiding Scale-In #{len(symbol_positions)+1} (PnL: {total_pnl:.2f})",
            confidence=0.8,
            spike_risk=spike_risk
        )
