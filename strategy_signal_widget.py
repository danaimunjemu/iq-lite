from typing import Dict, Any, Optional
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Static, Label
from models.trading import TradeSignal

class StrategySignalWidget(Container):
    """
    A premium Textual widget for real-time strategy signal surveillance.
    Visualizes indicator states, trend direction, and final execution decisions.
    """

    DEFAULT_CSS = """
    StrategySignalWidget {
        width: 100%;
        height: auto;
        background: #0f172a;
        border: solid #1e293b;
        padding: 1;
        margin-top: 1;
    }

    .signal-row {
        height: 1;
        margin-bottom: 0;
    }

    .signal-row Label {
        width: 18;
        color: #94a3b8;
        text-style: bold;
    }

    .signal-row Static {
        width: 1fr;
        text-align: right;
        text-style: bold;
    }

    #decision-container {
        margin-top: 1;
        padding-top: 1;
        border-top: dashed #334155;
        height: 3;
        align: center middle;
    }

    #signal-decision {
        text-style: bold;
        text-align: center;
        width: 100%;
    }

    /* Status Colors */
    .status-green { color: #4ade80; }
    .status-red { color: #f87171; }
    .status-yellow { color: #fbbf24; }
    .status-neutral { color: #94a3b8; }

    .decision-buy { background: #064e3b; color: #4ade80; text-style: bold; border: double #059669; }
    .decision-sell { background: #450a0a; color: #f87171; text-style: bold; border: double #b91c1c; }
    .decision-skip { background: #1e293b; color: #94a3b8; text-style: bold; border: double #334155; }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            # 1. RSI Status
            with Horizontal(classes="signal-row"):
                yield Label("RSI STATUS:")
                yield Static("NEUTRAL", id="signal-rsi")
            
            # 2. MA50 Trend
            with Horizontal(classes="signal-row"):
                yield Label("MA50 TREND:")
                yield Static("SIDEWAYS", id="signal-trend")
            
            # 3. Zone Status
            with Horizontal(classes="signal-row"):
                yield Label("ZONE STATUS:")
                yield Static("OUTSIDE", id="signal-zone")
            
            # 4. Spike Probability
            with Horizontal(classes="signal-row"):
                yield Label("SPIKE PROB:")
                yield Static("0.0%", id="signal-spike")
            
            # 5. Final Decision
            with Vertical(id="decision-container"):
                yield Static("SKIP", id="signal-decision", classes="decision-skip")

    def update_signals(self, features: Dict[str, Any], signal: Optional[TradeSignal]):
        """
        Dynamically update the widget with the latest indicators and signals.
        """
        # 1. RSI Update
        rsi = features.get("rsi_14", 50.0)
        rsi_stat = self.query_one("#signal-rsi", Static)
        if rsi < 30:
            rsi_stat.update(f"OVERSOLD ({rsi:.1f})")
            rsi_stat.set_classes("status-green")
        elif rsi > 70:
            rsi_stat.update(f"OVERBOUGHT ({rsi:.1f})")
            rsi_stat.set_classes("status-red")
        else:
            rsi_stat.update(f"NEUTRAL ({rsi:.1f})")
            rsi_stat.set_classes("status-yellow")

        # 2. MA50 Trend Update
        price = features.get("price", 0.0)
        ma50 = features.get("ma_50", 0.0)
        trend_stat = self.query_one("#signal-trend", Static)
        if price > ma50:
            trend_stat.update("ABOVE MA50")
            trend_stat.set_classes("status-green")
        elif price < ma50:
            trend_stat.update("BELOW MA50")
            trend_stat.set_classes("status-red")
        else:
            trend_stat.update("CROSSING")
            trend_stat.set_classes("status-yellow")

        # 3. Zone Status Update
        zone_type = features.get("zone_type", "NONE")
        zone_stat = self.query_one("#signal-zone", Static)
        if zone_type != "NONE":
            zone_stat.update(f"INSIDE {zone_type}")
            zone_stat.set_classes("status-green")
        else:
            zone_stat.update("OUTSIDE")
            zone_stat.set_classes("status-neutral")

        # 4. Spike Probability Update
        prob = features.get("spike_prob", 0.0)
        spike_stat = self.query_one("#signal-spike", Static)
        spike_stat.update(f"{prob*100:.1f}%")
        if prob < 0.15:
            spike_stat.set_classes("status-green")
        elif prob > 0.35:
            spike_stat.set_classes("status-red")
        else:
            spike_stat.set_classes("status-yellow")

        # 5. Final Decision Update
        decision_stat = self.query_one("#signal-decision", Static)
        if signal:
            decision_stat.update(signal.action.upper())
            if signal.action == "BUY":
                decision_stat.set_classes("decision-buy")
            elif signal.action == "SELL":
                decision_stat.set_classes("decision-sell")
            else:
                decision_stat.set_classes("decision-skip")
        else:
            decision_stat.update("SKIP")
            decision_stat.set_classes("decision-skip")

if __name__ == "__main__":
    # Integration Mock Demo
    class SignalDemoApp(App):
        def compose(self) -> ComposeResult:
            yield StrategySignalWidget()

        async def on_mount(self) -> None:
            widget = self.query_one(StrategySignalWidget)
            
            # Mock Data Update
            mock_features = {
                "rsi_14": 22.5,
                "price": 1050.2,
                "ma_50": 1040.0,
                "zone_type": "SUPPORT",
                "spike_prob": 0.05
            }
            mock_signal = TradeSignal(symbol="B1000", action="BUY", price=1050.2, epoch=0, probability=0.95, reason="OVERSOLD+SUPPORT")
            
            widget.update_signals(mock_features, mock_signal)

    SignalDemoApp().run()
