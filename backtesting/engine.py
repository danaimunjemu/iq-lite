import csv
import logging
from typing import List, Dict, Any, Optional
from models.trading import Tick, TradeSignal, BacktestResult
from features.indicators import FeatureGenerator
from strategy.base_strategy import UnifiedSignalEngine
from models.bankroll import BankrollManager
from risk.manager import RiskManager
from execution.exit_manager import TradeExitManager
from features.candles import CandleBuilder

logger = logging.getLogger(__name__)

class BacktestEngine:
    """
    Hybrid Backtesting Engine:
    - Tick-based replay for high-fidelity execution.
    - Candle-based (M5) strategic entry signals.
    - Continuous tick-based exit monitoring (Duration, Risk Surge).
    """
    def __init__(
        self, 
        symbol: str, 
        initial_balance: float = 1000.0,
        base_risk: float = 0.01,
        prob_threshold: float = 0.2,
        sl_amount: float = 1.0, # Strategy SL in USD
        tp_amount: float = 0.5  # Strategy TP in USD
    ):
        self.symbol = symbol
        self.initial_balance = initial_balance
        self.sl_amount = sl_amount
        self.tp_amount = tp_amount
        
        # Initialize Core Modules
        self.engine = UnifiedSignalEngine(symbols=[symbol], window_size=100)
        self.candle_builder = CandleBuilder(interval_seconds=300) # M5
        self.exit_manager = TradeExitManager(max_ticks=80, risk_threshold=0.35)
        self.bankroll = BankrollManager(initial_balance=initial_balance, risk_per_trade=base_risk)
        
        self.risk_mgr = RiskManager(
            max_daily_loss=initial_balance * 0.1,
            max_drawdown=initial_balance * 0.2
        )
        
        # State
        self.active_trade: Optional[Dict[str, Any]] = None
        self.trades_history: List[Dict[str, Any]] = []

    def run(self, csv_path: str) -> BacktestResult:
        logger.info(f"Starting hybrid backtest for {self.symbol}...")
        
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['symbol'] != self.symbol: continue
                
                tick = Tick(
                    symbol=row['symbol'],
                    price=float(row['price']),
                    epoch=int(row['epoch'])
                )
                
                self._process_tick(tick)
                
                if self.risk_mgr.is_kill_switch_active:
                    logger.warning(f"Backtest halted: {self.risk_mgr.kill_reason}")
                    break

        # Force close any active trade at end of data
        if self.active_trade:
            # We don't have a final tick here, but for simplicity let's assume
            # the last tick was used to check exit in _process_tick.
            pass

        return self.get_report()

    def _process_tick(self, tick: Tick):
        # 1. Update Candle Builder (M5)
        closed_candle = self.candle_builder.process_tick(tick)
        
        # 2. Continuous Tick Exits (Active Position Only)
        if self.active_trade:
            # Get current features for exit manager
            features = self.engine.feature_gen.process_tick(tick)
            
            # A. Check Logic-based exits (Duration, RSI Reversal, Risk Surge)
            exit_reason = self.exit_manager.evaluate_exit(self.symbol, features)
            
            if exit_reason:
                self._close_position(tick, exit_reason)
            else:
                # B. Check Price-based exits (Take Profit / Stop Loss)
                self._check_hard_exits(tick)
        
        # 3. Candle-Based Entries (Only when M5 closes)
        if not self.active_trade and closed_candle:
            # Use the tick that closed the candle to evaluate signals
            signal = self.engine.process_tick(tick)
            if signal:
                self._open_position(signal)

    def _check_hard_exits(self, tick: Tick):
        trade = self.active_trade
        if not trade: return
        
        entry = trade['entry_price']
        action = trade['action']
        
        # Simple TP/SL logic (Fixed USD target/risk)
        # Note: This could be converted to a more complex pip-based manager
        if action == "BUY":
            if tick.price >= entry + self.tp_amount:
                self._close_position(tick, "Take Profit")
            elif tick.price <= entry - self.sl_amount:
                self._close_position(tick, "Stop Loss")
        elif action == "SELL":
            if tick.price <= entry - self.tp_amount:
                self._close_position(tick, "Take Profit")
            elif tick.price >= entry + self.sl_amount:
                self._close_position(tick, "Stop Loss")

    def _open_position(self, signal: TradeSignal):
        # Adaptive Sizing
        sl_price = signal.price - self.sl_amount if signal.action == "BUY" else signal.price + self.sl_amount
        size = self.bankroll.calculate_position_size(
            signal.price, sl_price, spike_prob=signal.spike_risk
        )
        
        if size <= 0:
            return

        self.active_trade = {
            "symbol": signal.symbol,
            "action": signal.action,
            "entry_price": signal.price,
            "size": size,
            "entry_epoch": signal.epoch,
            "confidence": signal.confidence,
            "risk_at_entry": signal.spike_risk,
            "reason": signal.reason
        }
        
        # Register in exit manager for duration tracking
        self.exit_manager.register_trade(signal, current_rsi=signal.confidence * 100) # Simplified RSI for registration

    def _close_position(self, tick: Tick, reason: str):
        entry_price = self.active_trade['entry_price']
        size = self.active_trade['size']
        action = self.active_trade['action']
        
        pnl = (tick.price - entry_price) * size if action == "BUY" else (entry_price - tick.price) * size
        
        self.bankroll.update_balance(pnl)
        self.risk_mgr.record_trade(pnl, self.bankroll.balance)
        
        self.trades_history.append({
            **self.active_trade,
            "exit_price": tick.price,
            "exit_epoch": tick.epoch,
            "exit_reason": reason,
            "pnl": pnl
        })
        
        self.active_trade = None
        self.exit_manager.close_trade(self.symbol)

    def get_report(self) -> BacktestResult:
        from analytics.performance import PerformanceAnalytics
        
        analytics = PerformanceAnalytics(self.trades_history, self.initial_balance)
        metrics = analytics.calculate_all()
        
        return BacktestResult(
            symbol=self.symbol,
            initial_balance=self.initial_balance,
            final_balance=self.bankroll.balance,
            total_trades=metrics['total_trades'],
            win_rate=metrics['win_rate'],
            max_drawdown=metrics['max_drawdown'],
            profit_factor=metrics['profit_factor'],
            net_pnl=self.bankroll.balance - self.initial_balance
        )
