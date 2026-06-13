import os
import csv
import logging
import asyncio
import time
from typing import List, Optional
from models.trading import Candle
from data.manager import CSVStorage
from api.client import DerivClient

logger = logging.getLogger(__name__)

class HistoricalDownloader:
    """
    Handles gap detection and surgical backfilling of M5 and H1 candles.
    Ensures local CSV data is continuous.
    """
    def __init__(self, client: DerivClient, storage_dir: str = "data"):
        self.client = client
        self.storage_dir = storage_dir

    def get_last_stored_epoch(self, filename: str) -> Optional[int]:
        """
        Efficiently reads the last epoch from a CSV file.
        """
        if not os.path.exists(filename):
            return None
            
        try:
            with open(filename, 'rb') as f:
                try:
                    f.seek(-1024, os.SEEK_END)
                except OSError:
                    pass # File smaller than 1KB
                
                last_line = f.readlines()[-1].decode().strip()
                if not last_line or "symbol" in last_line:
                    return None
                    
                # Format: symbol,open,high,low,close,epoch,timestamp
                parts = last_line.split(',')
                if len(parts) >= 6:
                    return int(parts[5])
        except Exception as e:
            logger.warning(f"Failed to read last epoch from {filename}: {e}")
            
        return None

    async def get_gap_stats(self, symbol: str, interval: int, filename: str) -> dict:
        """Audits the filesystem for missing data duration."""
        current_time = int(time.time())
        last_epoch = self.get_last_stored_epoch(filename)
        
        if not last_epoch:
             return {"hours_missing": 168.0, "status": "No Local Data"}
        
        gap_seconds = current_time - last_epoch - interval
        if gap_seconds < interval:
             return {"hours_missing": 0.0, "status": "Perfect Integrity"}
             
        hours = max(gap_seconds / 3600.0, 0.0)
        return {"hours_missing": hours, "status": f"{hours:.1f}h Local Gap"}

    async def sync_symbol(self, symbol: str, interval: int, filename: str, max_lookback_days: int = 7) -> str:
        """
        Detects gap and backfills missing candles for a specific symbol/interval.
        Returns a human-readable result status.
        """
        current_time = int(time.time())
        last_epoch = self.get_last_stored_epoch(filename)
        
        # Determine start time
        if last_epoch:
            start_time = last_epoch + interval
        else:
            # Full backfill if file is empty
            start_time = current_time - (max_lookback_days * 86400)
            logger.info(f"[{symbol}] No existing data for {interval}s. Starting full {max_lookback_days}-day backfill.")

        # Floor to boundary
        start_time = (start_time // interval) * interval
        end_time = (current_time // interval) * interval - interval
        
        if start_time >= end_time:
            return "ALREADY UP TO DATE"

        gap_seconds = end_time - start_time
        logger.info(f"[{symbol}] Detected gap of {gap_seconds // 3600} hours in {interval}s data. Backfilling...")
        
        # Deriv API limits may apply, but fetch_historical_candles handles it
        candles = await self.client.fetch_historical_candles(
            symbol=symbol,
            granularity=interval,
            start_time=start_time,
            end_time=end_time
        )
        
        if candles:
            storage = CSVStorage(filename)
            await storage.write(candles)
            logger.info(f"[{symbol}] Backfilled {len(candles)} candles for {interval}s resolution.")
            return f"REPAIRED ({len(candles)} candles)"
        else:
            logger.warning(f"[{symbol}] API returned 0 candles for the gap {start_time} -> {end_time}")
            return "SYNC FAILED (No API Response)"

    async def sync_all(self, symbols: List[str]):
        """
        Synchronizes all resolutions for all symbols.
        """
        tasks = []
        for symbol in symbols:
            # M5 Sync
            tasks.append(self.sync_symbol(
                symbol, 300, f"{self.storage_dir}/candles_m5.csv"
            ))
            # H1 Sync
            tasks.append(self.sync_symbol(
                symbol, 3600, f"{self.storage_dir}/candles_h1.csv"
            ))
            
        if tasks:
            await asyncio.gather(*tasks)
