import asyncio
import json
import csv
from ingestion.client import DerivClient

APP_ID = 1089  # Public App ID

async def fetch_and_save_symbols():
    client = DerivClient(app_id=APP_ID)
    try:
        print("Connecting to Deriv...")
        await client.connect()
        
        print("Fetching active symbols...")
        symbols = await client.fetch_active_symbols()
        
        if not symbols:
            print("No symbols found.")
            return

        # Filter for synthetic indices mainly, but save all
        # Synthetic indices have market='synthetic_index'
        
        # Save to JSON
        with open("deriv_symbols.json", "w") as f:
            json.dump(symbols, f, indent=4)
        print(f"Saved {len(symbols)} symbols to deriv_symbols.json")
        
        # Save to CSV for easy viewing
        with open("deriv_symbols.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=symbols[0].keys())
            writer.writeheader()
            writer.writerows(symbols)
        print(f"Saved {len(symbols)} symbols to deriv_symbols.csv")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.stop()

if __name__ == "__main__":
    asyncio.run(fetch_and_save_symbols())
