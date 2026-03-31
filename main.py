import asyncio
import argparse
import os
import time
from ingestion.models import Tick
from ingestion.client import DerivClient
from ingestion.storage import CSVStorage
from ingestion.buffer import TickBuffer

# Configuration
APP_ID = 1089  # Public App ID for testing
SYMBOLS = ["R_100", "C1000", "B1000"]

async def main():
    parser = argparse.ArgumentParser(description="Deriv Data Ingestion Service")
    parser.add_argument("--symbols", nargs="+", default=SYMBOLS, help="Symbols to track")
    parser.add_argument("--historical", action="store_true", help="Fetch historical data")
    parser.add_argument("--live", action="store_true", default=True, help="Stream live data")
    args = parser.parse_args()

    # Initialize components
    storage = CSVStorage("ticks_data.csv")
    buffer = TickBuffer(storage, max_size=50, flush_interval=10.0)
    client = DerivClient(app_id=APP_ID)

    try:
        # 1. Historical Data Fetching (Optional)
        if args.historical:
            print(f"Fetching historical data for {args.symbols}...")
            end_time = int(time.time())
            start_time = end_time - (24 * 3600)  # Last 24 hours
            for symbol in args.symbols:
                hist_ticks = await client.fetch_historical_ticks(symbol, start_time, end_time)
                print(f"Fetched {len(hist_ticks)} historical ticks for {symbol}")
                await storage.write(hist_ticks)

        # 2. Live Streaming
        if args.live:
            print(f"Starting live stream for {args.symbols}...")
            await client.connect()
            await client.subscribe_ticks(args.symbols, buffer.add_tick)

    except KeyboardInterrupt:
        print("\nStopping service...")
    finally:
        client.stop()
        await buffer.close()

if __name__ == "__main__":
    asyncio.run(main())
