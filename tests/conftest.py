import pytest
from models.trading import Tick, Candle, Position
from risk.manager import RiskManager

@pytest.fixture
def base_tick():
    return Tick("BOOM1000", 100.0, 1711900000)

@pytest.fixture
def bullish_candle():
    return Candle("BOOM1000", 100.0, 110.0, 95.0, 105.0, 1711900000, True)

@pytest.fixture
def risk_mgr_strict():
    return RiskManager(max_daily_loss=100.0, max_trades_per_hour=3)

@pytest.fixture
def active_sell_pos():
    return Position("BOOM1000", "SELL", 100.0, 0.1, 1711900000)
