import csv
import argparse
import os
from ingestion.models import Tick
from ingestion.spikes import SpikeDetector, SpikeEvent

def load_ticks(filename: str, symbol: str):
    ticks = []
    with open(filename, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['symbol'] == symbol:
                ticks.append(Tick(
                    symbol=row['symbol'],
                    price=float(row['price']),
                    epoch=int(row['epoch'])
                ))
    return ticks

def main():
    parser = argparse.ArgumentParser(description="Label spikes in historical tick data")
    parser.add_argument("--file", default="ticks_data.csv", help="Input CSV file")
    parser.add_argument("--symbol", required=True, help="Symbol to process (e.g. C1000, B1000)")
    parser.add_argument("--sigma", type=float, default=5.0, help="Z-score threshold")
    parser.add_argument("--output", default="spikes_detected.csv", help="Output spikes file")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Error: {args.file} not found.")
        return

    print(f"Loading ticks for {args.symbol}...")
    ticks = load_ticks(args.file, args.symbol)
    print(f"Found {len(ticks)} ticks.")

    detector = SpikeDetector(window_size=100, z_threshold=args.sigma)
    print(f"Analyzing with sigma={args.sigma}...")
    spikes = detector.detect_historical(ticks)

    if not spikes:
        print("No spikes detected.")
        return

    print(f"Detected {len(spikes)} spikes.")
    
    # Write to CSV
    with open(args.output, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["symbol", "epoch", "timestamp", "price_before", "price_after", "magnitude", "type"])
        writer.writeheader()
        for s in spikes:
            # Manually construct dict from dataclass for cleaner control
            writer.writerow({
                "symbol": s.symbol,
                "epoch": s.epoch,
                "timestamp": s.timestamp,
                "price_before": f"{s.price_before:.5f}",
                "price_after": f"{s.price_after:.5f}",
                "magnitude": f"{s.magnitude:.5f}",
                "type": s.type
            })
    
    print(f"Results saved to {args.output}")

if __name__ == "__main__":
    main()
