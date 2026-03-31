import asyncio
import argparse
import csv
import os
import json
from ingestion.models import Tick
from ingestion.client import DerivClient
from ingestion.storage import CSVStorage
from ingestion.integrity import IntegrityChecker

APP_ID = 1089

def load_ticks_from_csv(filename: str, symbol_filter: str = None) -> list:
    ticks = []
    if not os.path.exists(filename):
        return []
        
    with open(filename, mode='r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if symbol_filter and row['symbol'] != symbol_filter:
                continue
            ticks.append(Tick(
                symbol=row['symbol'],
                price=float(row['price']),
                epoch=int(row['epoch'])
            ))
    return ticks

async def main():
    parser = argparse.ArgumentParser(description="Data Integrity Auditor & Backfiller")
    parser.add_argument("--file", default="ticks_data.csv", help="CSV file to audit")
    parser.add_argument("--symbol", required=True, help="Symbol to check")
    parser.add_argument("--threshold", type=int, default=5, help="Gap threshold in seconds")
    parser.add_argument("--fix", action="store_true", help="Automatically backfill gaps")
    args = parser.parse_args()

    print(f"--- Auditing {args.symbol} in {args.file} ---")
    
    # 1. Load data
    ticks = load_ticks_from_csv(args.file, symbol_filter=args.symbol)
    if not ticks:
        print(f"No data found for {args.symbol}. Exiting.")
        return

    # 2. Check integrity
    # We initialize client with None token for public historical data
    client = DerivClient(app_id=APP_ID)
    storage = CSVStorage(args.file)
    checker = IntegrityChecker(client, storage, gap_threshold=args.threshold)
    
    report = checker.get_completeness_report(ticks)
    print(json.dumps(report, indent=4))

    # 3. Handle gaps
    if report["gap_count"] > 0:
        gaps = checker.detect_gaps(ticks)
        print(f"\nDetected Gaps:")
        for i, (s, e) in enumerate(gaps[:10]): # Show first 10
            print(f"  {i+1}. {s} to {e} (Duration: {e - s + 1}s)")
        
        if len(gaps) > 10:
            print(f"  ... and {len(gaps) - 10} more.")

        if args.fix:
            print("\nInitiating backfill...")
            await client.connect()
            await checker.backfill_gaps(args.symbol, gaps)
            client.stop()
            print("Backfill process complete. Run audit again to verify.")
        else:
            print("\nRun with --fix to automatically backfill these gaps.")
    else:
        print("\nData is continuous. No action needed.")

if __name__ == "__main__":
    asyncio.run(main())
