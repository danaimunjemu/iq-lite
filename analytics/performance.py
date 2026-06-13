import math
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class PerformanceAnalytics:
    """
    Calculates key trading performance metrics from trade history.
    """
    def __init__(self, trades: List[Dict[str, Any]], initial_balance: float):
        self.trades = trades
        self.initial_balance = initial_balance
        self.pnls = [t['pnl'] for t in trades]

    def calculate_all(self) -> Dict[str, Any]:
        if not self.trades:
            return {
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "win_rate": 0.0,
                "expectancy": 0.0,
                "profit_factor": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "total_trades": 0
            }

        wins = [p for p in self.pnls if p > 0]
        losses = [abs(p) for p in self.pnls if p <= 0]
        
        avg_win = sum(wins) / len(wins) if wins else 0.0
        avg_loss = sum(losses) / len(losses) if losses else 0.0
        win_rate = len(wins) / len(self.pnls)
        
        profit_factor = sum(wins) / sum(losses) if losses and sum(losses) > 0 else float('inf')
        
        # Expectancy: (Win Rate * Avg Win) - (Loss Rate * Avg Loss)
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        
        return {
            "sharpe_ratio": self._calculate_sharpe(),
            "max_drawdown": self._calculate_max_drawdown(),
            "win_rate": round(win_rate, 4),
            "expectancy": round(expectancy, 4),
            "profit_factor": round(profit_factor, 4),
            "avg_win": round(avg_win, 4),
            "avg_loss": round(avg_loss, 4),
            "total_trades": len(self.pnls)
        }

    def _calculate_sharpe(self, risk_free_rate: float = 0.0) -> float:
        """
        Calculates the Sharpe Ratio based on trade-by-trade returns.
        """
        if len(self.pnls) < 2:
            return 0.0
            
        # Standard Deviation of PnL
        mean_pnl = sum(self.pnls) / len(self.pnls)
        variance = sum((p - mean_pnl) ** 2 for p in self.pnls) / len(self.pnls)
        std_dev = math.sqrt(variance)
        
        if std_dev == 0:
            return 0.0
            
        return round((mean_pnl - risk_free_rate) / std_dev, 4)

    def _calculate_max_drawdown(self) -> float:
        """
        Calculates the maximum peak-to-trough decline.
        """
        balance = self.initial_balance
        peak = self.initial_balance
        max_dd = 0.0
        
        for pnl in self.pnls:
            balance += pnl
            if balance > peak:
                peak = balance
            
            dd = peak - balance
            if dd > max_dd:
                max_dd = dd
                
        return round(max_dd, 4)

    def generate_interpretation(self, metrics: Dict[str, Any]) -> str:
        """
        Translates raw metrics into actionable trading advice.
        """
        pf = metrics['profit_factor']
        sharpe = metrics['sharpe_ratio']
        exp = metrics['expectancy']
        
        interpretation = []
        
        # Profit Factor Interpretation
        if pf > 2.0: interpretation.append("Strategy is highly profitable and robust.")
        elif pf > 1.5: interpretation.append("Strategy is sustainable with a good edge.")
        elif pf > 1.0: interpretation.append("Strategy is borderline profitable; consider refining entries.")
        else: interpretation.append("Strategy is currently losing money.")
        
        # Sharpe Interpretation
        if sharpe > 1.0: interpretation.append("Excellent risk-adjusted returns.")
        elif sharpe > 0.5: interpretation.append("Good risk control, but returns may be volatile.")
        
        # Expectancy Interpretation
        interpretation.append(f"On average, you can expect to make ${exp:.2f} per trade.")
        
        return " ".join(interpretation)
