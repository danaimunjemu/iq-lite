import pytest
from unittest.mock import MagicMock
from models.trading import Tick, Candle, Position
from strategy.synthetic_strategy import SyntheticIndexStrategy
from execution.provider import MarketDataProvider
from features.zones_h1 import H1Zone

@pytest.fixture
def mock_strategy():
    symbols = ["BOOM1000"]
    provider = MagicMock(spec=MarketDataProvider)
    # Mock H1 Candle (Open 150, Price 120 -> Down Trend Valid for SELL)
    mock_h1 = Candle("BOOM1000", 150.0, 160.0, 110.0, 140.0, 1711900000, True)
    provider.get_latest_h1.return_value = mock_h1
    
    strat = SyntheticIndexStrategy(symbols, provider)
    # Add a Resistance Zone at 120
    rez_zone = H1Zone("BOOM1000", 119.9, 120.1, 1711900000, "Resistance", strength=2.0)
    strat.h1_zone_detector.active_zones = [rez_zone]
    
    return strat

def test_entry_structural_alignment(mock_strategy):
    """Verifies that signals are approved only when near structural zones."""
    tick_in_zone = Tick("BOOM1000", 120.0, 1711900100)
    tick_out_zone = Tick("BOOM1000", 110.0, 1711900100)
    
    # Mock RSI signal (Seller exhaustion trigger)
    mock_strategy.signal_engine.process_tick = MagicMock(return_value=MagicMock(confidence=0.8, reason="RSI Crossback"))

    # 1. Inside Zone -> Approved
    signal_ok = mock_strategy._evaluate_entries(tick_in_zone, {})
    assert signal_ok is not None
    assert "Resistance Zone Confirmed" in signal_ok.reason
    # With 60/40 weighting: (0.8*0.6) + (0.4*0.4) = 0.64
    assert signal_ok.confidence >= 0.6 

    # 2. Outside Zone -> Suppressed
    signal_fail = mock_strategy._evaluate_entries(tick_out_zone, {})
    assert signal_fail is None

def test_exit_spike_probability(mock_strategy):
    """Verifies emergency exit triggers when spike probability exceeds threshold."""
    tick = Tick("BOOM1000", 120.0, 1711900200)
    pos = [Position("BOOM1000", "SELL", 120.0, 0.1, 1711900100)]
    
    # High Spike Risk (0.45 > 0.30 threshold)
    features = {"rsi_14": 50.0, "spike_risk": 0.45}
    
    exit_signal = mock_strategy._evaluate_exits(tick, pos, features)
    assert exit_signal is not None
    assert "Spike Probability too high" in exit_signal.reason
    assert exit_signal.action == "EXIT"

def test_exit_rsi_exhaustion(mock_strategy):
    """Verifies exhaustion-based exit when RSI hits target extremes."""
    tick = Tick("BOOM1000", 115.0, 1711900200)
    pos = [Position("BOOM1000", "SELL", 120.0, 0.1, 1711900100)]
    
    # Seller exhaustion for BOOM SELL (RSI < 20)
    features = {"rsi_14": 15.0, "spike_risk": 0.05}
    
    exit_signal = mock_strategy._evaluate_exits(tick, pos, features)
    assert exit_signal is not None
    assert "Seller exhaustion" in exit_signal.reason
