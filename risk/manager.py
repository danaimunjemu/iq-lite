import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from models.trading import RiskState

logger = logging.getLogger(__name__)

class RiskManager:
    """
    Electronic Gatekeeper that enforces trading limits and safety rules.
    Prevents execution if any risk parameter is breached.
    """
    def __init__(
        self, 
        max_daily_loss: float = 500.0, 
        daily_profit_target: float = 1000.0,
        max_drawdown: float = 1000.0,
        max_trades_per_day: int = 50,
        max_trades_per_hour: int = 10
    ):
        # Limits
        self.max_daily_loss = max_daily_loss
        self.daily_profit_target = daily_profit_target
        self.max_drawdown = max_drawdown
        self.max_trades_per_day = max_trades_per_day
        self.max_trades_per_hour = max_trades_per_hour

        # State
        self.daily_pnl = 0.0
        self.peak_balance = 0.0
        self.current_drawdown = 0.0
        self.is_kill_switch_active = False
        self.kill_reason: Optional[str] = None
        
        # Trade History for frequency control
        self.trade_timestamps: List[datetime] = []

    def can_trade(self) -> (bool, str):
        """
        Evaluates all risk rules. 
        Returns (True, "OK") if safe, or (False, reason) if blocked.
        """
        if self.is_kill_switch_active:
            return False, f"Kill switch active: {self.kill_reason}"

        # 1. Daily Profit Target reached (Yield Protection)
        if self.daily_pnl >= self.daily_profit_target:
            self._activate_kill_switch(f"Daily profit target hit (${self.daily_pnl:.2f})")
            return False, self.kill_reason

        # 2. Daily Loss Check
        if self.daily_pnl <= -self.max_daily_loss:
            self._activate_kill_switch(f"Daily loss limit reached (${self.daily_pnl:.2f})")
            return False, self.kill_reason

        # 3. Drawdown Check
        if self.current_drawdown >= self.max_drawdown:
            self._activate_kill_switch(f"Max drawdown reached (${self.current_drawdown:.2f})")
            return False, self.kill_reason

        # 3. Frequency Check (Day)
        day_ago = datetime.now() - timedelta(days=1)
        trades_today = [t for t in self.trade_timestamps if t > day_ago]
        if len(trades_today) >= self.max_trades_per_day:
            return False, f"Max daily trade frequency reached ({len(trades_today)})"

        # 4. Frequency Check (Hour)
        hour_ago = datetime.now() - timedelta(hours=1)
        trades_this_hour = [t for t in self.trade_timestamps if t > hour_ago]
        if len(trades_this_hour) >= self.max_trades_per_hour:
            return False, f"Max hourly trade frequency reached ({len(trades_this_hour)})"

        return True, "Rules pass"

    def record_trade(self, pnl: float, current_balance: float):
        """
        Updates risk metrics after a trade is completed.
        """
        self.daily_pnl += pnl
        self.trade_timestamps.append(datetime.now())
        
        # Update Peak and Drawdown
        if current_balance > self.peak_balance:
            self.peak_balance = current_balance
            self.current_drawdown = 0.0
        else:
            self.current_drawdown = self.peak_balance - current_balance

        # Immediate breach checks
        self.can_trade() 

    def _activate_kill_switch(self, reason: str):
        self.is_kill_switch_active = True
        self.kill_reason = reason
        logger.critical(f"!!! RISK KILL SWITCH ACTIVATED: {reason} !!!")

    def reset_kill_switch(self):
        """Manual reset required to resume trading."""
        self.is_kill_switch_active = False
        self.kill_reason = None
        self.daily_pnl = 0.0  # Reset daily stats on manual override
        logger.info("Risk Manager kill switch reset manually.")

    def get_state(self) -> RiskState:
        day_ago = datetime.now() - timedelta(days=1)
        return RiskState(
            daily_pnl=self.daily_pnl,
            max_drawdown=self.current_drawdown,
            trade_count_24h=len([t for t in self.trade_timestamps if t > day_ago]),
            is_kill_switch_active=self.is_kill_switch_active,
            last_kill_reason=self.kill_reason
        )
