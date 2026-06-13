import logging
from typing import Dict, Any, Optional, List
from models.trading import Tick, Candle

class CandleBuilder:
    """Historical Candle Replay Engine (Alias for CandleAggregator)."""
    def __init__(self, interval_seconds: int):
        self.agg = CandleAggregator([interval_seconds])
        self.interval = interval_seconds

    def process_tick(self, tick: Tick) -> Optional[Candle]:
        res = self.agg.update(tick)
        return res.get(self.interval)

class CandleAggregator:
    """
    Simultaneously tracks forming candles for multiple intervals (M5, H1, etc.).
    Returns a dictionary of closed candles when boundaries are crossed.
    """
    def __init__(self, intervals: List[int]):
        self.intervals = sorted(intervals) # e.g. [300, 3600]
        # interval -> symbol -> current active candle data
        self.active: Dict[int, Dict[str, Dict[str, Any]]] = {
            i: {} for i in intervals
        }

    def update(self, tick: Tick) -> Dict[int, Candle]:
        """
        Ingests a tick and returns any candles that were closed.
        Returns: {interval: closed_candle}
        """
        closed_candles = {}
        symbol = tick.symbol
        
        for interval in self.intervals:
            window_start = (tick.epoch // interval) * interval
            
            # 1. Initialize if first tick for this interval/symbol
            if symbol not in self.active[interval]:
                self.active[interval][symbol] = {
                    "open": tick.price,
                    "high": tick.price,
                    "low": tick.price,
                    "close": tick.price,
                    "epoch": window_start
                }
                continue
                
            current = self.active[interval][symbol]
            
            # 2. Check for Boundary Cross
            if window_start > current["epoch"]:
                # Close the forming candle
                closed_candles[interval] = Candle(
                    symbol=symbol,
                    open=current["open"],
                    high=current["high"],
                    low=current["low"],
                    close=current["close"],
                    epoch=current["epoch"],
                    is_closed=True
                )
                
                # Start new candle with current tick
                self.active[interval][symbol] = {
                    "open": tick.price,
                    "high": tick.price,
                    "low": tick.price,
                    "close": tick.price,
                    "epoch": window_start
                }
            else:
                # 3. Incremental Update
                current["high"] = max(current["high"], tick.price)
                current["low"] = min(current["low"], tick.price)
                current["close"] = tick.price
                
        return closed_candles

    def get_current_candle(self, symbol: str, interval: int) -> Optional[Candle]:
        """
        Returns the forming candle state for manual inspection/indicators.
        """
        if interval not in self.active or symbol not in self.active[interval]:
            return None
            
        current = self.active[interval][symbol]
        return Candle(
            symbol=symbol,
            open=current["open"],
            high=current["high"],
            low=current["low"],
            close=current["close"],
            epoch=current["epoch"],
            is_closed=False
        )

# Legacy alias omitted to keep it clean.
# Use CandleAggregator for multi-timeframe projects.
