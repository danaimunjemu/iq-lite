import os
import csv
import json
from datetime import datetime
from typing import List, Dict, Any

class SessionExporter:
    """
    Industrial-grade exporter for trading performance data.
    Generates professional reports in CSV, JSON, and Markdown formats.
    """
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def _get_filename(self, extension: str) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(self.output_dir, f"report_{timestamp}.{extension}")

    def export_csv(self, stats: Dict[str, Any], trades: List[Dict[str, Any]]) -> str:
        filename = self._get_filename("csv")
        if not trades:
             return "No trades to export."
             
        keys = trades[0].keys()
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(trades)
        return filename

    def export_json(self, stats: Dict[str, Any], trades: List[Dict[str, Any]]) -> str:
        filename = self._get_filename("json")
        report = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "session_summary": stats.get("global", {})
            },
            "performance": {
                "symbols": stats.get("symbols", {}),
                "engines": stats.get("engines", {})
            },
            "trades": trades
        }
        with open(filename, 'w') as f:
            json.dump(report, f, indent=4)
        return filename

    def export_markdown(self, stats: Dict[str, Any], trades: List[Dict[str, Any]]) -> str:
        filename = self._get_filename("md")
        global_s = stats.get("global", {})
        
        md = f"""# IQ-Lite Session Report: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
---
## 📊 Executive Summary
| Metric | Value |
| :--- | :--- |
| **Total Profit** | **${global_s.get('profit', 0):+.2f}** |
| **Win Rate** | **{global_s.get('win_rate', 0):.1f}%** |
| **Total Trades** | **{global_s.get('trades', 0)}** |
| **Max Drawdown** | **${global_s.get('drawdown', 0):.2f}** |

## 🚀 Performance by Engine
| Engine | P/L | Win % |
| :--- | :--- | :--- |
"""
        for engine, s in stats.get("engines", {}).items():
            wr = (s['wins'] / s['total'] * 100) if s['total'] > 0 else 0
            md += f"| {engine} | ${s['pnl']:+.2f} | {wr:.0f}% |\n"

        md += "\n## 💎 Performance by Symbol\n| Symbol | P/L | Trades |\n| :--- | :--- | :--- |\n"
        for symbol, s in stats.get("symbols", {}).items():
             md += f"| {symbol} | ${s['pnl']:+.2f} | {int(s['total'])} |\n"

        md += "\n## 📒 Trade Journal (Detailed)\n| Time | Symbol | Side | P/L | Reason |\n| :--- | :--- | :--- | :--- | :--- |\n"
        for t in trades[-20:]: # Last 20 trades
             md += f"| {t.get('timestamp','')} | {t.get('symbol','')} | {t.get('side','')} | ${t.get('pnl',0):+.2f} | {t.get('reason','')} |\n"

        with open(filename, 'w') as f:
            f.write(md)
        return filename
