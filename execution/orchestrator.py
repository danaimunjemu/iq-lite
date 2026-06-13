import asyncio
import logging
from typing import List, Dict, Any
from models.trading import Tick, Candle
from data.manager import CSVStorage
from features.candles import CandleAggregator
from execution.provider import MarketDataProvider
from api.client import DerivClient

logger = logging.getLogger(__name__)

class IngestionOrchestrator:
    """
    Main Orchestrator for multi-timeframe data ingestion.
    Routes Ticks to TickStorage, Aggregator, and Sync Provider.
    """
    def __init__(self, symbols: List[str], storage_dir: str = "data"):
        self.symbols = symbols
        self.storage_dir = storage_dir
        
        # 1. Initialize Storage
        self.tick_storage = CSVStorage(f"{storage_dir}/ticks.csv")
        self.m5_storage = CSVStorage(f"{storage_dir}/candles_m5.csv", headers=["symbol", "open", "high", "low", "close", "epoch", "timestamp"])
        self.h1_storage = CSVStorage(f"{storage_dir}/candles_h1.csv", headers=["symbol", "open", "high", "low", "close", "epoch", "timestamp"])
        
        # 2. Initialize Core Logic
        self.aggregator = CandleAggregator(intervals=[300, 3600]) 
        self.provider = MarketDataProvider(symbols=symbols)
        
        # 3. Buffer for batch writing ticks
        self.tick_buffer: Dict[str, List[Tick]] = {s: [] for s in symbols}
        self.buffer_limit = 50

    async def on_tick(self, tick: Tick):
        """
        Main Routing Logic: Tick -> (TickStorage, Aggregator -> Sync Provider)
        """
        # A. Update Provider (Real-time awareness)
        self.provider.update_tick(tick)

        # B. Raw Tick Storage (Buffered)
        self.tick_buffer[tick.symbol].append(tick)
        if len(self.tick_buffer[tick.symbol]) >= self.buffer_limit:
            batch = self.tick_buffer[tick.symbol]
            self.tick_buffer[tick.symbol] = []
            await self.tick_storage.write(batch)
            
        # C. Multi-Timeframe Candle Generation
        closed_candles = self.aggregator.update(tick)
        
        # D. Update Provider with closed events
        if closed_candles:
            self.provider.update_candles(closed_candles)
        
        # E. Route closed candles to respective storage
        if 300 in closed_candles:
            await self.m5_storage.write([closed_candles[300]])
            
        if 3600 in closed_candles:
            await self.h1_storage.write([closed_candles[3600]])

    async def process_historical(self, client: DerivClient, hours: int = 24):
        """
        Backfills ticks and reconstruction candles for the past X hours.
        """
        import time
        end_time = int(time.time())
        start_time = end_time - (hours * 3600)
        
        logger.info(f"Backfilling {hours} hours of data for {self.symbols}...")
        
        for symbol in self.symbols:
            ticks = await client.fetch_historical_ticks(symbol, start_time, end_time)
            logger.info(f"Fetched {len(ticks)} historical ticks for {symbol}.")
            
            # Replay all ticks through the same on_tick logic for absolute alignment
            for tick in ticks:
                await self.on_tick(tick)
            
            # Flush remaining buffer
            if self.tick_buffer[symbol]:
                await self.tick_storage.write(self.tick_buffer[symbol])
                self.tick_buffer[symbol] = []

        logger.info("Historical data ingestion complete.")
