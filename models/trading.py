from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Tick:
    symbol: str
    price: float
    epoch: int  # Unix timestamp from API
    
    @property
    def timestamp(self) -> datetime:
        """Converts Unix epoch to human-readable datetime."""
        return datetime.fromtimestamp(self.epoch)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "epoch": self.epoch,
            "timestamp": self.timestamp.isoformat()
        }
@dataclass
class TradeSignal:
    symbol: str
    action: str  # BUY, SELL, HOLD
    price: float
    epoch: int
    probability: float
    reason: str
    size: float = 0.0 # Lot size
    confidence: float = 0.0
    spike_risk: float = 0.0
    zone_confidence: float = 0.0

    @property
    def timestamp(self) -> datetime:
        return datetime.fromtimestamp(self.epoch)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "action": self.action,
            "price": self.price,
            "epoch": self.epoch,
            "size": round(self.size, 4),
            "probability": self.probability,
            "reason": self.reason,
            "confidence": round(self.confidence, 4),
            "spike_risk": round(self.spike_risk, 4),
            "zone_confidence": round(self.zone_confidence, 4),
            "timestamp": self.timestamp.isoformat()
        }

@dataclass
class Position:
    symbol: str
    side: str  # BUY, SELL
    entry_price: float
    size: float
    epoch: int
    
    @property
    def timestamp(self) -> datetime:
        return datetime.fromtimestamp(self.epoch)

    def get_unrealized_pnl(self, current_price: float) -> float:
        """Calculates unrealized PnL based on position side."""
        if self.side.upper() == "BUY":
            return (current_price - self.entry_price) * self.size
        else: # SELL
            return (self.entry_price - current_price) * self.size

@dataclass
class BankrollState:
    balance: float
    equity: float
    risk_amount: float
    timestamp: datetime

    def to_dict(self) -> dict:
        return {
            "balance": self.balance,
            "equity": self.equity,
            "risk_amount": self.risk_amount,
            "timestamp": self.timestamp.isoformat()
        }

@dataclass
class RiskState:
    daily_pnl: float
    max_drawdown: float
    trade_count_24h: int
    is_kill_switch_active: bool
    last_kill_reason: Optional[str] = None
    timestamp: datetime = datetime.now()

    def to_dict(self) -> dict:
        return {
            "daily_pnl": self.daily_pnl,
            "max_drawdown": self.max_drawdown,
            "trade_count": self.trade_count_24h,
            "kill_switch": self.is_kill_switch_active,
            "reason": self.last_kill_reason,
            "timestamp": self.timestamp.isoformat()
        }

@dataclass
class BacktestResult:
    symbol: str
    initial_balance: float
    final_balance: float
    total_trades: int
    win_rate: float
    max_drawdown: float
    profit_factor: float
    net_pnl: float

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "initial_balance": self.initial_balance,
            "final_balance": self.final_balance,
            "total_trades": self.total_trades,
            "win_rate_percent": round(self.win_rate * 100, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "profit_factor": round(self.profit_factor, 2),
            "net_pnl": round(self.net_pnl, 2)
        }

@dataclass
class Candle:
    symbol: str
    open: float
    high: float
    low: float
    close: float
    epoch: int  # Start of interval
    is_closed: bool = False

    @property
    def timestamp(self) -> datetime:
        return datetime.fromtimestamp(self.epoch)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "epoch": self.epoch,
            "timestamp": self.timestamp.isoformat()
        }
