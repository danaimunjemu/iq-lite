import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple, Dict
from models.trading import Candle

logger = logging.getLogger(__name__)

@dataclass
class H1Zone:
    """Standardized High-Probability Zone for Synthetic Indices."""
    symbol: str
    min_price: float
    max_price: float
    timestamp: datetime
    zone_type: str # 'Support', 'Resistance', 'Supply', 'Demand'
    strength: float = 1.0 # Multiplier based on move size

class H1ZoneDetector:
    """
    Identifies institutional-grade Support/Resistance and Supply/Demand zones 
    using H1 candle data.
    """
    def __init__(self, tolerance_pct: float = 0.0005):
        self.tolerance_pct = tolerance_pct
        self.active_zones: List[H1Zone] = []

    def detect_zones(self, candles: List[Candle]) -> List[H1Zone]:
        """
        Main scanner for H1 zones.
        """
        if len(candles) < 10:
            return []
            
        new_zones = []
        new_zones.extend(self._detect_support_resistance(candles))
        new_zones.extend(self._detect_supply_demand(candles))
        
        # Deduplicate and sort by strength
        self.active_zones = sorted(new_zones, key=lambda x: x.strength, reverse=True)
        return self.active_zones

    def is_price_in_zone(self, current_price: float) -> Optional[H1Zone]:
        """
        Checks if the current price is interacting with any active zone.
        """
        for zone in self.active_zones:
            tolerance = current_price * self.tolerance_pct
            if (zone.min_price - tolerance) <= current_price <= (zone.max_price + tolerance):
                return zone
        return None

    def _detect_support_resistance(self, candles: List[Candle], window: int = 2) -> List[H1Zone]:
        """
        Identifies Swing Highs and Swing Lows using a rolling window.
        """
        sr_zones = []
        n = len(candles)
        
        # Skip ends for window buffer
        for i in range(window, n - window):
            curr = candles[i]
            
            # 1. Swing High (Resistance)
            is_high = True
            for j in range(i - window, i + window + 1):
                if i == j: continue
                if candles[j].high >= curr.high:
                    is_high = False
                    break
            
            if is_high:
                sr_zones.append(H1Zone(
                    symbol=curr.symbol,
                    min_price=curr.high * 0.9998, # Small depth
                    max_price=curr.high * 1.0002,
                    timestamp=curr.timestamp,
                    zone_type='Resistance'
                ))

            # 2. Swing Low (Support)
            is_low = True
            for j in range(i - window, i + window + 1):
                if i == j: continue
                if candles[j].low <= curr.low:
                    is_low = False
                    break
            
            if is_low:
                sr_zones.append(H1Zone(
                    symbol=curr.symbol,
                    min_price=curr.low * 0.9998,
                    max_price=curr.low * 1.0002,
                    timestamp=curr.timestamp,
                    zone_type='Support'
                ))
                
        return sr_zones

    def _detect_supply_demand(self, candles: List[Candle], min_consolidation: int = 3) -> List[H1Zone]:
        """
        Identifies Supply/Demand zones based on consolidation followed by ERC moves.
        ERC = Extended Range Candle (Body > 2x average body of last 10 candles)
        """
        sd_zones = []
        n = len(candles)
        if n < 15: return []
        
        for i in range(min_consolidation, n):
            # 1. Check for ERC (The "Move Away")
            erc = candles[i]
            prev_bodies = [abs(c.close - c.open) for c in candles[i-10:i]]
            avg_body = sum(prev_bodies) / len(prev_bodies) if prev_bodies else 1.0
            
            body_size = abs(erc.close - erc.open)
            is_erc = body_size > (avg_body * 2.5)
            
            if is_erc:
                # 2. Check for Consolidation Base before ERC
                base = candles[i - min_consolidation : i]
                base_high = max(c.high for c in base)
                base_low = min(c.low for c in base)
                base_vol = base_high - base_low
                
                # Demand Zone (Bullish ERC)
                if erc.close > erc.open and erc.close > base_high:
                    sd_zones.append(H1Zone(
                        symbol=erc.symbol,
                        min_price=base_low,
                        max_price=base_high,
                        timestamp=erc.timestamp,
                        zone_type='Demand',
                        strength=body_size / (base_vol if base_vol > 0 else 1.0)
                    ))
                
                # Supply Zone (Bearish ERC)
                elif erc.close < erc.open and erc.close < base_low:
                    sd_zones.append(H1Zone(
                        symbol=erc.symbol,
                        min_price=base_low,
                        max_price=base_high,
                        timestamp=erc.timestamp,
                        zone_type='Supply',
                        strength=body_size / (base_vol if base_vol > 0 else 1.0)
                    ))
                    
        return sd_zones
