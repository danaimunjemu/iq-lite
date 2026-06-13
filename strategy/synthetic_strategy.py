import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from models.trading import Tick, TradeSignal, Position, Candle
from strategy.base_strategy import UnifiedSignalEngine
from strategy.rsi_strategy import RSISignalEngine
from strategy.strategies import HybridTradingStrategy
from risk.pyramiding import PyramidingEngine
from execution.provider import MarketDataProvider
from features.zones_h1 import H1ZoneDetector, H1Zone

logger = logging.getLogger(__name__)

class SyntheticIndexStrategy:
    """
    Unified Orchestrator for the Synthetic Index Trading Strategy.
    Integrates Multi-Timeframe signals, High Probability Zones (H1/M5), 
    and Advanced Position Scaling/Exit logic.
    """
    def __init__(self, 
                 symbols: List[str], 
                 provider: MarketDataProvider,
                 engine_mappings: Optional[Dict[str, str]] = None,
                 max_duration_ticks: int = 360,
                 exit_spike_prob: float = 0.30):
        self.symbols = symbols
        self.provider = provider
        self.engine_mappings = engine_mappings or {s: "TREND_HYBRID" for s in symbols}
        
        # Strategy Registry: Symbol -> Signal Engine
        self.engines: Dict[str, Any] = {}
        for s in symbols:
            engine_type = self.engine_mappings.get(s, "TREND_HYBRID")
            if engine_type == "RSI_CROSSBACK":
                self.engines[s] = RSISignalEngine([s])
            else:
                self.engines[s] = UnifiedSignalEngine([s])
        
        self.pyramiding_engine = PyramidingEngine(max_positions=3)
        self.h1_zone_detector = H1ZoneDetector(tolerance_pct=0.001)
        
        # State: Symbol -> Last Sync Epoch
        self.last_h1_sync: Dict[str, int] = {s: 0 for s in symbols}
        
        # State: Symbol -> List of Active Positions
        self.positions: Dict[str, List[Position]] = {s: [] for s in symbols}
        
        # Risk & Exit Settings
        self.max_duration_ticks = max_duration_ticks
        self.exit_spike_prob = exit_spike_prob
        self.rsi_exit_high = 80.0
        self.rsi_exit_low = 20.0
        
        # State: Symbol -> Latest features for TUI/Insights
        self.last_features: Dict[str, Dict[str, Any]] = {s: {} for s in symbols}
        self.last_signals: Dict[str, Optional[TradeSignal]] = {s: None for s in symbols}

    def process_tick(self, tick: Tick) -> List[TradeSignal]:
        """
        Main strategy pipeline executed on every incoming tick.
        Returns a list of signals (Entries, Scale-Ins, or Exits).
        """
        symbol = tick.symbol
        if symbol not in self.symbols:
            return []

        # 1. Update Sub-Engines
        engine = self.engines.get(symbol)
        if not engine: return []
        
        # Handle different engine interfaces
        if isinstance(engine, UnifiedSignalEngine):
             features = engine.feature_gen.process_tick(tick)
        else:
             # Legacy RSI engine needs manual feature feed - typically we use Unified as base
             features = self.engines.get(self.symbols[0]).feature_gen.process_tick(tick)
        
        self.last_features[symbol] = features
        self.last_signals[symbol] = None 
        signals = []

        # 2. H1 Zone Refresh (On New H1 Candle)
        h1_candle = self.provider.get_latest_h1(symbol)
        if h1_candle and h1_candle.epoch > self.last_h1_sync[symbol]:
            logger.info(f"[{symbol}] New H1 Candle detected. Rescanning High Probability Zones...")
            h1_history = self.provider.get_h1_history(symbol)
            self.h1_zone_detector.detect_zones(h1_history)
            self.last_h1_sync[symbol] = h1_candle.epoch

        # 3. Monitor & Exit Active Positions
        active_positions = self.positions.get(symbol, [])
        if active_positions:
            exit_signal = self._evaluate_exits(tick, active_positions, features)
            if exit_signal:
                signals.append(exit_signal)
                self.positions[symbol] = [] # Clear positions on exit
                return signals # Priority: Exit before scaling or new entry

            # 4. Scaling (Pyramiding) - Only if already in position
            scale_signal = self.pyramiding_engine.scale_position(
                symbol, tick, active_positions, features
            )
            if scale_signal:
                signals.append(scale_signal)
                self.positions[symbol].append(Position(
                    symbol, scale_signal.action, scale_signal.price, scale_signal.size, scale_signal.epoch
                ))

        # 5. Check for New Entry (If no positions active)
        else:
            entry_signal = self._evaluate_entries(tick, features)
            if entry_signal:
                signals.append(entry_signal)
                self.positions[symbol].append(Position(
                    symbol, entry_signal.action, entry_signal.price, entry_signal.size, entry_signal.epoch
                ))

        return signals

    def _evaluate_entries(self, tick: Tick, features: Dict[str, Any]) -> Optional[TradeSignal]:
        """
        Entry Logic: M5 RSI Setup + H1 Macro-Struct alignment (SR/SD Zones).
        """
        symbol = tick.symbol
        
        # A. Context Check (H1 Trend)
        h1_candle = self.provider.get_latest_h1(symbol)
        if not h1_candle:
            return None
            
        h1_trend_is_valid = True
        if "BOOM" in symbol.upper():
            h1_trend_is_valid = tick.price < h1_candle.open # Macroscopic down-trend for SELL
        elif "CRASH" in symbol.upper():
            h1_trend_is_valid = tick.price > h1_candle.open # Macroscopic up-trend for BUY

        # B. Macro Structural Alignment (Structural Zones)
        # BOOM SELL needs Resistance/Supply; CRASH BUY needs Support/Demand
        side = "SELL" if "BOOM" in symbol.upper() else "BUY"
        zone = self.h1_zone_detector.is_price_in_zone(tick.price)
        
        # Define high prob structural alignment
        is_structure_aligned = False
        if zone:
            if side == "SELL" and zone.zone_type in ["Resistance", "Supply"]:
                is_structure_aligned = True
            elif side == "BUY" and zone.zone_type in ["Support", "Demand"]:
                is_structure_aligned = True
        
        if not is_structure_aligned:
            # We don't trade unless we are at a structural level
            return None

        # C. Signal Check (Symbol-Specific Engine)
        if isinstance(engine, UnifiedSignalEngine):
            signal = engine.process_tick(tick)
        else:
            # RSI Engine uses different signature
            zone_eval = self.engines.get(self.symbols[0]).zone_detector.evaluate(features)
            signal = engine.process_features(features, zone=zone_eval)
        
        if signal and h1_trend_is_valid:
            # D. Enhanced Confidence Scoring (Signal + Structural Strength)
            # Signal confidence is 0-1. Zone strength can be > 1.
            # Weighted: 60% Signal extremity, 40% Structural Strength (capped at 5.0)
            structural_weight = min(zone.strength, 5.0) / 5.0
            signal.confidence = (signal.confidence * 0.6) + (structural_weight * 0.4)
            signal.zone_confidence = zone.strength
            
            signal.reason += f" | {zone.zone_type} Zone Confirmed (Strength: {zone.strength:.2f})"
            signal.size = 0.10 
            self.last_signals[symbol] = signal # Store for TUI
            return signal
            
        return None

    def _evaluate_exits(self, tick: Tick, positions: List[Position], features: Dict[str, Any]) -> Optional[TradeSignal]:
        """
        Exit Logic: RSI opposite level, Spike Risk spike, or Max Duration.
        """
        symbol = tick.symbol
        rsi = features.get("rsi_14", 50.0)
        spike_prob = features.get("spike_risk", 0.0)
        side = positions[0].side.upper()
        
        reason = ""
        
        # A. Spike Probability Exit (The "Stop" for Synthetic Indices)
        if spike_prob > self.exit_spike_prob:
            reason = f"Exiting: Spike Probability too high ({spike_prob:.2f})"
        
        # B. RSI Opposite Level (Exhaustion)
        elif side == "BUY" and rsi > self.rsi_exit_high:
             reason = f"Exiting: Buyer exhaustion (RSI: {rsi:.2f})"
        elif side == "SELL" and rsi < self.rsi_exit_low:
             reason = f"Exiting: Seller exhaustion (RSI: {rsi:.2f})"
             
        # C. Temporal Stop (Max Duration)
        # Check first position's age
        ticks_passed = features.get("ticks_since_spike", 0) # Use as proxy or track duration
        if ticks_passed > self.max_duration_ticks:
             reason = f"Exiting: Max duration reached ({ticks_passed} ticks)"

        if reason:
            logger.info(f"[{symbol}] EXIT Signal: {reason}")
            return TradeSignal(
                symbol=symbol,
                action="EXIT",
                price=tick.price,
                epoch=tick.epoch,
                probability=1.0,
                reason=reason,
                confidence=1.0
            )
            
        return None
