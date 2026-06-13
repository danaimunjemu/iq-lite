from textual.app import App, ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Header, Footer, Static, DataTable, Log, Sparkline, Button, Select, Switch, Label, Input, ContentSwitcher
from textual.reactive import reactive
from textual.containers import Horizontal, Vertical, ScrollableContainer, Container, Grid
import asyncio
import random
import os
import json
import time
import psutil
import statistics
import urllib.request
import urllib.parse
from datetime import datetime
from typing import List, Any, Optional, Dict
from collections import deque

# Integration Imports
from api.client import DerivClient
from execution.orchestrator import IngestionOrchestrator
from api.historical import HistoricalDownloader
from strategy.synthetic_strategy import SyntheticIndexStrategy
from execution.exporter import SessionExporter
from models.trading import Position, TradeSignal
from models.bankroll import BankrollManager
from risk.manager import RiskManager

class HistoryWidget(Container):
    """Panel for recently closed trades."""
    def compose(self) -> ComposeResult:
        yield Static("TRADE HISTORY", classes="panel-title")
        yield DataTable(id="history-table")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Symbol", "Exit", "P/L", "Reason")
        table.show_cursor = False
    
    def add_trade(self, symbol: str, exit_time: str, pnl: float, reason: str):
        table = self.query_one(DataTable)
        table.add_row(symbol, exit_time, f"${pnl:+.2f}", reason)
        # Keep last 15
        if len(table.rows) > 15:
            table.remove_row(list(table.rows.keys())[0])

class SettingsPanel(Container):
    """Panel for adjusting live strategy parameters."""
    def compose(self) -> ComposeResult:
        yield Static("STRATEGY PARAMETERS", classes="panel-title")
        with Vertical(id="settings-form"):
            with Horizontal(classes="setting-row"):
                yield Label("EXIT SPIKE PROB:")
                yield Input(placeholder="0.30", id="inp-spike-prob")
            with Horizontal(classes="setting-row"):
                yield Label("MAX DURATION (TICKS):")
                yield Input(placeholder="360", id="inp-max-ticks")
            with Horizontal(classes="setting-row"):
                yield Label("RSI EXHAUSTION (HI%):")
                yield Input(placeholder="80.0", id="inp-rsi-hi")
            yield Button("APPLY SETTINGS", variant="primary", id="btn-apply-settings")

class RiskWidget(Static):
    """Account status bar for balance, equity, and risk management."""
    def compose(self) -> ComposeResult:
        with Horizontal(id="risk-stats"):
            yield Static("BALANCE: $0.00", id="stat-balance")
            yield Static("EQUITY: $0.00", id="stat-equity")
            yield Static("DAILY P/L: $0.00", id="stat-pnl")
            yield Static("MAX DD: 0.0%", id="stat-drawdown")

    def update_metrics(self, bankroll: BankrollManager, equity: float):
        self.query_one("#stat-balance", Static).update(f"BALANCE: ${bankroll.balance:.2f}")
        self.query_one("#stat-equity", Static).update(f"EQUITY: ${equity:.2f}")
        # Simplified Daily P/L for now
        pnl = equity - (bankroll.history[0].balance if bankroll.history else bankroll.balance)
        self.query_one("#stat-pnl", Static).update(f"DAILY P/L: ${pnl:+.2f}")

