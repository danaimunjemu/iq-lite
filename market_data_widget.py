from typing import List, Optional
from datetime import datetime
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Static, DataTable, Label
from models.trading import Tick, Candle

class LiveMarketDataWidget(Container):
    """
    A premium Textual widget for live market surveillance.
    Displays current price, a history of recent ticks, and key candle metrics.
    """

    DEFAULT_CSS = """
    LiveMarketDataWidget {
        width: 100%;
        height: 100%;
        background: #0f172a;
        border: solid #1e293b;
        padding: 1;
    }

    .market-header {
        height: 3;
        align: center middle;
        border-bottom: double #334155;
        margin-bottom: 1;
    }

    #current-price-label {
        text-style: bold;
        color: #38bdf8;
        width: 1fr;
        text-align: center;
    }

    .section-title {
        background: #1e293b;
        color: #94a3b8;
        text-style: bold;
        padding: 0 1;
        margin-top: 1;
    }

    #tick-table, #candle-table {
        height: 1fr;
        border: none;
        background: transparent;
    }

    #tick-table > .datatable--header, #candle-table > .datatable--header {
        background: #1e293b;
        color: #f8fafc;
    }

    .price-up {
        color: #4ade80;
    }

    .price-down {
        color: #f87171;
    }
    """

    def __init__(self, symbol: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.symbol = symbol
        self._last_price: Optional[float] = None

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal(classes="market-header"):
                yield Label(f"SYMBOL: {self.symbol}", id="market-symbol")
                yield Static("0.00", id="current-price-label")
            
            yield Label("LATEST CANDLES (M5 | H1)", classes="section-title")
            yield DataTable(id="candle-table")
            
            yield Label("RECENT TICKS (REAL-TIME)", classes="section-title")
            yield DataTable(id="tick-table")

    def on_mount(self) -> None:
        # Initialize Tick Table
        tick_table = self.query_one("#tick-table", DataTable)
        tick_table.add_columns("TIME", "PRICE", "CHANGE")
        tick_table.cursor_type = "none"
        
        # Initialize Candle Table
        candle_table = self.query_one("#candle-table", DataTable)
        candle_table.add_columns("TF", "OPEN", "HIGH", "LOW", "CLOSE")
        candle_table.show_cursor = False
        candle_table.add_row("M5", "-", "-", "-", "-")
        candle_table.add_row("H1", "-", "-", "-", "-")

    def update_data(self, tick: Tick, recent_ticks: List[Tick], m5: Optional[Candle], h1: Optional[Candle]):
        """
        The primary update method to refresh UI components.
        """
        # 1. Update Price & Header
        price_label = self.query_one("#current-price-label", Static)
        price_label.update(f"{tick.price:.2f}")
        
        if self._last_price is not None:
            if tick.price > self._last_price:
                price_label.set_classes("price-up")
            elif tick.price < self._last_price:
                price_label.set_classes("price-down")
        self._last_price = tick.price

        # 2. Update Ticks Table (Last N)
        tick_table = self.query_one("#tick-table", DataTable)
        tick_table.clear()
        
        # Display ticks in reverse chronological order
        sorted_ticks = sorted(recent_ticks, key=lambda x: x.epoch, reverse=True)
        for i, t in enumerate(sorted_ticks):
            timestamp = t.timestamp.strftime("%H:%M:%S")
            change = "-"
            if i < len(sorted_ticks) - 1:
                prev_t = sorted_ticks[i+1]
                diff = t.price - prev_t.price
                change = f"{diff:+.2f}"
            
            tick_table.add_row(
                timestamp,
                f"{t.price:.2f}",
                change
            )

        # 3. Update Candles
        candle_table = self.query_one("#candle-table", DataTable)
        if m5:
            candle_table.update_cell_at((0, 1), f"{m5.open:.2f}")
            candle_table.update_cell_at((0, 2), f"{m5.high:.2f}")
            candle_table.update_cell_at((0, 3), f"{m5.low:.2f}")
            candle_table.update_cell_at((0, 4), f"{m5.close:.2f}")
        
        if h1:
            candle_table.update_cell_at((1, 1), f"{h1.open:.2f}")
            candle_table.update_cell_at((1, 2), f"{h1.high:.2f}")
            candle_table.update_cell_at((1, 3), f"{h1.low:.2f}")
            candle_table.update_cell_at((1, 4), f"{h1.close:.2f}")

if __name__ == "__main__":
    import asyncio
    import random

    class DemoApp(App):
        def compose(self) -> ComposeResult:
            yield LiveMarketDataWidget(symbol="CRASH1000")

        async def on_mount(self) -> None:
            widget = self.query_one(LiveMarketDataWidget)
            symbol = "CRASH1000"
            base_price = 1000.0
            ticks = []
            
            async def simulated_stream():
                nonlocal base_price
                while True:
                    base_price += random.uniform(-0.5, 0.5)
                    new_tick = Tick(symbol=symbol, price=base_price, epoch=int(datetime.now().timestamp()))
                    ticks.append(new_tick)
                    if len(ticks) > 20: ticks.pop(0)
                    
                    m5 = Candle(symbol=symbol, open=base_price-1, high=base_price+2, low=base_price-3, close=base_price, epoch=int(datetime.now().timestamp()))
                    h1 = Candle(symbol=symbol, open=base_price-5, high=base_price+10, low=base_price-15, close=base_price, epoch=int(datetime.now().timestamp()))
                    
                    widget.update_data(new_tick, ticks, m5, h1)
                    await asyncio.sleep(1)

            asyncio.create_task(simulated_stream())

    DemoApp().run()
