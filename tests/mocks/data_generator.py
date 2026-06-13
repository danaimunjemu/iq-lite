import math
import random
from typing import List
from models.trading import Tick

class SyntheticMarketGenerator:
    """
    Generates high-fidelity synthetic market scenarios for strategy validation.
    """
    def __init__(self, symbol: str = "SYNTH1000", base_price: float = 100.0):
        self.symbol = symbol
        self.base_price = base_price
        self.epoch_start = 1711900000

    def generate_sine_wave(self, n_ticks: int = 1000, amplitude: float = 5.0, period: int = 200) -> List[Tick]:
        """Tests Mean Reversion and RSI Oscillation."""
        ticks = []
        for i in range(n_ticks):
            # Price oscillates around base_price
            price = self.base_price + (amplitude * math.sin(2 * math.pi * i / period))
            ticks.append(Tick(self.symbol, round(price, 4), self.epoch_start + i))
        return ticks

    def generate_linear_trend(self, n_ticks: int = 1000, drift_per_tick: float = 0.05) -> List[Tick]:
        """Tests Trend Following and MA Crossovers."""
        ticks = []
        for i in range(n_ticks):
            price = self.base_price + (i * drift_per_tick)
            ticks.append(Tick(self.symbol, round(price, 4), self.epoch_start + i))
        return ticks

    def generate_spike_scenarios(self, n_ticks: int = 1000, spike_height: float = 50.0, spike_index: int = 500) -> List[Tick]:
        """Tests Spike Exit Logic and Risk Gating."""
        ticks = []
        for i in range(n_ticks):
            price = self.base_price + (random.uniform(-0.1, 0.1)) # Baseline noise
            if i == spike_index:
                price += spike_height # THE SPIKE
            ticks.append(Tick(self.symbol, round(price, 4), self.epoch_start + i))
        return ticks

    def generate_consolidation_breakout(self, n_ticks: int = 1000, breakout_index: int = 700) -> List[Tick]:
        """Tests H1 Zone/Support/Resistance breakout logic."""
        ticks = []
        for i in range(n_ticks):
            if i < breakout_index:
                # Small range [98, 102]
                price = self.base_price + random.uniform(-2.0, 2.0)
            else:
                # Breakout
                price = self.base_price + 2.0 + ((i - breakout_index) * 0.5)
            ticks.append(Tick(self.symbol, round(price, 4), self.epoch_start + i))
        return ticks