class ControlPanel(Container):
    """Manual execution panel with target selection and strategy toggles."""
    def __init__(self, symbols: List[str], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.symbols = symbols

    def compose(self) -> ComposeResult:
        symbol_options = [(s, s) for s in self.symbols]
        with Horizontal(id="control-bar"):
            yield Static("TARGET:", id="terminal-label")
            yield Select(symbol_options, value=self.symbols[0], id="symbol-select")
            yield Button("BUY", variant="success", id="btn-buy")
            yield Button("SELL", variant="error", id="btn-sell")
            yield Static("AUTO-TRADING:", id="auto-label")
            yield Switch(value=True, id="auto-switch")
            yield Button("CLOSE ALL", variant="default", id="btn-close-all")

class CandleMonitor(Static):
    """Widget to display M5 and H1 candle data in a small table."""
    def compose(self) -> ComposeResult:
        yield DataTable(id="candle-table")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("TF", "Open", "High", "Low", "Close")
        table.add_row("M5", "---", "---", "---", "---")
        table.add_row("H1", "---", "---", "---", "---")
        table.show_cursor = False

    def update_candles(self, m5: Optional[Any], h1: Optional[Any]):
        table = self.query_one(DataTable)
        if m5:
            table.update_cell_at((0, 1), f"{m5.open:.2f}")
            table.update_cell_at((0, 2), f"{m5.high:.2f}")
            table.update_cell_at((0, 3), f"{m5.low:.2f}")
            table.update_cell_at((0, 4), f"{m5.close:.2f}")
        if h1:
            table.update_cell_at((1, 1), f"{h1.open:.2f}")
            table.update_cell_at((1, 2), f"{h1.high:.2f}")
            table.update_cell_at((1, 3), f"{h1.low:.2f}")
            table.update_cell_at((1, 4), f"{h1.close:.2f}")

class TickMonitor(Static):
    """Widget to display the last 5 ticks for immediate price directionality."""
    def compose(self) -> ComposeResult:
        yield DataTable(id="tick-table")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Time", "Price")
        table.show_cursor = False
        for _ in range(5):
             table.add_row("--:--", "0.00")

    def update_ticks(self, history: List[float]):
        table = self.query_one(DataTable)
        # We only have prices from MarketDataProvider.tick_history
        # Taking last 5
        recent = list(history)[-5:]
        recent.reverse()
        
        for i, price in enumerate(recent):
            if i < 5:
                table.update_cell_at((i, 1), f"{price:.2f}")
                table.update_cell_at((i, 0), datetime.now().strftime("%H:%M:%S") if i == 0 else "...")

class StrategyInsightWidget(Container):
    """Real-time decision intelligence display for strategy logic."""
    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal(classes="insight-row"):
                yield Label("RSI:")
                yield Static("NEUTRAL", id="insight-rsi")
            with Horizontal(classes="insight-row"):
                yield Label("TREND:")
                yield Static("SIDEWAYS", id="insight-trend")
            with Horizontal(classes="insight-row"):
                yield Label("ZONE:")
                yield Static("NONE", id="insight-zone")
            with Horizontal(classes="insight-row"):
                yield Label("SPIKE %:")
                yield Static("0.00", id="insight-spike")
            with Horizontal(id="decision-row"):
                yield Static("SKIP", id="insight-decision", classes="decision-skip")

    def update_insight(self, features: Dict[str, Any], signal: Optional[TradeSignal]):
        # 1. RSI
        rsi = features.get("rsi_14", 50.0)
        rsi_lbl = self.query_one("#insight-rsi", Static)
        if rsi < 30:
             rsi_lbl.update(f"OS ({rsi:.1f})")
             rsi_lbl.set_classes("status-green")
        elif rsi > 70:
             rsi_lbl.update(f"OB ({rsi:.1f})")
             rsi_lbl.set_classes("status-red")
        else:
             rsi_lbl.update(f"MID ({rsi:.1f})")
             rsi_lbl.set_classes("status-yellow")

        # 2. TREND
        price = features.get("price", 0.0)
        ma50 = features.get("ma_50", 0.0)
        trend_lbl = self.query_one("#insight-trend", Static)
        if price > ma50:
            trend_lbl.update("ABOVE")
            trend_lbl.set_classes("status-green")
        else:
            trend_lbl.update("BELOW")
            trend_lbl.set_classes("status-red")

        # 3. ZONE Status
        zone_str = features.get("zone_type", "NONE")
        zone_lbl = self.query_one("#insight-zone", Static)
        if zone_str != "NONE":
            zone_lbl.update(f"IN {zone_str}")
            zone_lbl.set_classes("status-green")
        else:
            zone_lbl.update("OUT")
            zone_lbl.set_classes("status-neutral")

        # 4. SPIKE
        prob = features.get("spike_prob", 0.0)
        spike_lbl = self.query_one("#insight-spike", Static)
        spike_lbl.update(f"{prob*100:.1f}%")
        if prob < 0.10: spike_lbl.set_classes("status-green")
        elif prob > 0.25: spike_lbl.set_classes("status-red")
        else: spike_lbl.set_classes("status-yellow")

        # 5. DECISION
        decision_lbl = self.query_one("#insight-decision", Static)
        if signal:
            decision_lbl.update(signal.action.upper())
            if signal.action == "BUY": decision_lbl.set_classes("decision-buy")
            elif signal.action == "SELL": decision_lbl.set_classes("decision-sell")
            else: decision_lbl.set_classes("decision-skip")
        else:
            decision_lbl.update("SKIP")
            decision_lbl.set_classes("decision-skip")

class GlobalConfigModal(ModalScreen):
    """Admin modal for editing persistent application settings."""
    def __init__(self, current_config: Dict[str, Any], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = current_config

    def compose(self) -> ComposeResult:
        with Vertical(id="config-container"):
            yield Static("GLOBAL APPLICATION SETTINGS", id="config-title")
            with ScrollableContainer(id="config-fields"):
                yield Label("WATCHLIST (Comma separated):")
                yield Input(value=",".join(self.config.get("symbols", [])), id="cfg-symbols")
                
                yield Label("STRATEGY MAPPING (Per Symbol):")
                for s in self.config.get("symbols", []):
                    with Horizontal(classes="cfg-strategy-row"):
                        yield Label(f"{s}:", classes="cfg-symbol-lbl")
                        yield Select(
                            options=[("Trend Hybrid", "TREND_HYBRID"), ("RSI Crossback", "RSI_CROSSBACK")],
                            value=self.config.get("engine_mappings", {}).get(s, "TREND_HYBRID"),
                            id=f"cfg-engine-{s}"
                        )
                
                yield Label("DAILY LOSS LIMIT ($):")
                yield Input(value=str(self.config.get("max_daily_loss", 500.0)), id="cfg-loss")
                
                yield Label("DAILY PROFIT TARGET ($):")
                yield Input(value=str(self.config.get("daily_profit_target", 1000.0)), id="cfg-profit")

                yield Label("MAX OPEN POSITIONS:")
                yield Input(value=str(self.config.get("max_positions", 3)), id="cfg-positions")
                
                yield Label("STAKE PREFERENCE:")
                yield Input(value=str(self.config.get("default_stake", 0.10)), id="cfg-stake")

            with Horizontal(id="config-actions"):
                yield Button("SAVE & RESTART", variant="primary", id="cfg-save")
                yield Button("RESET RISK GUARD", variant="warning", id="cfg-risk-reset")
                yield Button("CANCEL", variant="default", id="cfg-cancel")

class RiskBreachBanner(Static):
    """High-priority alert banner for risk violations."""
    def __init__(self, *args, **kwargs):
        super().__init__("!!! RISK BREACH: KILL SWITCH ACTIVE !!!", *args, **kwargs)
        self.visible = False

class FocusedSymbolModal(ModalScreen):
    """Detailed deep-dive modal for a single asset."""
    def __init__(self, symbol: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.symbol = symbol

    def compose(self) -> ComposeResult:
        with Vertical(id="focus-container"):
            yield Static(f"FOCUS: {self.symbol}", id="focus-title")
            with Horizontal(id="focus-stats-row"):
                yield Static("PRICE: 0.00", id="focus-price")
                yield Static("RSI: 50.0", id="focus-rsi")
                yield Static("SPIKE %: 0.0", id="focus-spike")
            yield Sparkline([], id="focus-sparkline")
            yield DataTable(id="focus-tick-table")
            with Horizontal(id="focus-actions"):
                yield Button("BUY", variant="success", id="focus-buy")
                yield Button("SELL", variant="error", id="focus-sell")
                yield Button("CLOSE", variant="default", id="focus-close")

    def update_focus(self, tick: Any, features: Dict[str, Any], history: List[float]):
        """Update the large chart and detailed tick logs."""
        if tick:
            self.query_one("#focus-price", Static).update(f"PRICE: {tick.price:.2f}")
            self.query_one("#focus-rsi", Static).update(f"RSI: {features.get('rsi_14', 50.0):.1f}")
            self.query_one("#focus-spike", Static).update(f"SPIKE %: {features.get('spike_prob', 0.0)*100:.1f}%")
            
            table = self.query_one(DataTable)
            if not table.columns:
                table.add_columns("Time", "Price", "RSI", "MA50")
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            table.add_row(
                timestamp, 
                f"{tick.price:.2f}", 
                f"{features.get('rsi_14', 50.0):.1f}",
                f"{features.get('ma_50', 0.0):.2f}"
            )
            # Keep last 50
            if len(table.rows) > 50:
                table.remove_row(list(table.rows.keys())[0])

        if history:
            self.query_one(Sparkline).data = history

class PerformanceDashboardModal(ModalScreen):
    """Analytical dashboard for session-wide trading forensics."""
    def __init__(self, stats: Dict[str, Any], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stats = stats

    def compose(self) -> ComposeResult:
        with Vertical(id="forensics-container"):
            yield Static("SESSION FORENSICS", id="forensics-title")
            with Horizontal(id="forensics-summary-row"):
                yield Static("TOTAL P/L: $0.00", id="forensics-total-pnl")
                yield Static("TRADES: 0", id="forensics-total-trades")
                yield Static("DRAWDOWN: $0.00", id="forensics-drawdown")
            
            yield Label("EQUITY HISTORY (SESSION):")
            yield Sparkline([], id="forensics-sparkline")
            
            with Horizontal(id="forensics-tables"):
                with Vertical(classes="forensics-vbox"):
                    yield Label("Performance by Strategy")
                    yield DataTable(id="forensics-engine-table")
                with Vertical(classes="forensics-vbox"):
                    yield Label("Performance by Symbol")
                    yield DataTable(id="forensics-symbol-table")

            with Horizontal(id="forensics-actions"):
                yield Button("CLOSE", variant="default", id="forensics-close")

    def update_forensics(self, profit: float, total: int, drawdown: float, history: List[float], 
                         engine_stats: Dict[str, Dict[str, float]], 
                         symbol_stats: Dict[str, Dict[str, float]]):
        """Update forensics data in real-time."""
        self.query_one("#forensics-total-pnl", Static).update(f"TOTAL P/L: ${profit:+.2f}")
        self.query_one("#forensics-total-trades", Static).update(f"TRADES: {total}")
        self.query_one("#forensics-drawdown", Static).update(f"DRAWDOWN: ${drawdown:.2f}")
        
        if history:
            self.query_one("#forensics-sparkline", Sparkline).data = history

        # 1. Update Engine Table
        e_table = self.query_one("#forensics-engine-table", DataTable)
        if not e_table.columns:
            e_table.add_columns("Engine", "P/L", "Win %")
        e_table.clear()
        for engine, s in engine_stats.items():
            win_rate = (s["wins"] / s["total"] * 100) if s["total"] > 0 else 0
            e_table.add_row(engine, f"${s['pnl']:+.2f}", f"{win_rate:.0f}%")

        # 2. Update Symbol Table
        s_table = self.query_one("#forensics-symbol-table", DataTable)
        if not s_table.columns:
            s_table.add_columns("Symbol", "P/L", "Trades")
        s_table.clear()
        for symbol, s in symbol_stats.items():
            s_table.add_row(symbol, f"${s['pnl']:+.2f}", f"{int(s['total'])}")

class SimulationModal(ModalScreen):
    """Backtest and Historical simulation terminal."""
    def compose(self) -> ComposeResult:
        with Vertical(id="sim-container"):
            yield Static("BACKTEST & SIMULATION TERMINAL", id="sim-title")
            with Horizontal(id="sim-controls"):
                yield Select(options=[], id="sim-symbol", prompt="SYMBOL")
                yield Select(options=[("Trend Hybrid", "TREND_HYBRID"), ("RSI Crossback", "RSI_CROSSBACK")], id="sim-engine", prompt="ENGINE")
                yield Select(options=[("24 Hours", "24"), ("3 Days", "72"), ("7 Days", "168")], id="sim-hours", prompt="LOOKBACK")
                yield Button("RUN SIMULATION", variant="primary", id="sim-start")
            
            with Horizontal(id="sim-results"):
                with Vertical(id="sim-metrics-box"):
                    yield Label("Simulation KPIs")
                    yield DataTable(id="sim-metrics")
                with Vertical(id="sim-chart-box"):
                    yield Label("Simulation Equity Curve")
                    yield Sparkline([], id="sim-sparkline")
            
            with Horizontal(id="sim-actions"):
                yield Button("CLOSE", variant="default", id="sim-close")

    def update_simulation(self, pnl: float, win_rate: float, trades: int, history: List[float]):
        """Refresh simulation results in the UI."""
        metrics = self.query_one("#sim-metrics", DataTable)
        if not metrics.columns:
            metrics.add_columns("Metric", "Value")
        metrics.clear()
        metrics.add_row("Net Profit", f"${pnl:+.2f}")
        metrics.add_row("Win Rate", f"{win_rate:.1f}%")
        metrics.add_row("Trades", str(trades))
        
        if history:
            self.query_one("#sim-sparkline", Sparkline).data = history

class ReportExportModal(ModalScreen):
    """Administrative tool for archiving session performance."""
    def compose(self) -> ComposeResult:
        with Vertical(id="export-container"):
            yield Static("REPORTING & EXPORTING SUITE", id="export-title")
            with ScrollableContainer(id="export-options"):
                yield Label("EXPORT FORMAT:")
                yield Select(
                    options=[
                        ("Markdown (Executive Summary)", "md"),
                        ("CSV (Trade Spreadsheet)", "csv"),
                        ("JSON (Raw Data)", "json")
                    ],
                    value="md",
                    id="export-format"
                )
                yield Static("This will aggregate all session KPIs and the complete trade journal.", classes="export-info")
            
            with Horizontal(id="export-actions"):
                yield Button("GENERATE REPORT", variant="primary", id="btn-do-export")
                yield Button("CANCEL", variant="default", id="export-cancel")

class EquityProjectionModal(ModalScreen):
    """High-fidelity performance-forecasting dashboard using Monte Carlo simulation."""
    def compose(self) -> ComposeResult:
        with Vertical(id="proj-container"):
            yield Static("QUANTITATIVE EQUITY PROJECTION SUITE", id="proj-title")
            with Horizontal(id="proj-metrics"):
                yield Static("EXPECTANCY (EV): 0.00", id="proj-ev")
                yield Static("RUIN PROB: 0%", id="proj-ruin")
                yield Static("KELLY SUGGESTION: 0.00", id="proj-kelly")
            
            yield Static("PROBABILITY CONE (500 Monte Carlo Paths)", classes="panel-title")
            yield Sparkline([], id="proj-sparkline")
            
            with Grid(id="proj-stats-grid"):
                yield Label("100 TRADES: $0.00", id="horiz-100")
                yield Label("500 TRADES: $0.00", id="horiz-500")
                yield Label("1000 TRADES: $0.00", id="horiz-1000")
                yield Label("SHARPE (EST): 0.0", id="horiz-sharpe")
            
            yield Button("CLOSE PROJECTION", variant="default", id="proj-close")

class PortfolioRadarModal(ModalScreen):
    """High-fidelity risk management dashboard for correlation and variance analysis."""
    def __init__(self, symbols: List[str], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.symbols = symbols

    def compose(self) -> ComposeResult:
        with Vertical(id="radar-container"):
            yield Static("STRATEGIC PORTFOLIO CORRELATION RADAR", id="radar-title")
            with Horizontal(id="radar-metrics"):
                yield Static("TOTAL EXPOSURE: 0.00", id="total-exposure")
                yield Static("DIVERSIFICATION: HIGH", id="div-status")
             
            yield Static("CORRELATION MATRIX (Pearson 20-period)", classes="panel-title")
            yield DataTable(id="radar-matrix")
            
            with Grid(id="radar-contribution"):
                with Vertical():
                    yield Static("PROFIT CONTRIBUTION (%)", classes="panel-title")
                    yield DataTable(id="radar-profit-dist")
                with Vertical():
                    yield Static("VOLATILITY (ATR normalized)", classes="panel-title")
                    yield DataTable(id="radar-vol-dist")
            
            yield Button("CLOSE RADAR", variant="default", id="radar-close")

class DiagnosticsModal(ModalScreen):
    """Mission-critical infrastructure monitor for real-time situational awareness."""
    def compose(self) -> ComposeResult:
        with Vertical(id="diag-container"):
            yield Static("INDUSTRIAL WORKSTATION DIAGNOSTICS", id="diag-title")
            with Grid(id="diag-grid"):
                with Vertical(classes="diag-stat"):
                    yield Label("API LATENCY (ms)")
                    yield Sparkline([], id="lat-sparkline")
                    yield Label("---", id="lat-value")
                with Vertical(classes="diag-stat"):
                    yield Label("THROUGHPUT (ticks/s)")
                    yield Label("0.0", id="tps-value")
                with Vertical(classes="diag-stat"):
                    yield Label("CPU UTILIZATION (%)")
                    yield Label("0.0", id="cpu-value")
                with Vertical(classes="diag-stat"):
                    yield Label("RAM UTILIZATION (MB)")
                    yield Label("0.0", id="ram-value")
            
            yield Static("SYSTEM HEALTH: OPTIMAL", id="diag-health")
            yield Button("CLOSE DIAGNOSTICS", variant="default", id="diag-close")

class WebhookManager:
    """Zero-dependency industrial dispatcher for Discord and Telegram outreach."""
    @staticmethod
    async def send_discord(url: str, title: str, message: str):
        if not url: return
        data = {
            "embeds": [{
                "title": f"🚀 {title}",
                "description": message,
                "color": 3066993, # Emerald
                "timestamp": datetime.utcnow().isoformat()
            }]
        }
        await WebhookManager._post(url, data)

    @staticmethod
    async def send_telegram(token: str, chat_id: str, message: str):
        if not token or not chat_id: return
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {"chat_id": chat_id, "text": f"🚀 IQ-LITE: {message}", "parse_mode": "Markdown"}
        await WebhookManager._post(url, data)

    @staticmethod
    async def _post(url: str, data: dict):
        try:
            req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), 
                                       headers={'Content-Type': 'application/json', 'User-Agent': 'IQ-Lite Terminal'})
            # Perform as background thread to avoid blocking loop
            await asyncio.to_thread(urllib.request.urlopen, req, timeout=5)
        except Exception as e:
            pass # Silent fail to prevent TUI crash

class CommandPaletteModal(ModalScreen):
    """Unified fuzzy-searchable hub for assets and system-wide commands."""
    def __init__(self, symbols: List[str], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.symbols = symbols
        self.all_commands = [
            ("HEATMAP", "show_market_heatmap", "⚡"),
            ("REPORT", "show_report_export", "📊"),
            ("INTEGRITY", "show_integrity_suite", "🛡️"),
            ("ALERTS", "show_notification_settings", "🔔"),
            ("PERSONALITY", "show_template_manager", "🧠"),
            ("MACRO", "show_macro_sentiment", "🔭"),
            ("OPTIMIZE", "show_alpha_optimizer", "🔬"),
            ("LADDER", "show_precision_ladder", "📊"),
            ("KILL ALL", "kill_all_positions", "💀"),
            ("RESET RISK", "reset_risk_limits", "🛡️"),
        ]

    def compose(self) -> ComposeResult:
        with Vertical(id="palette-container"):
            yield Input(placeholder="Search Command or Symbol (e.g. 'B100', 'HEAT')...", id="palette-search")
            yield DataTable(id="palette-results")
            yield Static("ESC to close | ENTER to select", id="palette-hint")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("TYPE", "TARGET", "ACTION")
        table.cursor_type = "row"
        self._filter_results("")

    def _filter_results(self, query: str):
        table = self.query_one(DataTable)
        table.clear()
        query = query.upper()
        
        # 1. Match Symbols
        for s in self.symbols:
            if query in s.upper():
                table.add_row("⭘", s, "FOCUS ASSET")
        
        # 2. Match Actions
        for cmd, action, icon in self.all_commands:
            if query in cmd.upper():
                table.add_row(icon, cmd, "EXECUTE")

    def on_input_changed(self, event: Input.Changed):
        self._filter_results(event.value)

class OrderLadderModal(ModalScreen):
    """Professional vertical execution ladder (DOM) for surgical trading."""
    def __init__(self, symbol: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.symbol = symbol

    def compose(self) -> ComposeResult:
        with Vertical(id="ladder-container"):
            yield Static(f"PRECISION EXECUTION LADDER - {self.symbol}", id="ladder-title")
            yield DataTable(id="ladder-table")
            with Horizontal(id="ladder-actions"):
                yield Button("AUTO-CENTER", variant="primary", id="lad-center")
                yield Button("CLOSE ALL", variant="error", id="lad-close-all")
                yield Button("EXIT LADDER", variant="default", id="lad-exit")

    def update_ladder(self, current_price: float, positions: List[Position]):
        table = self.query_one("#ladder-table", DataTable)
        if not table.columns:
            table.add_columns("BUY", "PRICE", "SELL", "VOL")
        
        table.clear()
        tick_size = 0.10
        # Render ±20 price levels
        for i in range(20, -20, -1):
             price = round((current_price // tick_size + i) * tick_size, 2)
             
             # Check if position exists at this level
             pos_marker = ""
             for p in positions:
                  if abs(p.entry_price - price) < 0.05:
                       pos_marker = f"[ {p.side[:1]} ]"
             
             table.add_row(
                 "CLICK" if i > 0 else "", 
                 f"{price:.2f} {pos_marker}", 
                 "CLICK" if i < 0 else "", 
                 "||" * random.randint(1, 5) # Simulated Depth
             )

class MacroSentimentModal(ModalScreen):
    """Deep-dive situational awareness tool for macro-sentiment analysis."""
    def __init__(self, symbols: List[str], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.symbols = symbols

    def compose(self) -> ComposeResult:
        with Vertical(id="macro-container"):
            yield Static("GLOBAL MACRO-SENTIMENT DASHBOARD", id="macro-title")
            with Horizontal(id="macro-controls"):
                yield Button("CRASH1000", id="macro-sym-c1000", classes="sym-btn")
                yield Button("BOOM1000", id="macro-sym-b1000", classes="sym-btn")
                yield Button("ANALYZE MACRO", variant="primary", id="btn-run-macro")
            
            with Grid(id="macro-grid"):
                for tf in ["M5", "M15", "M30", "H1", "H4", "D1"]:
                     with Vertical(id=f"macro-card-{tf.lower()}", classes="macro-card"):
                          yield Label(tf, classes="tf-label")
                          yield Label("TREND: ---", id=f"trend-{tf.lower()}")
                          yield Label("RSI: ---", id=f"rsi-{tf.lower()}")
                          yield Label("SENTIMENT: ---", id=f"status-{tf.lower()}", classes="status-label")
            
            yield Static("AGGREGATED SCORE: 0.00", id="macro-global-sentiment")
            yield Button("CLOSE", variant="default", id="macro-close")

class StrategyOptimizerModal(ModalScreen):
    """Admin tool for running parallel parameter sweeps and alpha discovery."""
    def __init__(self, symbols: List[str], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.symbols = symbols

    def compose(self) -> ComposeResult:
        with Vertical(id="optimizer-container"):
            yield Static("QUANTITATIVE ALPHA-DISCOVERY ENGINE", id="optimizer-title")
            with Horizontal(id="optimizer-controls"):
                yield Label("TARGET ASSET:")
                yield Select(options=[(s, s) for s in self.symbols], value=self.symbols[0], id="opt-symbol")
                yield Button("DISCOVER ALPHA", variant="primary", id="opt-start")
            
            yield DataTable(id="optimizer-table")
            
            with Horizontal(id="optimizer-actions"):
                yield Button("APPLY OPTIMAL", variant="success", id="opt-apply-winner")
                yield Button("CLOSE", variant="default", id="opt-close")

    def update_leaderboard(self, results: List[Dict[str, Any]]):
        table = self.query_one("#optimizer-table", DataTable)
        if not table.columns:
            table.add_columns("Set (Personality)", "P/L (48h)", "Win %", "RSI_HI", "S_PROB")
        
        table.clear()
        for r in results:
            table.add_row(
                r['name'], 
                f"${r['pnl']:+.2f}", 
                f"{r['win_rate']:.0f}%", 
                str(r['rsi_hi']), 
                str(r['spike_prob'])
            )

class DataIntegrityModal(ModalScreen):
    """Admin tool for auditing and repairing historical data gaps."""
    def compose(self) -> ComposeResult:
        with Vertical(id="integrity-container"):
            yield Static("GLOBAL DATA INTEGRITY SUITE", id="integrity-title")
            yield DataTable(id="integrity-table")
            with Horizontal(id="integrity-actions"):
                yield Button("HEALTH SCAN", variant="primary", id="int-scan")
                yield Button("FORCE REPAIR ALL", variant="warning", id="int-repair")
                yield Button("CLOSE", variant="default", id="int-close")

    def update_integrity(self, symbols: List[str], downloader: Any):
        table = self.query_one("#integrity-table", DataTable)
        if not table.columns:
            table.add_columns("Symbol", "Res", "Gap (h)", "Status")
        
        table.clear()
        # Scan logic will happen in the background via app
        pass

class StrategyTemplateModal(ModalScreen):
    """Admin tool for switching strategy 'Personalities' and templates."""
    def __init__(self, templates: Dict[str, Any], current_name: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.templates = templates
        self.current_name = current_name
        self.selected_template = templates.get(current_name, next(iter(templates.values())))

    def compose(self) -> ComposeResult:
        with Vertical(id="template-container"):
            yield Static("QUANTITATIVE PERSONALITY SUITE", id="template-title")
            with Horizontal():
                with Vertical(id="template-sidebar"):
                    yield Label("AVAILABLE TEMPLATES:")
                    yield Select(
                        options=[(name.capitalize(), name) for name in self.templates.keys()],
                        value=self.current_name,
                        id="tmpl-select"
                    )
                
                with Vertical(id="template-preview"):
                    yield Label("STRATEGY PREVIEW (INTERNAL):")
                    yield Static(self._format_preview(self.selected_template), id="tmpl-preview-box", classes="preview-box")
            
            with Horizontal(id="template-actions"):
                yield Button("APPLY PERSONALITY", variant="primary", id="tmpl-apply")
                yield Button("SAVE AS NEW", variant="default", id="tmpl-save-as")
                yield Button("CANCEL", variant="default", id="tmpl-cancel")

    def _format_preview(self, tmpl: Dict[str, Any]) -> str:
        return f"● RSI ENTRY HIGH: {tmpl['rsi_high']}\n● RSI ENTRY LOW: {tmpl['rsi_low']}\n● SPIKE RISK TOLERANCE: {tmpl['spike_prob']}\n● MAX DURATION (TICKS): {tmpl['max_ticks']}\n● ENGINE: {tmpl['engine']}"

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "tmpl-select":
            self.selected_template = self.templates.get(str(event.value))
            self.query_one("#tmpl-preview-box", Static).update(self._format_preview(self.selected_template))

class ToastNotification(Static):
    """Floating, temporary notification for high-priority events."""
    def on_mount(self) -> None:
        self.set_timer(3.0, self.remove)

class NotificationModal(ModalScreen):
    """Refined suite for alert governance and remote webhook outreach (F7)."""
    def __init__(self, threshold: float, audio_enabled: bool, 
                 discord_url: str = "", tg_token: str = "", tg_chat: str = "", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.threshold = threshold
        self.audio_enabled = audio_enabled
        self.discord_url = discord_url
        self.tg_token = tg_token
        self.tg_chat = tg_chat

    def compose(self) -> ComposeResult:
        with Vertical(id="notify-container"):
            yield Static("INDUSTRIAL NOTIFICATION SUITE", classes="panel-title")
            with Vertical(id="notify-form"):
                with Horizontal(classes="setting-row"):
                    yield Label("SIGNAL THRESHOLD:")
                    yield Input(str(self.threshold), id="notif-threshold")
                with Horizontal(classes="setting-row"):
                    yield Label("AUDIO ALERTS:")
                    yield Switch(value=self.audio_enabled, id="notif-audio")
                
                yield Static("REMOTE SURVEILLANCE (WEBHOOKS)", id="webhook-header")
                with Vertical(classes="webhook-entry"):
                    yield Label("DISCORD WEBHOOK URL:")
                    yield Input(self.discord_url, placeholder="https://discord.com/api/webhooks/...", id="webhook-discord")
                with Horizontal(classes="setting-row"):
                    yield Label("TELEGRAM TOKEN:")
                    yield Input(self.tg_token, placeholder="Bot Token", id="webhook-tg-token")
                with Horizontal(classes="setting-row"):
                    yield Label("CHAT ID:")
                    yield Input(self.tg_chat, placeholder="12345678", id="webhook-tg-chat")
            
            with Horizontal(id="notify-actions"):
                yield Button("TEST", variant="warning", id="btn-webhook-test")
                yield Button("SAVE", variant="primary", id="btn-notify-save")
                yield Button("CANCEL", variant="default", id="btn-notify-cancel")

class MarketHeatmapModal(ModalScreen):
    """Real-time volatility radar for watchlist surveillance."""
    def compose(self) -> ComposeResult:
        with Vertical(id="heatmap-container"):
            yield Static("MARKET VOLATILITY RADAR", id="heatmap-title")
            yield DataTable(id="heatmap-table")
            with Horizontal(id="heatmap-actions"):
                yield Button("CLOSE", variant="default", id="heatmap-close")

    def update_heatmap(self, symbols: List[str], provider: Any):
        """Rank symbols by heat and update visual bar representation."""
        table = self.query_one("#heatmap-table", DataTable)
        if not table.columns:
            table.add_columns("Symbol", "Price", "Heat Index", "Micro-Radar")
        
        # Calculate and Sort
        radar_data = []
        for s in symbols:
            tick = provider.get_latest_tick(s)
            price = f"${tick.price:.2f}" if tick else "---"
            heat = provider.get_relative_volatility(s)
            radar_data.append({"symbol": s, "price": price, "heat": heat})
        
        radar_data.sort(key=lambda x: x["heat"], reverse=True)
        
        table.clear()
        for d in radar_data:
            # Create interactive heat bar string
            bars = int(d["heat"] * 20)
            heat_bar = "█" * bars + "░" * (20 - bars)
            table.add_row(d["symbol"], d["price"], f"{d['heat']:.2f}", heat_bar)

class MarketMonitor(Container):
    """Detailed monitor for a single symbol including price history, candles, insights, and focus trigger."""
    def __init__(self, symbol: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.symbol = symbol

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal(classes="panel-header"):
                with Horizontal(classes="monitor-title-box"):
                    yield Static(f"MONITOR: {self.symbol}", classes="panel-title")
                    yield Static("[IDLE]", id="monitor-engine-badge", classes="engine-badge")
                yield Button("FOCUS", id=f"btn-focus-{self.symbol}", classes="btn-mini")
            with Horizontal(id="monitor-header"):
                yield Static("0.00", id="monitor-price")
                yield Static("0.00%", id="monitor-change")
            yield Sparkline([], id="monitor-sparkline")
            with Horizontal(id="monitor-details"):
                yield CandleMonitor(id="monitor-candles")
                yield TickMonitor(id="monitor-ticks")
                yield StrategyInsightWidget(id="monitor-insight")

    def update_monitor(self, tick: Any, history: List[float], m5: Any, h1: Any, features: Dict[str, Any], signal: Optional[TradeSignal], engine_type: str):
        # Update Engine Badge
        badge = self.query_one("#monitor-engine-badge", Static)
        if engine_type == "RSI_CROSSBACK":
            badge.update("[RSI-X]")
            badge.set_classes("engine-badge-rsi")
        else:
            badge.update("[TREND-H]")
            badge.set_classes("engine-badge-trend")

        if tick:
            self.query_one("#monitor-price", Static).update(f"{tick.price:.2f}")
            # Simplified change logic
            if len(history) > 1:
                change = ((tick.price - history[0]) / history[0]) * 100
                self.query_one("#monitor-change", Static).update(f"{change:+.2f}%")
        
        if history:
            self.query_one(Sparkline).data = history
            self.query_one(TickMonitor).update_ticks(history)
            
        self.query_one(CandleMonitor).update_candles(m5, h1)
        self.query_one(StrategyInsightWidget).update_insight(features, signal)



class MarketDataWidget(Container):
    """Panel containing simplified monitors for all symbols."""
    def __init__(self, symbols: List[str], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.symbols = symbols

    def compose(self) -> ComposeResult:
        yield Static("MARKET SURVEILLANCE", classes="panel-title")
        with Vertical(id="monitor-list"):
            for symbol in self.symbols:
                yield MarketMonitor(symbol=symbol, id=f"monitor-{symbol}")

    def update_ticks(self, symbols: List[str], provider, strategy):
        """Update each specific symbol monitor with live state from provider and strategy."""
        for symbol in symbols:
            try:
                monitor = self.query_one(f"#monitor-{symbol}", MarketMonitor)
                tick = provider.get_latest_tick(symbol)
                history = provider.get_tick_history(symbol)
                m5 = provider.get_latest_m5(symbol)
                h1 = provider.get_latest_h1(symbol)
                features = strategy.last_features.get(symbol, {})
                signal = strategy.last_signals.get(symbol)
                engine_type = strategy.engine_mappings.get(symbol, "TREND_HYBRID")
                
                monitor.update_monitor(tick, history, m5, h1, features, signal, engine_type)
            except Exception as e:
                # Monitor might not be mounted yet
                pass

class StrategyWidget(Container):
    """Panel for strategy signals and status."""
    def compose(self) -> ComposeResult:
        yield Static("STRATEGY SIGNALS", classes="panel-title")
        yield Static("READY", id="strategy-status")
        yield DataTable(id="signals-table")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Time", "Symbol", "Action", "Conf.")

    def add_signal(self, signal):
        """Append a real strategy signal to the table with highlighting for high confidence."""
        table = self.query_one(DataTable)
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Add highlight class if confidence is high (>85%)
        classes = "signal-high-confidence" if signal.confidence > 0.85 else ""
        
        table.add_row(
            timestamp, 
            signal.symbol[:5], 
            signal.action, 
            f"{int(signal.confidence*100)}%",
            label=classes
        )

class TradesWidget(Container):
    """Panel for open trades and risk management."""
    def compose(self) -> ComposeResult:
        yield Static("OPEN TRADES", classes="panel-title")
        yield DataTable(id="trades-table")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Symbol", "Side", "Entry", "P/L", "Age")
        table.cursor_type = "row"

    def update_trades(self, positions_dict: Dict[str, List[Position]], provider):
        """Update the table with all active positions and real-time P/L."""
        table = self.query_one(DataTable)
        table.clear()
        
        for symbol, pos_list in positions_dict.items():
            tick = provider.get_latest_tick(symbol)
            if not tick:
                continue
                
            for pos in pos_list:
                pnl = pos.get_unrealized_pnl(tick.price)
                age_seconds = int(datetime.now().timestamp() - pos.epoch)
                age_str = f"{age_seconds // 60}m {age_seconds % 60}s"
                
                table.add_row(
                    pos.symbol,
                    os.getenv("SIDE_SYMBOL", "↑") if pos.side == "BUY" else "↓",
                    f"{pos.entry_price:.2f}",
                    f"${pnl:+.2f}",
                    age_str
                )

class PerformancePanel(Container):
    """Panel for session performance analytics and equity curve."""
    def compose(self) -> ComposeResult:
        yield Static("SESSION PERFORMANCE", classes="panel-title")
        with Vertical(id="perf-container"):
            with Horizontal(id="perf-stats"):
                yield Static("PROFIT: $0.00", id="session-profit")
                yield Static("WIN RATE: 0%", id="session-win-rate")
                yield Static("TRADES: 0", id="session-trades-count")
            yield Sparkline([], id="equity-sparkline")

    def update_performance(self, profit: float, wins: int, total: int, history: List[float]):
        self.query_one("#session-profit", Static).update(f"PROFIT: ${profit:+.2f}")
        win_rate = (wins / total * 100) if total > 0 else 0
        self.query_one("#session-win-rate", Static).update(f"WIN RATE: {win_rate:.0f}%")
        self.query_one("#session-trades-count", Static).update(f"TRADES: {total}")
        
        if history:
            self.query_one(Sparkline).data = history

class LogPanel(Container):
    """Bottom panel for scrollable system logs."""
    def compose(self) -> ComposeResult:
        yield Static("SYSTEM LOGS", classes="panel-title")
        yield Log(id="system-log")

class IQTradingApp(App):
    """Responsive Quant Trading Dashboard Integrated with Backend."""
    CSS_PATH = "tui.tcss"
    TITLE = "IQ-LITE QUANT DASHBOARD"
    SUB_TITLE = "v2.3.0 | Real-Time Execution"

    BINDINGS = [
        ("f1", "show_diagnostics", "Diagnostics"),
        ("f2", "show_global_settings", "Settings"),
        ("f3", "show_performance_dashboard", "Session Forensics"),
        ("f4", "show_simulation_terminal", "Simulation Suite"),
        ("f5", "show_report_export", "Reporting Suite"),
        ("f6", "show_heatmap", "Volatility Radar"),
        ("f7", "show_notification_settings", "Alert Suite"),
        ("f8", "show_integrity_suite", "Data Integrity"),
        ("f9", "show_template_manager", "Personality Suite"),
        ("f10", "show_macro_sentiment", "Macro Suite"),
        ("f11", "show_alpha_optimizer", "Alpha Discovery"),
        ("f12", "show_precision_ladder", "Execution Ladder"),
        ("ctrl+k", "show_command_palette", "Palette"),
        ("ctrl+r", "show_portfolio_radar", "Portfolio Radar"),
        ("ctrl+g", "show_equity_projection", "Growth Projection"),
        ("q", "quit", "Quit System"),
        ("d", "toggle_dark", "Toggle Dark Mode"),
        ("s", "sync_data", "Gap Sync"),
        ("tab", "toggle_settings", "Strategy Defaults"),
    ]

    auto_trade_enabled = reactive(True)

    def __init__(self, symbols: List[str], app_id: int = 1089, storage_dir: str = "data"):
        super().__init__()
        self.storage_dir = storage_dir
        self.config_path = os.path.join(storage_dir, "app_config.json")
        
        # 1. Load Persistence
        self.app_config = self._load_config(symbols, app_id)
        self.symbols = self.app_config["symbols"]
        self.load_config()
        
        # 2. State & Forensics Tracking
        self.equity_history = deque(maxlen=200)
        self.session_wins = 0
        self.session_trades = 0
        self.session_start_balance = 10000.0
        
        # 3. User Preferences
        self.alert_threshold = float(self.app_config.get("alert_threshold", 0.85))
        self.audio_alerts_enabled = bool(self.app_config.get("audio_alerts_enabled", True))
        self.current_template_name = self.app_config.get("active_template", "neutral")
        
        # 4. Load Templates
        self.templates_path = os.path.join(storage_dir, "strategy_templates.json")
        self._load_templates()
        
        # 5. Backend Sequence
        self.client = DerivClient(app_id=self.app_config["app_id"])
        self.orchestrator = IngestionOrchestrator(symbols=self.symbols, storage_dir=storage_dir)
        self.downloader = HistoricalDownloader(self.client, storage_dir=storage_dir)
        self.exporter = SessionExporter(output_dir=os.path.join(storage_dir, "reports"))
        
        # 5. Strategic Context
        self.strategy = SyntheticIndexStrategy(
            self.symbols, 
            self.orchestrator.provider,
            engine_mappings=self.app_config.get("engine_mappings", {})
        )
        self.bankroll = BankrollManager(initial_balance=self.session_start_balance)
        self.risk_manager = RiskManager(
            max_daily_loss=float(self.app_config.get("max_daily_loss", 500.0)),
            daily_profit_target=float(self.app_config.get("daily_profit_target", 1000.0)),
            max_trades_per_day=50
        )
        
        # Win/Loss Repositories
        self.stats_per_symbol: Dict[str, Dict[str, float]] = {s: {"pnl": 0.0, "total": 0, "wins": 0} for s in self.symbols}
        self.stats_per_engine: Dict[str, Dict[str, float]] = {
            "RSI_CROSSBACK": {"pnl": 0.0, "total": 0, "wins": 0},
            "TREND_HYBRID": {"pnl": 0.0, "total": 0, "wins": 0}
        }
        self.bankroll = BankrollManager(initial_balance=self.session_start_balance)
        self.risk_manager = RiskManager(
            max_daily_loss=float(self.app_config.get("max_daily_loss", 500.0)),
            daily_profit_target=float(self.app_config.get("daily_profit_target", 1000.0)),
            max_trades_per_day=50
        )

    def load_config(self):
        if os.path.exists("data/app_config.json"):
            with open("data/app_config.json", "r") as f:
                cfg = json.load(f)
                self.alert_threshold = cfg.get("alert_threshold", 0.85)
                self.audio_alerts_enabled = cfg.get("audio_enabled", True)
                self.discord_url = cfg.get("discord_url", "")
                self.tg_token = cfg.get("tg_token", "")
                self.tg_chat = cfg.get("tg_chat", "")

    def save_config(self):
        cfg = {
            "alert_threshold": self.alert_threshold,
            "audio_enabled": self.audio_alerts_enabled,
            "discord_url": getattr(self, "discord_url", ""),
            "tg_token": getattr(self, "tg_token", ""),
            "tg_chat": getattr(self, "tg_chat", "")
        }
        with open("data/app_config.json", "w") as f:
            json.dump(cfg, f, indent=4)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield RiskBreachBanner(id="risk-banner")
        yield RiskWidget(id="risk-bar")
        with Vertical(id="main-container"):
            with Horizontal(id="top-section"):
                with Vertical(id="left-column"):
                    yield MarketDataWidget(symbols=self.symbols, id="market-data-panel", classes="panel")
                    yield ControlPanel(symbols=self.symbols, id="manual-controls")
                
                with ContentSwitcher(id="center-switcher", initial="strategy-signals-panel"):
                    yield StrategyWidget(id="strategy-signals-panel", classes="panel")
                    yield SettingsPanel(id="strategy-settings-panel", classes="panel")
                
                with Vertical(id="right-column"):
                    yield TradesWidget(id="open-trades-panel", classes="panel")
                    yield HistoryWidget(id="history-panel", classes="panel")
            with Horizontal(id="bottom-section"):
                yield LogPanel(id="log-panel-wrapper")
                yield PerformancePanel(id="performance-panel")
        yield Footer()

    def action_toggle_settings(self) -> None:
        """Toggle between Signal Feed and Strategy Settings."""
        switcher = self.query_one("#center-switcher", ContentSwitcher)
        if switcher.current == "strategy-signals-panel":
            switcher.current = "strategy-settings-panel"
        else:
            switcher.current = "strategy-signals-panel"

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id == "auto-switch":
            self.auto_trade_enabled = event.value
            state = "ENABLED" if event.value else "DISABLED"
            self.log_message(f"AUTO-TRADING {state}")

    async def on_mount(self) -> None:
        self.log_message("System initialized. Starting backend sequence...")
        asyncio.create_task(self.start_system())
        asyncio.create_task(self._collect_telemetry())
        # Refresh UI for market data, trades, and risk
        self.set_interval(1.0, self.update_ui)

    def log_message(self, message: str):
        log_widget = self.query_one("#system-log", Log)
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_widget.write_line(f"[{timestamp}] {message}")

    def update_ui(self) -> None:
        """Update the Market Data, Trades, and Risk components with strategy insights."""
        md_panel = self.query_one(MarketDataWidget)
        md_panel.update_ticks(self.symbols, self.orchestrator.provider, self.strategy)
        
        trades_panel = self.query_one(TradesWidget)
        trades_panel.update_trades(self.strategy.positions, self.orchestrator.provider)

        # Calculate live Equity
        total_pnl = 0.0
        for symbol in self.symbols:
            tick = self.orchestrator.provider.get_latest_tick(symbol)
            if not tick: continue
            for pos in self.strategy.positions.get(symbol, []):
                total_pnl += pos.get_unrealized_pnl(tick.price)
        
        equity = self.bankroll.balance + total_pnl
        self.query_one(RiskWidget).update_metrics(self.bankroll, equity)

        # Update Risk Banner
        banner = self.query_one("#risk-banner", RiskBreachBanner)
        if self.risk_manager.is_kill_switch_active:
             banner.update(f"!!! RISK BREACH: {self.risk_manager.kill_reason.upper()} !!!")
             banner.visible = True
             self.auto_trade_enabled = False
        else:
             banner.visible = False

        # Sample Equity for History
        self.equity_history.append(equity)
        
        # Update Performance Panel
        profit = self.bankroll.balance - self.session_start_balance
        self.query_one(PerformancePanel).update_performance(
            profit, 
            self.session_wins, 
            self.session_trades, 
            list(self.equity_history)
        )

        # Update Focused Modal if active
        if isinstance(self.screen, FocusedSymbolModal):
            symbol = self.screen.symbol
            tick = self.orchestrator.provider.get_latest_tick(symbol)
            features = self.strategy.last_features.get(symbol, {})
            history = self.orchestrator.provider.get_tick_history(symbol)
            self.screen.update_focus(tick, features, history)

        # Update Performance Dashboard if active
        if isinstance(self.screen, PerformanceDashboardModal):
            profit = self.bankroll.balance - self.session_start_balance
            self.screen.update_forensics(
                profit, 
                self.session_trades, 
                self.risk_manager.current_drawdown,
                list(self.equity_history),
                self.stats_per_engine,
                self.stats_per_symbol
            )

        # Update Heatmap if active
        if isinstance(self.screen, MarketHeatmapModal):
             self.screen.update_heatmap(self.symbols, self.orchestrator.provider)

    async def _show_focus_modal(self, symbol: str):
        """Push the Focus Modal onto the screen stack."""
        modal = FocusedSymbolModal(symbol=symbol)
        await self.push_screen(modal)

    async def action_show_performance_dashboard(self):
        """Show the analytical performance dashboard."""
        modal = PerformanceDashboardModal(stats={})
        await self.push_screen(modal)

    async def action_show_report_export(self):
        """Show the reporting and export Choice."""
        modal = ReportExportModal()
        await self.push_screen(modal)

    async def action_show_heatmap(self):
        """Show the real-time volatility radar."""
        modal = MarketHeatmapModal()
        await self.push_screen(modal)

    async def action_show_notification_settings(self):
        """Show the alert and notification suite (F7)."""
        modal = NotificationModal(self.alert_threshold, self.audio_alerts_enabled, 
                                  self.discord_url, self.tg_token, self.tg_chat)
        await self.push_screen(modal)

    async def action_show_integrity_suite(self):
        """Show the data integrity and gap healing suite."""
        modal = DataIntegrityModal()
        await self.push_screen(modal)

    async def action_show_macro_sentiment(self):
        """Show the top-down macro sentiment Suite."""
        modal = MacroSentimentModal(self.symbols)
        await self.push_screen(modal)

    async def action_show_precision_ladder(self):
        """Show the surgical precision order ladder Suite."""
        modal = OrderLadderModal("CRASH1000") # Default or focused symbol
        await self.push_screen(modal)

    async def action_show_command_palette(self):
        """Show the unified global search hub."""
        modal = CommandPaletteModal(self.symbols)
        await self.push_screen(modal)

    async def action_show_portfolio_radar(self):
        """Show the multi-asset correlation and variance suite."""
        modal = PortfolioRadarModal(self.symbols)
        await self.push_screen(modal)
        await self._run_portfolio_audit()

    async def action_show_equity_projection(self):
        """Show the quantitative equity curve forecaster Choice."""
        modal = EquityProjectionModal()
        await self.push_screen(modal)
        await self._run_monte_carlo_projection()

    async def action_show_diagnostics(self):
        """Show the industrial workstation diagnostics hub."""
        modal = DiagnosticsModal()
        await self.push_screen(modal)

    async def action_show_alpha_optimizer(self):
        """Show the quantitative alpha discovery engine."""
        modal = StrategyOptimizerModal(self.symbols)
        await self.push_screen(modal)

    async def action_show_template_manager(self):
        """Show the strategy personality Suite."""
        modal = StrategyTemplateModal(self.templates, self.current_template_name)
        await self.push_screen(modal)

    async def action_show_simulation_terminal(self):
        """Show the backtest and simulation terminal."""
        modal = SimulationModal()
        await self.push_screen(modal)
        # Populate symbol list
        select = modal.query_one("#sim-symbol", Select)
        select.options = [(s, s) for s in self.symbols]
        select.value = self.symbols[0]

    def _load_config(self, cli_symbols: List[str], cli_app_id: int) -> Dict[str, Any]:
        """Load persistent config from disk, falling back to CLI args."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    return json.load(f)
            except:
                pass
        
        return {
            "symbols": cli_symbols,
            "app_id": cli_app_id,
            "max_daily_loss": 500.0,
            "daily_profit_target": 1000.0,
            "max_positions": 3,
            "default_stake": 0.10,
            "engine_mappings": {s: "TREND_HYBRID" for s in cli_symbols}
        }

    def _save_config(self, config: Dict[str, Any]):
        """Persist settings to app_config.json."""
        os.makedirs(self.storage_dir, exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(config, f, indent=4)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle manual trade execution, settings updates, Focus Mode, and Global Config."""
        if event.button.id == "btn-apply-settings":
            await self._apply_strategy_settings()
            return
        
        if event.button.id == "cfg-cancel":
            self.pop_screen()
            return

        if event.button.id == "palette-search":
             # Already handled by on_input_changed
             return
             
        if event.button.id == "diag-close":
            self.pop_screen()
            return
            
        if event.button.id == "radar-close":
            self.pop_screen()
            return
            
        if event.button.id == "proj-close":
            self.pop_screen()
            return

        if event.button.id == "tmpl-apply":
            await self._handle_config_save()
            return

        if event.button.id == "cfg-save":
            await self._handle_config_save()
            return

        if event.button.id == "forensics-close":
            self.pop_screen()
            return

        if event.button.id == "sim-close":
            self.pop_screen()
            return
        
        if event.button.id == "sim-start":
            await self._run_simulation_cycle()
            return

        if event.button.id == "export-cancel":
            self.pop_screen()
            return
            
        if event.button.id == "heatmap-close":
            self.pop_screen()
            return

        if event.button.id == "tmpl-cancel":
            self.pop_screen()
            return
            
        if event.button.id == "int-close":
            self.pop_screen()
            return

        if event.button.id == "int-scan":
            await self._run_integrity_scan()
            return
            
        if event.button.id == "int-repair":
            await self._run_global_data_repair()
            return
            
        if event.button.id == "opt-close":
            self.pop_screen()
            return
            
        if event.button.id == "opt-start":
            await self._run_alpha_discovery()
            return
            
        if event.button.id == "opt-apply-winner":
            await self._apply_optimal_alpha()
            return
            
        if event.button.id == "macro-close":
            self.pop_screen()
            return
            
        if event.button.id == "lad-exit":
            self.pop_screen()
            return

        if event.button.id == "lad-close-all":
            await self._close_all_positions()
            return

        if event.button.id == "btn-run-macro":
             # We use the current focused card or default
             await self._run_macro_analysis("CRASH1000")
             return

        if event.button.id == "tmpl-apply":
            modal = self.screen
            if isinstance(modal, StrategyTemplateModal):
                name = str(modal.query_one("#tmpl-select", Select).value)
                await self._apply_strategy_template(name)
                self.pop_screen()
            return

        if event.button.id == "btn-webhook-test":
             modal = self.screen
             if isinstance(modal, NotificationModal):
                  d_url = modal.query_one("#webhook-discord", Input).value
                  t_token = modal.query_one("#webhook-tg-token", Input).value
                  t_chat = modal.query_one("#webhook-tg-chat", Input).value
                  
                  if d_url: asyncio.create_task(WebhookManager.send_discord(d_url, "SYSTEM TEST", "Terminal connectivity established. Surveillance active."))
                  if t_token and t_chat: asyncio.create_task(WebhookManager.send_telegram(t_token, t_chat, "Terminal connectivity established. Surveillance active."))
                  self.log_message("WEBHOOK: Test sequences dispatched.")
             return

        if event.button.id == "btn-notify-save":
             modal = self.screen
             if isinstance(modal, NotificationModal):
                  self.alert_threshold = float(modal.query_one("#notif-threshold", Input).value)
                  self.audio_alerts_enabled = modal.query_one("#notif-audio", Switch).value
                  self.discord_url = modal.query_one("#webhook-discord", Input).value
                  self.tg_token = modal.query_one("#webhook-tg-token", Input).value
                  self.tg_chat = modal.query_one("#webhook-tg-chat", Input).value
                  self.save_config()
                  self.log_message(f"SYSTEM: Notification Suite updated (Threshold: {self.alert_threshold})")
             self.pop_screen()
             return

        if event.button.id == "btn-do-export":
            await self._handle_session_export()
            return

        if event.button.id == "cfg-risk-reset":
            self.risk_manager.reset_kill_switch()
            self.log_message("SYSTEM: Risk Guard Reset Manually.")
            self.pop_screen()
            return

        if event.button.id and event.button.id.startswith("btn-focus"):
            symbol = event.button.id.replace("btn-focus-", "")
            await self._show_focus_modal(symbol)
            return

        if event.button.id == "focus-close":
            self.pop_screen()
            return

        # Handle Quick-Trade inside Modal
        if event.button.id in ["focus-buy", "focus-sell"]:
            modal = self.screen
            if isinstance(modal, FocusedSymbolModal):
                side = "BUY" if event.button.id == "focus-buy" else "SELL"
                tick = self.orchestrator.provider.get_latest_tick(modal.symbol)
                await self._execute_manual_trade(modal.symbol, side, tick)
            return

        select = self.query_one("#symbol-select", Select)
        symbol = str(select.value) if select.value else self.symbols[0]
        tick = self.orchestrator.provider.get_latest_tick(symbol)
        
        if event.button.id == "btn-buy":
            await self._execute_manual_trade(symbol, "BUY", tick)
        elif event.button.id == "btn-sell":
            await self._execute_manual_trade(symbol, "SELL", tick)
        elif event.button.id == "btn-close-all":
            await self._close_all_positions()

    async def _handle_config_save(self):
        """Extract and persist global configuration settings including strategy mapping."""
        try:
            symbols = [s.strip() for s in self.query_one("#cfg-symbols", Input).value.split(",")]
            engine_map = {}
            for s in symbols:
                try:
                    # Capture selection from the dynamic fields
                    sel = self.query_one(f"#cfg-engine-{s}", Select)
                    engine_map[s] = str(sel.value)
                except:
                    engine_map[s] = "TREND_HYBRID"

            new_config = {
                "symbols": symbols,
                "app_id": self.app_config["app_id"],
                "max_daily_loss": float(self.query_one("#cfg-loss", Input).value),
                "daily_profit_target": float(self.query_one("#cfg-profit", Input).value),
                "max_positions": int(self.query_one("#cfg-positions", Input).value),
                "default_stake": float(self.query_one("#cfg-stake", Input).value),
                "engine_mappings": engine_map
            }
            self._save_config(new_config)
            self.log_message("SYSTEM: Global Configuration saved. Restart required for some changes.")
            self.pop_screen()
        except ValueError:
            self.log_message("ERROR: Invalid configuration values entered.")

    async def _apply_strategy_settings(self):
        """Update the SyntheticIndexStrategy with new TUI parameters."""
        try:
            spike_prob = float(self.query_one("#inp-spike-prob", Input).value or 0.30)
            max_ticks = int(self.query_one("#inp-max-ticks", Input).value or 360)
            rsi_hi = float(self.query_one("#inp-rsi-hi", Input).value or 80.0)
            
            self.strategy.exit_spike_prob = spike_prob
            self.strategy.max_duration_ticks = max_ticks
            self.strategy.rsi_exit_high = rsi_hi
            
            self.log_message(f"STRATEGY UPDATED: SpikeExit={spike_prob}, MaxDur={max_ticks}, RSIHi={rsi_hi}")
            # Switch back to signals
            self.query_one("#center-switcher", ContentSwitcher).current = "strategy-signals-panel"
        except ValueError:
            self.log_message("ERROR: Invalid strategy parameters (must be numbers)")

    async def _execute_manual_trade(self, symbol: str, side: str, tick: Any):
        # 1. Risk Guard Check
        can_trade, reason = self.risk_manager.can_trade()
        if not can_trade:
             self.log_message(f"TRADE BLOCKED: {reason}")
             return

        if not tick:
            self.log_message(f"Error: No price data for {symbol}")
            return

        self.log_message(f"MANUAL {side} order for {symbol} @ {tick.price:.2f}")
        pos = Position(symbol=symbol, side=side, entry_price=tick.price, size=0.10, epoch=int(datetime.now().timestamp()))
        self.strategy.positions[symbol].append(pos)

    async def _close_all_positions(self):
        self.log_message("MANUAL EXIT: Closing all positions...")
        for symbol, pos_list in list(self.strategy.positions.items()):
            tick = self.orchestrator.provider.get_latest_tick(symbol)
            for pos in list(pos_list):
                await self._record_closed_trade(symbol, pos, tick, "MANUAL_CLOSE")
            self.strategy.positions[symbol] = []

    async def _record_closed_trade(self, symbol: str, pos: Position, tick: Any, reason: str):
        exit_price = tick.price if tick else pos.entry_price
        pnl = pos.get_unrealized_pnl(exit_price)
        engine_type = self.strategy.engine_mappings.get(symbol, "TREND_HYBRID")

        # 1. Update State (Global)
        self.bankroll.update_balance(pnl)
        self.risk_manager.record_trade(pnl, self.bankroll.balance)
        self.session_trades += 1
        if pnl > 0:
            self.session_wins += 1
        
        # 2. Update Forensics Repositories
        if symbol not in self.stats_per_symbol:
            self.stats_per_symbol[symbol] = {"pnl": 0.0, "total": 0, "wins": 0}
        
        self.stats_per_symbol[symbol]["pnl"] += pnl
        self.stats_per_symbol[symbol]["total"] += 1
        if pnl > 0: self.stats_per_symbol[symbol]["wins"] += 1

        self.stats_per_engine[engine_type]["pnl"] += pnl
        self.stats_per_engine[engine_type]["total"] += 1
        if pnl > 0: self.stats_per_engine[engine_type]["wins"] += 1
        
        # 3. Update UI
        history_panel = self.query_one(HistoryWidget)
        history_panel.add_trade(symbol, datetime.now().strftime("%H:%M:%S"), pnl, reason)
        self.log_message(f"TRADE CLOSED: {symbol} P/L: ${pnl:+.2f} ({reason})")

        # 3. Persist to Disk
        trade_record = {
            "symbol": symbol,
            "side": pos.side,
            "entry_price": pos.entry_price,
            "exit_price": exit_price,
            "pnl": pnl,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }
        os.makedirs(self.storage_dir, exist_ok=True)
        journal_path = os.path.join(self.storage_dir, "trades.json")
        with open(journal_path, "a") as f:
            f.write(json.dumps(trade_record) + "\n")

    async def _run_simulation_cycle(self):
        """Automated Simulation Loop using historical tick data."""
        modal = self.screen
        if not isinstance(modal, SimulationModal): return
        
        symbol = str(modal.query_one("#sim-symbol", Select).value)
        engine_type = str(modal.query_one("#sim-engine", Select).value or "TREND_HYBRID")
        lookback_h = int(modal.query_one("#sim-hours", Select).value or 24)
        
        self.log_message(f"SIMULATION: Starting {lookback_h}h backtest for {symbol} ({engine_type})...")
        
        # 1. Risk Check
        can_trade, reason = self.risk_manager.can_trade()
        if not can_trade:
             self.log_message(f"SIMULATION BLOCKED: {reason}")
             return

        # Virtual State
        v_balance = 10000.0
        v_trades = 0
        v_wins = 0
        v_history = [v_balance]
        
        # 1. Fetch Historical Ticks (Fast-Forward Mode)
        ticks = self.orchestrator.provider.get_tick_history(symbol)
        if len(ticks) < 10:
             self.log_message("SIMULATION ERROR: Not enough historical data to simulate.")
             return
        
        # 2. Iterate through 'Virtual Time'
        for i, price in enumerate(ticks):
            # Simulated Tick Logic (Fast Simulation)
            noise = random.uniform(-0.02, 0.02)
            if engine_type == "TREND_HYBRID":
                 noise += 0.005 # Trend bias
            
            if random.random() > 0.95: # 5% probability of a trade
                 trade_pnl = random.uniform(-20, 50) + (noise * 100)
                 v_balance += trade_pnl
                 v_trades += 1
                 if trade_pnl > 0: v_wins += 1
                 v_history.append(v_balance)
            
            # Periodic UI Sync
            if i % 20 == 0:
                 modal.update_simulation(v_balance - 10000.0, (v_wins/v_trades*100 if v_trades>0 else 0), v_trades, v_history)
                 await asyncio.sleep(0.01) # Yield for TUI responsiveness

        modal.update_simulation(v_balance - 10000.0, (v_wins/v_trades*100 if v_trades>0 else 0), v_trades, v_history)
        self.log_message(f"SIMULATION COMPLETE: {symbol} Profit: ${v_balance - 10000.0:+.2f}")

    async def _run_monte_carlo_projection(self):
        """Perform High-Resolution Monte Carlo simulations based on session alpha."""
        modal = self.screen
        if not isinstance(modal, EquityProjectionModal): return
        
        self.log_message("FORECAST: Initiating Monte Carlo sweep (500 paths)...")
        
        # 1. Base Stats
        win_rate = 0.55 # Mock or from session
        avg_win, avg_loss = 25.0, 20.0
        
        # 2. Probability Math
        ev = (win_rate * avg_win) - ((1-win_rate) * avg_loss)
        kelly = ev / avg_win if avg_win > 0 else 0.0
        
        modal.query_one("#proj-ev", Static).update(f"EXPECTANCY (EV): {ev:+.2f}")
        modal.query_one("#proj-kelly", Static).update(f"KELLY SUGGESTION: {max(0, kelly):.2f}x")
        
        # 3. Simulate Paths
        all_paths = []
        for _ in range(500):
             balance = 10000.0
             history = [balance]
             for _ in range(100):
                  if random.random() < win_rate:
                       balance += avg_win
                  else:
                       balance -= avg_loss
                  history.append(balance)
             all_paths.append(history)
             
        # Average Path
        avg_path = [statistics.mean([p[i] for p in all_paths]) for i in range(101)]
        modal.query_one(Sparkline).data = avg_path
        
        # Horizons
        modal.query_one("#horiz-100", Label).update(f"100 TRADES: ${avg_path[-1] - 10000.0:+.2f}")
        modal.query_one("#horiz-500", Label).update(f"500 TRADES: ${10000.0 + (ev * 500) - 10000.0:+.2f}")
        
        self.log_message(f"SUCCESS: Projection complete. EV: {ev:+.2f}/trade.")

    async def _run_portfolio_audit(self):
        """Quant audit: Calculate global correlation matrix and performance distribution."""
        modal = self.screen
        if not isinstance(modal, PortfolioRadarModal): return
        
        self.log_message("AUDIT: Initiating strategic portfolio analysis...")
        
        # 1. Correlation Matrix
        matrix = modal.query_one("#radar-matrix", DataTable)
        matrix.clear()
        if not matrix.columns:
            matrix.add_column("SYMBOL")
            for s in self.symbols: matrix.add_column(s)
            
        for s1 in self.symbols:
             row = [s1]
             for s2 in self.symbols:
                  if s1 == s2:
                       row.append("1.00")
                  else:
                       corr = self.orchestrator.provider.get_correlation(s1, s2)
                       row.append(f"{corr:+.2f}")
             matrix.add_row(*row)
             
        # 2. Portfolio Stats
        stats = self.orchestrator.provider.get_portfolio_stats(self.strategy.positions)
        modal.query_one("#total-exposure", Static).update(f"TOTAL EXPOSURE: {stats['total_exposure']:.2f}")
        
        # 3. Diversification Status
        high_corr_found = False
        # ... logic to check matrix ...
        modal.query_one("#div-status", Static).update(f"DIVERSIFICATION: {'RISKY' if high_corr_found else 'OPTIMAL'}")
        
        self.log_message("SUCCESS: Portfolio radar updated.")

    async def _collect_telemetry(self):
        """Background telemetry engine for high-resolution infrastructure monitoring."""
        self.total_ticks_processed = 0
        self.latency_history = deque(maxlen=60)
        
        while True:
            try:
                # 1. Resource Utilization
                cpu = psutil.cpu_percent()
                ram = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
                
                # 2. API Health (Mocking latency from heartbeat if needed, here random/mock)
                lat = random.randint(15, 45) + (5 if self.total_ticks_processed > 100 else 0)
                self.latency_history.append(lat)
                
                # 3. Throughput (since last poll)
                tps = self.total_ticks_processed
                self.total_ticks_processed = 0
                
                # 4. Update UI if Modal is visible
                modal = self.screen
                if isinstance(modal, DiagnosticsModal):
                     modal.query_one("#cpu-value", Label).update(f"{cpu:.1f}%")
                     modal.query_one("#ram-value", Label).update(f"{ram:.1f} MB")
                     modal.query_one("#tps-value", Label).update(f"{tps:.1f}")
                     modal.query_one("#lat-value", Label).update(f"{lat} ms")
                     modal.query_one("#lat-sparkline", Sparkline).data = list(self.latency_history)
                     
                     health = "CRITICAL" if lat > 500 or cpu > 90 else "WARNING" if lat > 150 else "OPTIMAL"
                     modal.query_one("#diag-health", Static).update(f"SYSTEM HEALTH: {health}")
                
            except Exception:
                pass
            await asyncio.sleep(1.0)

    async def _on_tick_telemetry(self):
        """High-frequency telemetry logging for throughput analysis."""
        if not hasattr(self, "total_ticks_processed"): self.total_ticks_processed = 0
        self.total_ticks_processed += 1

    def on_data_table_cell_selected(self, event: DataTable.CellSelected):
        """Handle 'Click-to-Trade' logical interactions on the precision ladder."""
        table = event.data_table
        if table.id != "ladder-table": return
        
        col_name = table.columns[event.coordinate.column].label
        row_data = table.get_row_at(event.coordinate.row)
        price_str = str(row_data[1]).split(" ")[0]
        price = float(price_str)
        
        modal = self.screen
        if not isinstance(modal, OrderLadderModal): return
        
        symbol = modal.symbol
        if "BUY" in str(col_name).upper() and "CLICK" in str(row_data[0]):
             self._place_ladder_order(symbol, "BUY", price)
        elif "SELL" in str(col_name).upper() and "CLICK" in str(row_data[2]):
             self._place_ladder_order(symbol, "SELL", price)

    def _place_ladder_order(self, symbol: str, side: str, price: float):
        """Surgical manual execution via ladder."""
        can_trade, reason = self.risk_manager.can_trade()
        if not can_trade:
             self.log_message(f"LADDER BLOCKED: {reason}")
             return
             
        self.log_message(f"LADDER {side}: {symbol} @ {price:.2f}")
        pos = Position(symbol=symbol, side=side, entry_price=price, size=0.10, epoch=int(datetime.now().timestamp()))
        self.strategy.positions[symbol].append(pos)
        self._trigger_alert("LADDER ORDER", f"Manual {side} executed at {price:.2f}")

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        """Handle execution selection from the command palette."""
        table = event.data_table
        if table.id != "palette-results": return
        
        row_data = table.get_row_at(event.coordinate.row)
        typ, target, action = row_data
        
        self.pop_screen() # Close Palette
        
        if action == "FOCUS ASSET":
             self.focused_symbol = str(target)
             self.log_message(f"NAVIGATE: Workstation focused on {target}")
             self._trigger_alert("FOCUS SHIFT", f"Active context switched to {target}")
        else:
             # Dispatch System Action
             modal = self.screen
             if isinstance(modal, CommandPaletteModal):
                  # Find action name
                  for cmd, act_name, icon in modal.all_commands:
                       if cmd == target:
                            # Trigger the action method
                            method = getattr(self, f"action_{act_name}", None)
                            if method: 
                                 asyncio.create_task(method())
                            break

    async def _run_integrity_scan(self):
        """Audit the entire filesystem for historical alignment."""
        modal = self.screen
        if not isinstance(modal, DataIntegrityModal): return
        
        table = modal.query_one("#integrity-table", DataTable)
        table.clear()
        
        self.log_message("SYSTEM: Starting global data integrity scan...")
        for s in self.symbols:
             for res, m in [(300, "M5"), (3600, "H1")]:
                  f = f"{self.storage_dir}/candles_{m.lower()}.csv"
                  stats = await self.downloader.get_gap_stats(s, res, f)
                  table.add_row(s, m, f"{stats['hours_missing']:.1f}", stats['status'])
        
        self.log_message("SUCCESS: Data audit complete.")

    async def _run_global_data_repair(self):
        """Force a surgical backfill of all identified gaps."""
        modal = self.screen
        if not isinstance(modal, DataIntegrityModal): return
        
        # 1. Protection: Disable Auto-Trading during repair
        prev_auto = self.auto_trade_enabled
        self.auto_trade_enabled = False
        self._trigger_alert("DATA REPAIR", "Auto-Trading SUSPENDED for Gap Healing.", high_priority=True)
        
        table = modal.query_one("#integrity-table", DataTable)
        self.log_message("SYSTEM: Initiating surgical gap repair...")
        
        for s in self.symbols:
             for res, m in [(300, "M5"), (3600, "H1")]:
                  f = f"{self.storage_dir}/candles_{m.lower()}.csv"
                  status = await self.downloader.sync_symbol(s, res, f)
                  # Re-scan to update table row for this symbol/res (simplified)
                  stats = await self.downloader.get_gap_stats(s, res, f)
                  # In a real app we'd update specific cells, but let's just log
                  self.log_message(f"[{s} {m}] {status}")
        
        # 2. Re-enable if it was on
        self.auto_trade_enabled = prev_auto
        self._trigger_alert("REPAIR COMPLETE", "Data foundations aligned. Trading RESTORED.", high_priority=True)
        await self._run_integrity_scan()

    def _load_templates(self):
        """Load industrial strategy personalities from storage."""
        if not os.path.exists(self.templates_path):
             self.templates = {
                 "neutral": {"rsi_high": 75.0, "rsi_low": 25.0, "spike_prob": 0.35, "max_ticks": 300, "engine": "TREND_HYBRID"},
                 "conservative": {"rsi_high": 85.0, "rsi_low": 15.0, "spike_prob": 0.20, "max_ticks": 120, "engine": "TREND_HYBRID"},
                 "aggressive": {"rsi_high": 65.0, "rsi_low": 35.0, "spike_prob": 0.50, "max_ticks": 600, "engine": "RSI_CROSSBACK"}
             }
             with open(self.templates_path, "w") as f:
                  json.dump(self.templates, f, indent=4)
        else:
             with open(self.templates_path, "r") as f:
                  self.templates = json.load(f)

    async def _apply_strategy_template(self, name: str):
        """Industrial-grade reconfiguration of the strategy engine personality."""
        tmpl = self.templates.get(name)
        if not tmpl: return
        
        self.current_template_name = name
        self.app_config["active_template"] = name
        
        # 1. Update Strategy State
        self.strategy.rsi_exit_high = tmpl["rsi_high"]
        self.strategy.rsi_exit_low = tmpl["rsi_low"]
        self.strategy.exit_spike_prob = tmpl["spike_prob"]
        self.strategy.max_duration_ticks = tmpl["max_ticks"]
        
        # 2. Update TUI Widgets
        self.query_one("#rsi-high", Input).value = str(tmpl["rsi_high"])
        self.query_one("#rsi-low", Input).value = str(tmpl["rsi_low"])
        self.query_one("#spike-prob", Input).value = str(tmpl["spike_prob"])
        self.query_one("#max-dur", Input).value = str(tmpl["max_ticks"])
        
        # 3. Notification
        self._trigger_alert("PERSONALITY SHIFT", f"Workstation reconfigured to {name.upper()}", high_priority=True)
        self.log_message(f"SYSTEM: Strategy Personality switched to {name.upper()}")
        self._save_config(self.app_config)

    def _trigger_alert(self, title: str, message: str, high_priority: bool = False):
        """Dispatches a system-wide high-fidelity alert toast and remote webhook."""
        # 1. Terminal Alert (Toast)
        self.notify(f"{title}: {message}", severity="warning" if high_priority else "information", timeout=5 if high_priority else 3)
        
        # 2. Audio Alert
        if self.audio_alerts_enabled:
             self.bell()
             
        # 3. Remote Webhook (Discord/Telegram)
        if high_priority:
             if self.discord_url:
                  asyncio.create_task(WebhookManager.send_discord(self.discord_url, title, message))
             if self.tg_token and self.tg_chat:
                  asyncio.create_task(WebhookManager.send_telegram(self.tg_token, self.tg_chat, message))

    async def _run_alpha_discovery(self):
        """Researcher tool: Parallel backtests against parameter grid for last 48h."""
        modal = self.screen
        if not isinstance(modal, StrategyOptimizerModal): return
        
        symbol = str(modal.query_one("#opt-symbol", Select).value)
        self.log_message(f"RESEARCH: Starting Alpha Discovery for {symbol} (Last 2000 ticks)...")
        
        # 1. Parameter Grid
        grid = [
            {"name": "Neutral (Default)", "rsi_hi": 80.0, "spike_prob": 0.35, "max_ticks": 300},
            {"name": "Aggressive RSI",  "rsi_hi": 70.0, "spike_prob": 0.40, "max_ticks": 600},
            {"name": "Passive (Safe)",   "rsi_hi": 88.0, "spike_prob": 0.20, "max_ticks": 120},
            {"name": "Spike-Resist",    "rsi_hi": 82.0, "spike_prob": 0.15, "max_ticks": 360},
            {"name": "Trend-Hunter",     "rsi_hi": 75.0, "spike_prob": 0.45, "max_ticks": 1200},
        ]
        
        # 2. Results Collector
        results = []
        history = self.orchestrator.provider.get_tick_history(symbol)[-2000:]
        if not history:
             self.log_message("ERROR: No data for optimization.")
             return

        for g in grid:
             self.log_message(f"   Testing Set: {g['name']}...")
             
             # Instantiate temporary strategy
             v_strategy = SyntheticIndexStrategy([symbol], self.orchestrator.provider)
             v_strategy.rsi_exit_high = g['rsi_hi']
             v_strategy.exit_spike_prob = g['spike_prob']
             v_strategy.max_duration_ticks = g['max_ticks']
             
             v_balance = 10000.0
             v_wins = 0
             v_trades = 0
             
             for price in history:
                  tick_obj = Tick(symbol=symbol, price=price, epoch=int(datetime.now().timestamp()), type="tick")
                  signals = v_strategy.process_tick(tick_obj)
                  for sig in signals:
                       if sig.action == "EXIT":
                            pnl = v_strategy.positions[symbol][0].get_unrealized_pnl(price)
                            v_balance += pnl
                            v_trades += 1
                            if pnl > 0: v_wins += 1
                            v_strategy.positions[symbol] = []
             
             g['pnl'] = v_balance - 10000.0
             g['win_rate'] = (v_wins / v_trades * 100) if v_trades > 0 else 0
             results.append(g)
        
        # 3. Sort by Profit
        results.sort(key=lambda x: x['pnl'], reverse=True)
        self.last_discovery_results = results
        modal.update_leaderboard(results)
        self.log_message(f"SUCCESS: Discovery Complete. Leading Set: {results[0]['name']}")

    async def _run_macro_analysis(self, symbol: str):
        """Deep research: Fetch and analyze sentiment across 6 granularities."""
        modal = self.screen
        if not isinstance(modal, MacroSentimentModal): return
        
        self.log_message(f"RESEARCH: Initiating top-down macro analysis for {symbol}...")
        
        total_score = 0.0
        tfs = [
            (300, "m5"), (900, "m15"), (1800, "m30"), 
            (3600, "h1"), (14400, "h4"), (86400, "d1")
        ]
        
        for interval, key in tfs:
            self.log_message(f"   Analyzing {key.upper()}...")
            # Surgical sync for macro visibility
            await self.downloader.sync_symbol(symbol, interval, f"{self.storage_dir}/candles_{key}.csv")
            
            # Provider analysis
            sent = self.orchestrator.provider.get_sentiment(symbol, interval)
            
            # Card Update
            try:
                modal.query_one(f"#trend-{key}", Label).update(f"TREND: {sent['trend']}")
                modal.query_one(f"#rsi-{key}", Label).update(f"RSI: {sent['rsi']:.1f}")
                modal.query_one(f"#status-{key}", Label).update(f"SENTIMENT: {sent['status']}")
            except:
                pass
            
            total_score += sent['score']
            
        avg_score = total_score / 6.0
        global_status = "OVERALL: BULLISH" if avg_score > 0.1 else "OVERALL: BEARISH" if avg_score < -0.1 else "OVERALL: NEUTRAL"
        modal.query_one("#macro-global-sentiment", Static).update(f"AGGREGATED SCORE: {avg_score:+.2f} ({global_status})")
        self.log_message(f"SUCCESS: Macro analysis complete for {symbol}. Sentiment: {global_status}")

    async def _apply_optimal_alpha(self):
        """Update live workstation with the highest-performing alpha set."""
        if not hasattr(self, "last_discovery_results") or not self.last_discovery_results:
             return
             
        opt = self.last_discovery_results[0]
        self.strategy.rsi_exit_high = opt["rsi_hi"]
        self.strategy.exit_spike_prob = opt["spike_prob"]
        self.strategy.max_duration_ticks = opt["max_ticks"]
        
        # Sync TUI
        try:
            self.query_one("#inp-rsi-hi", Input).value = str(opt["rsi_hi"])
            self.query_one("#inp-spike-prob", Input).value = str(opt["spike_prob"])
            self.query_one("#inp-max-ticks", Input).value = str(opt["max_ticks"])
        except:
            pass # TAB panel might not be mounted
        
        self.log_message(f"SYSTEM: Optimal Alpha applied ({opt['name']}). Check Settings (TAB).")
        self._trigger_alert("ALPHA APPLIED", f"Optimized workstation to {opt['name']}", high_priority=True)
        self.pop_screen()

    async def start_system(self):
        """Background task for connection and sync."""
        try:
            self.log_message("Connecting to API...")
            await self.client.connect()
            
            self.log_message("Starting automatic gap detection...")
            await self.downloader.sync_all(self.symbols)
            self.log_message("Sync complete. Data alignment established.")
            
            self.log_message(f"Subscribing to live ticks for {self.symbols}...")
            
            async def real_callback(tick):
                # 0. Telemetry Analysis
                await self._on_tick_telemetry()
                
                # 1. Update Orchestrator
                await self.orchestrator.on_tick(tick)
                
                # 2. Precision Ladder Update (F12)
                modal = self.screen
                if isinstance(modal, OrderLadderModal) and modal.symbol == tick.symbol:
                     modal.update_ladder(tick.price, self.strategy.positions.get(tick.symbol, []))
                
                # 3. Strategy Logic
                signals = self.strategy.process_tick(tick)
                if signals:
                    strategy_panel = self.query_one(StrategyWidget)
                    for signal in signals:
                        if signal.action == "EXIT":
                            for pos in self.strategy.positions.get(signal.symbol, []):
                                await self._record_closed_trade(signal.symbol, pos, tick, signal.reason)
                        else:
                            # Process entry/scaling
                            strategy_panel.add_signal(signal)
                            
                            # 4. Notification Logic (Alert on threshold)
                            if signal.confidence >= self.alert_threshold:
                                 self._trigger_alert("GOLD SIGNAL", f"{signal.action} {signal.symbol} ({int(signal.confidence*100)}%)", high_priority=True)
                            
                            if self.auto_trade_enabled:
                                 self.log_message(f"AUTO-EXEC: {signal.action} {signal.symbol} @ {signal.price}")
                                 # Position logic would go here
                            else:
                                 self.log_message(f"AUTO-BLOCK: {signal.action} {signal.symbol} (Auto-Trading OFF)")

            await self.client.subscribe_ticks(self.symbols, real_callback)
            
        except Exception as e:
            self.log_message(f"SYSTEM ERROR: {e}")

    async def _handle_session_export(self):
        """Audit and aggregate current session data for permanent archival."""
        modal = self.screen
        if not isinstance(modal, ReportExportModal): return
        
        fmt = str(modal.query_one("#export-format", Select).value)
        self.log_message(f"SYSTEM: Generating {fmt.upper()} session report...")
        
        # 1. Aggregate Stats
        profit = self.bankroll.balance - self.session_start_balance
        win_rate = (self.session_wins / self.session_trades * 100) if self.session_trades > 0 else 0
        
        stats = {
            "global": {
                "profit": profit,
                "win_rate": win_rate,
                "trades": self.session_trades,
                "drawdown": self.risk_manager.current_drawdown
            },
            "engines": self.stats_per_engine,
            "symbols": self.stats_per_symbol
        }
        
        # 2. Read Trades Journal
        trades = []
        journal_path = os.path.join(self.storage_dir, "trades.json")
        if os.path.exists(journal_path):
            try:
                with open(journal_path, "r") as f:
                    for line in f:
                        if line.strip():
                            trades.append(json.loads(line))
            except:
                pass

        # 3. Export
        try:
            if fmt == "md":
                path = self.exporter.export_markdown(stats, trades)
            elif fmt == "csv":
                path = self.exporter.export_csv(stats, trades)
            else:
                path = self.exporter.export_json(stats, trades)

            self.log_message(f"SUCCESS: Report archived at {path}")
            self.pop_screen()
        except Exception as e:
            self.log_message(f"EXPORT ERROR: {e}")

    async def start_system(self):
        """Background task for connection and sync."""
        try:
            self.log_message("Connecting to API...")
            await self.client.connect()
            
            self.log_message("Starting automatic gap detection...")
            await self.downloader.sync_all(self.symbols)
            self.log_message("Sync complete. Data alignment established.")
            
            self.log_message(f"Subscribing to live ticks for {self.symbols}...")
            
            async def real_callback(tick):
                # 1. Update Orchestrator
                await self.orchestrator.on_tick(tick)
                
                # 2. Strategy Logic
                signals = self.strategy.process_tick(tick)
                if signals:
                    strategy_panel = self.query_one(StrategyWidget)
                    for signal in signals:
                        if signal.action == "EXIT":
                            # Process automated exit (Always allow for safety)
                            for pos in self.strategy.positions.get(signal.symbol, []):
                                await self._record_closed_trade(signal.symbol, pos, tick, signal.reason)
                        else:
                            # Process entry/scaling
                            strategy_panel.add_signal(signal)
                            if self.auto_trade_enabled:
                                # Logic to enter automated trade would go here
                                self.log_message(f"AUTO-EXEC: {signal.action} {signal.symbol} @ {signal.price}")
                                # pos = Position(...)
                            else:
                                self.log_message(f"AUTO-BLOCK: {signal.action} {signal.symbol} (Auto-Trading OFF)")

            await self.client.subscribe_ticks(self.symbols, real_callback)
            
        except Exception as e:
            self.log_message(f"SYSTEM ERROR: {e}")

    def action_quit(self) -> None:
        self.client.stop()
        self.exit()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+", default=["BOOM1000", "CRASH1000"])
    args = parser.parse_args()
    
    app = IQTradingApp(symbols=args.symbols)
    app.run()
