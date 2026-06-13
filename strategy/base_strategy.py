import logging
from typing import Dict, Any, Optional, List
from models.trading import Tick, TradeSignal
from features.indicators import FeatureGenerator
from strategy.rsi_strategy import RSISignalEngine
from strategy.filters import trend_filter, volatility_filter, is_trade_safe
from features.zones import HybridZoneDetector
from analytics.probability import probability_of_spike

logger = logging.getLogger(__name__)

class UnifiedSignalEngine:
    """
    Unified Brain for the Synthetic Index Trading System.
    Integrates Multi-Stage Indicators, Filters, and Zone Context.
    """
    def __init__(self, symbols: List[str], window_size: int = 100):
        self.feature_gen = FeatureGenerator(window_size=window_size)
        self.rsi_engine = RSISignalEngine(symbols)
        self.zone_detector = HybridZoneDetector(confidence_threshold=0.65)
        self.holding_time = 20
        self.prob_threshold = 0.20

    def process_tick(self, tick: Tick) -> Optional[TradeSignal]:
        """
        Main Pipeline: Ingest -> Zones -> Features -> RSI -> Scored Signal
        """
        # 1. Feature Engineering
        features = self.feature_gen.process_tick(tick)
        symbol = tick.symbol
        
        # 2. Zone Detection (Context Layer)
        zone = self.zone_detector.evaluate(features)
        
        # 3. Fast Signal Trigger (Context-Aware RSI Crossback)
        signal = self.rsi_engine.process_features(features, zone=zone)
        
        # 4. Filter Gating: (Additional Safety logic)
        if signal and signal.action != "HOLD":
                
            # Current Filters (Trend, Vol, Spike)
            win = self.feature_gen._get_window(symbol)
            price_history = list(win.prices)
            ma_history = [win.last_ema_50] * len(price_history)
            
            if not trend_filter(signal, price_history, ma_history, lookback=5):
                logger.info(f"[{symbol}] Signal REJECTED: Trend mismatch")
                return None
                
            if not volatility_filter(features.get("return_std", 0.0), features.get("avg_volatility", 0.0001)):
                logger.info(f"[{symbol}] Signal REJECTED: Volatility turbulence")
                return None
                
            if not is_trade_safe(features, holding_time=self.holding_time, prob_threshold=self.prob_threshold):
                logger.info(f"[{symbol}] Signal REJECTED: Spike risk too high")
                return None
            
            # 5. Scored Result
            rsi_val = features.get("rsi_14", 50.0)
            risk_prob = probability_of_spike(self.holding_time, features)
            
            # Confidence Logic
            rsi_extremity = abs(rsi_val - 50) / 50.0
            risk_headroom = (self.prob_threshold - risk_prob) / self.prob_threshold if self.prob_threshold > 0 else 0
            
            signal.confidence = (rsi_extremity * 0.6) + (max(0, risk_headroom) * 0.4)
            signal.spike_risk = risk_prob
            signal.zone_confidence = zone.confidence_score
            
            return signal
            
        return None
