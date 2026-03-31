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
