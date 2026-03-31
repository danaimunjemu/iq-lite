import asyncio
import logging
from typing import List, Tuple, Optional
from datetime import datetime
from .models import Tick
from .client import DerivClient
from .storage import StorageHandler

logger = logging.getLogger(__name__)

class IntegrityChecker:
    def __init__(self, client: DerivClient, storage: StorageHandler, gap_threshold: int = 5):
        """
        :param client: Initialized DerivClient instance.
        :param storage: StorageHandler instance to write backfilled data.
        :param gap_threshold: Max allowed seconds between ticks before it's considered a gap.
        """
        self.client = client
        self.storage = storage
        self.gap_threshold = gap_threshold

    def detect_gaps(self, ticks: List[Tick]) -> List[Tuple[int, int]]:
        """
        Analyzes a sorted list of ticks and identifies gaps.
        Returns a list of (start_epoch, end_epoch) tuples representing missing periods.
        """
        if len(ticks) < 2:
            return []

        gaps = []
        # Ensure ticks are sorted by epoch
        sorted_ticks = sorted(ticks, key=lambda x: x.epoch)

        for i in range(len(sorted_ticks) - 1):
            current_tick = sorted_ticks[i]
            next_tick = sorted_ticks[i+1]
            
            diff = next_tick.epoch - current_tick.epoch
            if diff > self.gap_threshold:
                # Gap starts after current tick and ends before next tick
                gaps.append((current_tick.epoch + 1, next_tick.epoch - 1))
        
        return gaps

    async def backfill_gaps(self, symbol: str, gaps: List[Tuple[int, int]]):
        """
        Iterates through detected gaps and fetches missing data from Deriv API.
        """
        if not gaps:
            logger.info(f"No gaps detected for {symbol}.")
            return

        logger.info(f"Detected {len(gaps)} gaps for {symbol}. Starting backfill...")
        
        for start, end in gaps:
            logger.info(f"Backfilling {symbol} from {datetime.fromtimestamp(start)} to {datetime.fromtimestamp(end)}...")
            try:
                missing_ticks = await self.client.fetch_historical_ticks(symbol, start, end)
                if missing_ticks:
                    await self.storage.write(missing_ticks)
                    logger.info(f"Successfully backfilled {len(missing_ticks)} ticks for {symbol}.")
                else:
                    logger.warning(f"No data returned for gap {start}-{end} on {symbol}.")
                
                # Small sleep to respect API rate limits if many gaps
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Failed to backfill gap {start}-{end}: {e}")

    def get_completeness_report(self, ticks: List[Tick]) -> dict:
        """
        Generates a summary of data health.
        """
        if not ticks:
            return {"status": "empty", "tick_count": 0}
            
        sorted_ticks = sorted(ticks, key=lambda x: x.epoch)
        start_time = datetime.fromtimestamp(sorted_ticks[0].epoch)
        end_time = datetime.fromtimestamp(sorted_ticks[-1].epoch)
        total_duration = sorted_ticks[-1].epoch - sorted_ticks[0].epoch
        
        gaps = self.detect_gaps(ticks)
        gap_count = len(gaps)
        total_gap_duration = sum(end - start + 1 for start, end in gaps)
        
        completeness = 100.0
        if total_duration > 0:
            completeness = max(0.0, 100.0 * (1 - (total_gap_duration / total_duration)))

        return {
            "status": "ok" if gap_count == 0 else "degraded",
            "tick_count": len(ticks),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "gap_count": gap_count,
            "completeness_pct": round(completeness, 2)
        }
