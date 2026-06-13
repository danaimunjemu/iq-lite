import logging
from collections import deque
from typing import Dict, List, Optional, Deque, Any
from models.trading import Tick, Candle

logger = logging.getLogger(__name__)

class MarketDataProvider:
    """
    Data Synchronization Layer.
    Single source of truth for the Strategy Engine.
    Ensures that only fully CLOSED candles are used for strategic decisions.
    """
    def __init__(self, symbols: List[str], buffer_size: int = 100):
        self.symbols = symbols
        self.buffer_size = buffer_size
        
        # Current Real-Time State
        self.latest_ticks: Dict[str, Tick] = {}
        self.tick_history: Dict[str, Deque[float]] = {s: deque(maxlen=30) for s in symbols}
        
        # Closed History Buffers (Interval -> Symbol -> Deque[Candle])
        # Intervals: 300(M5), 900(M15), 1800(M30), 3600(H1), 14400(H4), 86400(D1)
        self.intervals = [300, 900, 1800, 3600, 14400, 86400]
        self.history: Dict[int, Dict[str, Deque[Candle]]] = {
            i: {s: deque(maxlen=buffer_size) for s in symbols} for i in self.intervals
        }

    def update_tick(self, tick: Tick):
        """Processes a new incoming tick."""
        self.latest_ticks[tick.symbol] = tick
        self.tick_history[tick.symbol].append(tick.price)

    def update_candles(self, closed_candles: Dict[int, Candle]):
        """Processes one or more closed candles from the aggregator."""
        for interval, candle in closed_candles.items():
            if interval in self.history and candle.symbol in self.history[interval]:
                self.history[interval][candle.symbol].append(candle)
                logger.debug(f"[DataProvider] Added {interval}s candle for {candle.symbol}")

    # --- Clean Strategy Interface ---

    def get_latest_tick(self, symbol: str) -> Optional[Tick]:
        return self.latest_ticks.get(symbol)

    def get_tick_history(self, symbol: str) -> List[float]:
        return list(self.tick_history.get(symbol, []))

    def get_sentiment(self, symbol: str, interval: int) -> Dict[str, Any]:
        """Calculates normalized sentiment (-1.0 to 1.0) for a timeframe."""
        buffer = self.history.get(interval, {}).get(symbol)
        if not buffer or len(buffer) < 10:
             return {"score": 0.0, "status": "No Macro Data", "trend": "Neutral"}
        
        import statistics
        prices = [c.close for c in buffer]
        current = prices[-1]
        sma = statistics.mean(prices[-10:])
        
        # 1. Trend (MA Alignment)
        trend_score = 1.0 if current > sma else -1.0
        
        # 2. RSI (Simplified)
        up = sum(max(0, prices[i] - prices[i-1]) for i in range(-9, 0))
        down = sum(max(0, prices[i-1] - prices[i]) for i in range(-9, 0))
        rsi = 100 - (100 / (1 + (up/down if down > 0 else 100)))
        
        # 3. Aggregate Workstation Sentiment
        score = (trend_score * 0.7) + ((rsi - 50)/50 * 0.3)
        status = "Strong Bull" if score > 0.6 else "Weak Bull" if score > 0.1 else \
                 "Strong Bear" if score < -0.6 else "Weak Bear" if score < -0.1 else "Neutral"
        
        return {
            "score": score,
            "status": status,
            "trend": "Bullish" if trend_score > 0 else "Bearish",
            "rsi": rsi
        }

    def get_latest_m5(self, symbol: str) -> Optional[Candle]:
        """Returns the most recently CLOSED 5-minute candle."""
        buffer = self.history[300].get(symbol)
        return buffer[-1] if buffer else None

    def get_latest_h1(self, symbol: str) -> Optional[Candle]:
        """Returns the most recently CLOSED 1-hour candle."""
        buffer = self.history[3600].get(symbol)
        return buffer[-1] if buffer else None

    def get_m5_history(self, symbol: str) -> List[Candle]:
        """Returns the full M5 history buffer for indicator calculations."""
        buffer = self.history[300].get(symbol)
        return list(buffer) if buffer else []

    def get_h1_history(self, symbol: str) -> List[Candle]:
        """Returns the full H1 history buffer for indicator calculations."""
        buffer = self.history[3600].get(symbol)
        return list(buffer) if buffer else []

    def get_relative_volatility(self, symbol: str) -> float:
        """
        Calculates a 'Heat Score' (0.0 - 1.0) based on recent volatility.
        Uses standard deviation of last 30 ticks relative to M5 range.
        """
        ticks = self.get_tick_history(symbol)
        if len(ticks) < 10: return 0.0
        
        # 1. Micro-Volatility (Tick Std Dev)
        import statistics
        try:
            current_vol = statistics.stdev(ticks)
        except:
            current_vol = 0.0
            
        # 2. Benchmark (M5 Average Range)
        m5_history = self.get_m5_history(symbol)
        if not m5_history:
             # Fallback to absolute tick variance
             return min(current_vol / 2.0, 1.0)
        
        avg_range = statistics.mean([abs(c.high - c.low) for c in m5_history[-10:]])
        if avg_range == 0: return 0.0
        
        # 3. Heat Index (Current StdDev vs Historical Range)
        heat = (current_vol * 1.5) / avg_range
        return min(max(heat, 0.0), 1.0)

    def is_aligned(self, symbol: str) -> bool:
        """
        Validates that the latest tick is within a reasonable 
        offset of the last closed M5 candle.
        """
        tick = self.get_latest_tick(symbol)
        m5 = self.get_latest_m5(symbol)
        if not tick or not m5:
            return False
            
        # Tick should not be more than 10 minutes (2x M5) older than the last candle 
        # (This is a safety check for stale data)
        return abs(tick.epoch - m5.epoch) < 600

    def get_correlation(self, s1: str, s2: str, window: int = 20) -> float:
        """Calculates Pearson Correlation Coefficient between two symbols."""
        b1 = self.history[300].get(s1)
        b2 = self.history[300].get(s2)
        if not b1 or not b2 or len(b1) < window or len(b2) < window:
             return 0.0
             
        p1 = [c.close for c in list(b1)[-window:]]
        p2 = [c.close for c in list(b2)[-window:]]
        
        import statistics
        try:
            m1, m2 = statistics.mean(p1), statistics.mean(p2)
            num = sum((x - m1) * (y - m2) for x, y in zip(p1, p2))
            den = (sum((x - m1)**2 for x in p1) * sum((y - m2)**2 for y in p2))**0.5
            return num / den if den != 0 else 0.0
        except:
            return 0.0

    def get_portfolio_stats(self, positions_dict: Dict[str, List[Any]]) -> Dict[str, Any]:
        """Aggregates portfolio-wide risk and exposure metrics."""
        total_exposure = 0.0
        by_symbol = {}
        
        for s in self.symbols:
             pos_list = positions_dict.get(s, [])
             count = len(pos_list)
             exposure = sum(p.size for p in pos_list)
             total_exposure += exposure
             
             # Calculate variance (simplified)
             m5_history = [c.close for c in self.get_m5_history(s)[-10:]]
             vol = statistics.stdev(m5_history) if len(m5_history) > 2 else 0.0
             
             by_symbol[s] = {
                 "count": count,
                 "exposure": exposure,
                 "volatility": vol
             }
             
        return {
            "total_exposure": total_exposure,
            "symbols": by_symbol,
            "timestamp": int(datetime.now().timestamp())
        }
