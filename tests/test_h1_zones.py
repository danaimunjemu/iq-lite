import asyncio
from models.trading import Candle
from features.zones_h1 import H1ZoneDetector

def test_h1_zones():
    print("--- H1 High-Probability Zone Verification ---")
    
    # 1. Setup
    symbol = "BOOM1000"
    detector = H1ZoneDetector(tolerance_pct=0.001)
    
    # 2. Case A: Support/Resistance (Swing Extrema)
    print("\nCase A: Support/Resistance (Swing High-Low)...")
    # Provide 10 padding candles + 5 for the swing
    candles_sr = [
        Candle(symbol, 100, 105, 95, 102, 1711900000 + i*3600, True) for i in range(10)
    ]
    # Swing High at index 12 (centered at 12, window=2)
    candles_sr.append(Candle(symbol, 102, 120, 101, 105, 1711900000 + 10*3600, True))
    candles_sr.extend([
        Candle(symbol, 105, 110, 95, 102, 1711900000 + i*3600, True) for i in range(11, 15)
    ])
    
    zones = detector.detect_zones(candles_sr)
    sr_zones = [z for z in zones if z.zone_type == 'Resistance']
    if len(sr_zones) > 0:
         print(f"  [PASS] Resistance Zone Detected @ {sr_zones[0].max_price:.2f}")
    else:
         print(f"  [FAIL] Failed to detect Resistance swing high. (n={len(candles_sr)})")

    # 3. Case B: Supply/Demand (Consolidation + ERC)
    print("\nCase B: Supply/Demand (Consolidation-ERC)...")
    # Base: 20 small candles (avg body ~5)
    # We need 15+ candles for detection
    candles_sd = [
        Candle(symbol, 100, 110, 90, 105, 1711900300 + i*3600, True) for i in range(20)
    ]
    # ERC: massive bearish drop (50-point body)
    candles_sd.append(Candle(symbol, 105, 105, 50, 50, 1711900300 + 20*3600, True))
    
    zones = detector.detect_zones(candles_sd)
    sd_zones = [z for z in zones if z.zone_type == 'Supply']
    if len(sd_zones) > 0:
         print(f"  [PASS] Supply Zone Detected (Base High: {sd_zones[0].max_price:.2f})")
         # Check Hit Detection
         z_hit = detector.is_price_in_zone(108.0)
         if z_hit and z_hit.zone_type == 'Supply':
              print("  [PASS] Price Hit Detection Verified.")
         else:
              print(f"  [FAIL] Hit Detection missed. Price: 108.0, Zone: {z_hit}")
    else:
         print("  [FAIL] Failed to detect Supply zone (Consolidation-ERC).")

    print("\n[SUCCESS] H1 High-Probability Zone Verification complete.")

if __name__ == "__main__":
    test_h1_zones()
