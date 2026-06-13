import math
import logging
from collections import deque
from typing import Dict, List, Optional, Any
from datetime import datetime
from models.trading import Tick

logger = logging.getLogger(__name__)

class TickWindow:
    """Manages a rolling window of ticks with state-aware optimized calculations."""
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.prices = deque(maxlen=window_size)
        self.epochs = deque(maxlen=window_size)
        
        # Optimized State
        self.price_sum_50 = 0.0
        self.last_ema_50: Optional[float] = None
        self.rsi_history = deque(maxlen=5) # For rsi_ma_5
        self.last_spike_epoch: Optional[int] = None
        self.ticks_since_spike: int = 0

    def add_tick(self, tick: Tick):
        # Manage SMA-50 Sum
        if len(self.prices) >= 50:
            self.price_sum_50 -= self.prices[-50]
        self.price_sum_50 += tick.price
        
        # Manage EMA-50 (O(1))
        if self.last_ema_50 is None:
            self.last_ema_50 = tick.price
        else:
            multiplier = 2 / (50 + 1)
            self.last_ema_50 = (tick.price - self.last_ema_50) * multiplier + self.last_ema_50
            
        self.prices.append(tick.price)
        self.epochs.append(tick.epoch)
        self.ticks_since_spike += 1

    @property
    def is_full(self) -> bool:
        return len(self.prices) >= self.window_size

    def _calculate_rsi_14(self, prices_list: List[float]) -> float:
        if len(prices_list) < 15:
            return 50.0
        gains = []
        losses = []
        for i in range(len(prices_list)-14, len(prices_list)):
            diff = prices_list[i] - prices_list[i-1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))
        avg_gain = sum(gains) / 14
        avg_loss = sum(losses) / 14
        if avg_loss == 0: return 100.0
        return 100 - (100 / (1 + (avg_gain / avg_loss)))

    def get_stats(self) -> Dict[str, float]:
        if not self.prices: return {}
        
        prices = list(self.prices)
        n = len(prices)
        
        # 1. Base Stats
        mean = sum(prices) / n
        std_dev = math.sqrt(sum((p - mean) ** 2 for p in prices) / n)
        z_score = (prices[-1] - mean) / std_dev if std_dev > 0 else 0.0
        
        # 2. Optimized MAs
        ma_50 = self.price_sum_50 / min(n, 50)
        ema_50 = self.last_ema_50 or prices[-1]
        
        # 3. RSI Logic
        current_rsi = self._calculate_rsi_14(prices)
        # Update RSI History (fixed to allow duplicates for MA calculation)
        self.rsi_history.append(current_rsi)
        rsi_ma_5 = sum(self.rsi_history) / len(self.rsi_history) if self.rsi_history else 50.0
        
        # 4. Volatility (Returns-based)
        return_std = 0.0
        avg_vol = 0.0
        if n > 20:
            rets = [(prices[i]/prices[i-1]-1) for i in range(n-20, n)]
            r_mean = sum(rets) / 20
            return_std = math.sqrt(sum((r - r_mean) ** 2 for r in rets) / 20)
            avg_vol = sum(abs(r) for r in rets) / 20
            
        return {
            "mean": mean, "std_dev": std_dev, "z_score": z_score,
            "ma_50": ma_50, "ema_50": ema_50,
            "rsi_14": current_rsi, "rsi_ma_5": rsi_ma_5,
            "return_std": return_std, "avg_volatility": avg_vol,
            "momentum": prices[-1] - prices[0] if n > 1 else 0.0
        }

class FeatureGenerator:
    """Consolidated high-performance feature pipeline."""
    def __init__(self, window_size: int = 100, spike_threshold_std: float = 3.5):
        self.windows: Dict[str, TickWindow] = {}
        self.window_size = window_size
        self.spike_threshold_std = spike_threshold_std

    def _get_window(self, symbol: str) -> TickWindow:
        if symbol not in self.windows:
            self.windows[symbol] = TickWindow(self.window_size)
        return self.windows[symbol]

    def process_tick(self, tick: Tick) -> Dict[str, Any]:
        win = self._get_window(tick.symbol)
        stats = win.get_stats()
        
        # Spike Detection (Pre-update logic)
        is_spike = False
        if stats and stats.get("std_dev", 0) > 0:
            if abs(tick.price - stats["mean"]) > self.spike_threshold_std * stats["std_dev"]:
                is_spike = True
                win.last_spike_epoch = tick.epoch
                win.ticks_since_spike = 0

        win.add_tick(tick)
        new_stats = win.get_stats()
        
        return {
            "symbol": tick.symbol,
            "price": tick.price,
            "epoch": tick.epoch,
            "timestamp": tick.timestamp.isoformat(),
            **new_stats,
            "is_spike": is_spike,
            "ticks_since_spike": win.ticks_since_spike
        }
