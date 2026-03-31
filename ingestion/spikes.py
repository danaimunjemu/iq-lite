import math
import logging
from collections import deque
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict
from .models import Tick

logger = logging.getLogger(__name__)

@dataclass
class SpikeEvent:
    symbol: str
    epoch: int
    timestamp: str
    price_before: float
    price_after: float
    magnitude: float
    type: str  # 'Boom' or 'Crash'

class SpikeDetector:
    """Detects and records 'spikes' in synthetic indices."""
    def __init__(self, window_size: int = 50, z_threshold: float = 4.0, min_magnitude: float = 0.5):
        self.window_size = window_size
        self.z_threshold = z_threshold
        self.min_magnitude = min_magnitude
        
        # State per symbol
        self.returns = {} # Dict[str, deque]
        self.last_price = {} # Dict[str, float]

    def _get_returns_buffer(self, symbol: str) -> deque:
        if symbol not in self.returns:
            self.returns[symbol] = deque(maxlen=self.window_size)
        return self.returns[symbol]

    def process_tick(self, tick: Tick) -> Optional[SpikeEvent]:
        symbol = tick.symbol
        price = tick.price
        
        # We need at least one previous price to calculate a return
        if symbol not in self.last_price:
            self.last_price[symbol] = price
            return None

        # Calculate log return for more stable volatility estimation
        prev_price = self.last_price[symbol]
        diff = price - prev_price
        
        # log_return = math.log(price / prev_price) - too sensitive for small ticks
        # Simple relative return
        rel_return = diff / prev_price if prev_price != 0 else 0
        
        buffer = self._get_returns_buffer(symbol)
        
        spike = None
        
        if len(buffer) >= self.window_size:
            # Baseline stats
            avg_ret = sum(buffer) / len(buffer)
            var_ret = sum((r - avg_ret)**2 for r in buffer) / len(buffer)
            std_ret = math.sqrt(var_ret)
            
            # Detect spike
            if std_ret > 0:
                z_score = (rel_return - avg_ret) / std_ret
                
                # Logic: Positive z-score for Boom (upward), Negative for Crash (downward)
                # But typically Crash/Boom indices ONLY spike in one direction.
                # Boom 1000 -> Upward spikes
                # Crash 1000 -> Downward spikes
                
                is_boom = "BOOM" in symbol.upper() and z_score > self.z_threshold
                is_crash = "CRASH" in symbol.upper() and z_score < -self.z_threshold
                
                if (is_boom or is_crash) and abs(diff) >= self.min_magnitude:
                    spike = SpikeEvent(
                        symbol=symbol,
                        epoch=tick.epoch,
                        timestamp=tick.timestamp.isoformat(),
                        price_before=prev_price,
                        price_after=price,
                        magnitude=diff,
                        type="Boom" if is_boom else "Crash"
                    )
                    logger.info(f"SPIKE DETECTED: {spike}")

        # Update buffer and state
        # After a spike, we don't add it to the buffer to avoid inflating volatility
        if not spike:
            buffer.append(rel_return)
            
        self.last_price[symbol] = price
        return spike

    def detect_historical(self, ticks: List[Tick]) -> List[SpikeEvent]:
        """Scans a list of ticks and identifies all spikes."""
        spikes = []
        # Clear state to ensure clean run
        self.returns = {}
        self.last_price = {}
        
        for tick in ticks:
            event = self.process_tick(tick)
            if event:
                spikes.append(event)
        return spikes
