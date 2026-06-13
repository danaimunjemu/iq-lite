import asyncio
import os
import csv
import time
from api.client import DerivClient
from api.historical import HistoricalDownloader

async def test_downloader_gap():
    print("--- Historical Downloader Gap Sync Test ---")
    
    # 1. Setup
    storage_dir = "test_sync_data"
    os.makedirs(storage_dir, exist_ok=True)
    symbol = "BOOM1000"
    m5_file = os.path.join(storage_dir, "candles_m5.csv")
    
    client = DerivClient(app_id=1089)
    downloader = HistoricalDownloader(client, storage_dir=storage_dir)

    # 2. Simulate existing data with a gap
    # We'll create a file that ends 1 hour ago
    current_time = int(time.time())
    one_hour_ago = (current_time // 300) * 300 - 3600
    
    print(f"Creating mock data ending at {one_hour_ago}...")
    with open(m5_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["symbol", "open", "high", "low", "close", "epoch", "timestamp"])
        writer.writerow([symbol, 100.0, 101.0, 99.0, 100.5, one_hour_ago, "2026-04-02T00:00:00"])

    # 3. Run Sync
    print("Running sync_symbol...")
    await client.connect()
    await downloader.sync_symbol(symbol, 300, m5_file)
    
    # 4. Verify
    print("\nVerifying results:")
    with open(m5_file, 'r') as f:
        rows = list(csv.DictReader(f))
        print(f"  Total rows after sync: {len(rows)}")
        
        last_row = rows[-1]
        last_epoch = int(last_row['epoch'])
        print(f"  Last epoch in file: {last_epoch}")
        print(f"  Target end time: {current_time // 300 * 300 - 300}")
        
        # Should have at least 12 new candles (1 hour of M5)
        assert len(rows) > 10
        assert last_epoch > one_hour_ago

    print("\n[SUCCESS] Historical Downloader gap sync verified.")
    client.stop()

if __name__ == "__main__":
    asyncio.run(test_downloader_gap())
