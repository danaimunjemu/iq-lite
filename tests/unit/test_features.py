import pytest
from models.trading import Tick
from features.indicators import TickWindow, FeatureGenerator
from tests.mocks.data_generator import SyntheticMarketGenerator

def test_tick_window_sma_ema_math():
    """Verifies SMA and EMA calculations are mathematically sound."""
    win = TickWindow(window_size=10)
    # Feed constant price
    for i in range(10):
        win.add_tick(Tick("TEST", 100.0, 1000+i))
    
    stats = win.get_stats()
    assert stats["ma_50"] == 100.0
    assert stats["ema_50"] == 100.0
    assert stats["std_dev"] == 0.0

    # Add a jump
    win.add_tick(Tick("TEST", 110.0, 1010))
    stats = win.get_stats()
    assert stats["ma_50"] > 100.0
    assert stats["ema_50"] > 100.0
    assert stats["std_dev"] > 0.0

def test_rsi_calculation():
    """Verifies RSI reaches expected extremes in trending markets."""
    win = TickWindow(window_size=20)
    gen = SyntheticMarketGenerator(base_price=100.0)
    
    # 1. Bullish Trend -> High RSI
    bull_ticks = gen.generate_linear_trend(n_ticks=20, drift_per_tick=1.0)
    for t in bull_ticks:
        win.add_tick(t)
    
    stats = win.get_stats()
    assert stats["rsi_14"] > 70.0 # Standard overbought threshold
    
    # 2. Bearish Trend -> Low RSI
    win_bear = TickWindow(window_size=20)
    bear_ticks = gen.generate_linear_trend(n_ticks=20, drift_per_tick=-1.0)
    for t in bear_ticks:
        win_bear.add_tick(t)
        
    stats_bear = win_bear.get_stats()
    assert stats_bear["rsi_14"] < 30.0 # Standard oversold threshold

def test_spike_detection_logic():
    """Verifies that the FeatureGenerator correctly flags anomalous price jumps."""
    feat_gen = FeatureGenerator(window_size=50, spike_threshold_std=3.0)
    gen = SyntheticMarketGenerator(base_price=100.0)
    
    # Populate with stable ticks
    stable_ticks = gen.generate_sine_wave(n_ticks=50, amplitude=0.5)
    for t in stable_ticks[:-1]:
        feat_gen.process_tick(t)
        
    # The 'Target' Tick is a massive spike
    spike_tick = Tick("SYNTH1000", 150.0, 1711900050)
    result = feat_gen.process_tick(spike_tick)
    
    assert result["is_spike"] is True
    # The tick itself is the spike, so it remains at 0 or 1 depending on update order
    # Current implementation increments after detection
    assert result["ticks_since_spike"] <= 1 
