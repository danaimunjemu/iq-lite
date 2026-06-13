import asyncio
import os
import csv
import time
from models.trading import Tick
from execution.orchestrator import IngestionOrchestrator

async def test_ingestion_sync():
    print("--- Multi-Timeframe Ingestion Test ---")
    
    # 1. Setup
    storage_dir = "test_data"
    os.makedirs(storage_dir, exist_ok=True)
    
    # Clean old data BEFORE initializing orchestrator
    for f in ["ticks.csv", "candles_m5.csv", "candles_h1.csv"]:
        path = os.path.join(storage_dir, f)
        if os.path.exists(path): 
            print(f"Cleaning {path}")
            os.remove(path)

    orchestrator = IngestionOrchestrator(symbols=["TEST"], storage_dir=storage_dir)
    
    # 2. Simulate 601 Ticks (1 tick per second)
    # This should cross one M5 boundary (300s) and bridge two (600s total)
    start_epoch = 1711900000 # Normalized arbitrary epoch
    
    print("Processing simulated ticks...")
    for i in range(601):
        tick = Tick(
            symbol="TEST",
            price=100.0 + (i * 0.01),
            epoch=start_epoch + i
        )
        await orchestrator.on_tick(tick)
    
    # Flush remaining tick buffer
    if orchestrator.tick_buffer["TEST"]:
        await orchestrator.tick_storage.write(orchestrator.tick_buffer["TEST"])

    # 3. Verify Files
    print("\nVerifying Files:")
    
    # Ticks
    with open(os.path.join(storage_dir, "ticks.csv"), 'r') as f:
        ticks = list(csv.DictReader(f))
        print(f"  ticks.csv: {len(ticks)} entries (Expected 601)")
        assert len(ticks) == 601
        
    # M5 Candles (601 seconds should cross two boundaries and generate two closed candles)
    # Actually, 601 seconds is 10 minutes and 1 second.
    # Boundary 1: 300s, Boundary 2: 600s.
    with open(os.path.join(storage_dir, "candles_m5.csv"), 'r') as f:
        candles_m5 = list(csv.DictReader(f))
        print(f"  candles_m5.csv: {len(candles_m5)} entries (Expected 2)")
        assert len(candles_m5) == 2
        
    # H1 Candles (Not enough data for a closed H1 candle, expected 0)
    # But let's check if the file exists.
    if os.path.exists(os.path.join(storage_dir, "candles_h1.csv")):
        with open(os.path.join(storage_dir, "candles_h1.csv"), 'r') as f:
            candles_h1 = list(csv.DictReader(f))
            print(f"  candles_h1.csv: {len(candles_h1)} entries (Expected 0)")
            assert len(candles_h1) == 0

    print("\n[SUCCESS] Multi-timeframe ingestion verified.")

if __name__ == "__main__":
    asyncio.run(test_ingestion_sync())
