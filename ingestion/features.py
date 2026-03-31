import math
import logging
from collections import deque
from typing import Dict, List, Optional
from datetime import datetime
from .models import Tick

logger = logging.getLogger(__name__)

class TickWindow:
    """Manages a rolling window of ticks for a single symbol."""
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.prices = deque(maxlen=window_size)
        self.epochs = deque(maxlen=window_size)
        self.last_spike_epoch: Optional[int] = None
        self.ticks_since_spike: int = 0

    def add_tick(self, tick: Tick):
        self.prices.append(tick.price)
        self.epochs.append(tick.epoch)
        self.ticks_since_spike += 1

    @property
    def is_full(self) -> bool:
        return len(self.prices) >= self.window_size

    def get_stats(self) -> Dict[str, float]:
        if not self.prices:
            return {}

        prices = list(self.prices)
        n = len(prices)
        mean = sum(prices) / n
        
        # Variance and Standard Deviation
        variance = sum((p - mean) ** 2 for p in prices) / n
        std_dev = math.sqrt(variance)
        
        # Returns (tick-to-tick)
        returns = 0.0
        if n > 1:
            returns = (prices[-1] / prices[-2]) - 1

        # Z-Score
        z_score = 0.0
        if std_dev > 0:
            z_score = (prices[-1] - mean) / std_dev

        # Momentum (N ticks ago vs current)
        momentum = 0.0
        if n > 1:
            momentum = prices[-1] - prices[0]

        return {
            "mean": mean,
            "std_dev": std_dev,
            "z_score": z_score,
            "returns": returns,
            "momentum": momentum,
            "volatility": std_dev / mean if mean != 0 else 0
        }

class FeatureGenerator:
    """Main interface for generating features for multiple symbols."""
    def __init__(self, window_size: int = 100, spike_threshold_std: float = 3.5):
        self.windows: Dict[str, TickWindow] = {}
        self.window_size = window_size
        self.spike_threshold_std = spike_threshold_std

    def _get_window(self, symbol: str) -> TickWindow:
        if symbol not in self.windows:
            self.windows[symbol] = TickWindow(self.window_size)
        return self.windows[symbol]

    def process_tick(self, tick: Tick) -> Dict[str, any]:
        """Processes a single tick and returns computed features."""
        win = self._get_window(tick.symbol)
        
        # Pre-update stats to detect spikes
        stats = win.get_stats()
        
        # Spike Detection (Specific for Crash/Boom)
        # A spike is a move > threshold * standard deviation
        is_spike = False
        if stats and "std_dev" in stats and stats["std_dev"] > 0:
            current_return = (tick.price / win.prices[-1]) - 1 if win.prices else 0
            # Simplify: A spike is a large relative move compared to volatility
            # For Crash 1000, it's a large drop. For Boom 1000, it's a large jump.
            # We use absolute Z-score for general spike detection
            price_diff = abs(tick.price - stats["mean"])
            if price_diff > self.spike_threshold_std * stats["std_dev"]:
                is_spike = True
                win.last_spike_epoch = tick.epoch
                win.ticks_since_spike = 0

        # Update window
        win.add_tick(tick)
        
        # Post-update stats
        new_stats = win.get_stats()
        
        features = {
            "symbol": tick.symbol,
            "price": tick.price,
            "epoch": tick.epoch,
            "timestamp": tick.timestamp.isoformat(),
            **new_stats,
            "is_spike": is_spike,
            "ticks_since_spike": win.ticks_since_spike
        }
        
        return features
