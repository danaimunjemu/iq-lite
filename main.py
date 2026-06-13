import asyncio
import argparse
import logging
import os
from api.client import DerivClient
from execution.orchestrator import IngestionOrchestrator
from api.historical import HistoricalDownloader
from strategy.synthetic_strategy import SyntheticIndexStrategy

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    parser = argparse.ArgumentParser(description="Multi-Timeframe Data Ingestion System")
    parser.add_argument("--symbols", nargs="+", default=["BOOM1000", "CRASH1000"], help="Symbols to track")
    parser.add_argument("--historical", type=int, default=0, help="Number of hours of historical data to backfill (Force)")
    parser.add_argument("--live", action="store_true", default=True, help="Enable live streaming")
    parser.add_argument("--storage", type=str, default="data", help="Directory for CSV storage")
    parser.add_argument("--skip-sync", action="store_true", help="Skip automatic gap detection and sync")
    args = parser.parse_args()

    # 1. Initialize Ingestion Orchestrator
    orchestrator = IngestionOrchestrator(symbols=args.symbols, storage_dir=args.storage)
    client = DerivClient(app_id=1089)
    downloader = HistoricalDownloader(client, storage_dir=args.storage)
    strategy = SyntheticIndexStrategy(args.symbols, orchestrator.provider)

    try:
        await client.connect()
        
        # 2. Automated Gap Sync
        if not args.skip_sync:
            logger.info("Starting automated gap detection and sync...")
            await downloader.sync_all(args.symbols)

        # 3. Live Streaming with Sync Provider
        if args.live:
            logger.info(f"Starting multi-timeframe ingestion for {args.symbols}...")
            
            async def strategic_callback(tick):
                # A. Core Ingestion (Updates Provider & Storage)
                await orchestrator.on_tick(tick)
                
                # B. Strategy Processing (Entries / Scaling / Exits)
                signals = strategy.process_tick(tick)
                
                for signal in signals:
                    logger.info(f"[{signal.symbol}] {signal.action} @ {signal.price} (Reason: {signal.reason})")
                    # In live mode: await executor.execute(signal)

                # C. Alignment Check
                if not orchestrator.provider.is_aligned(tick.symbol):
                    logger.warning(f"[{tick.symbol}] Data alignment lag detected!")

            await client.subscribe_ticks(args.symbols, strategic_callback)

    except KeyboardInterrupt:
        logger.info("Shutting down ingestion service...")
    finally:
        client.stop()
        logger.info("Service terminated.")

if __name__ == "__main__":
    asyncio.run(main())
