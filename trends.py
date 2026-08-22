"""
Local trend history for pinggrid (community roadmap: history & trends).
Appends device status to a lightweight JSONL store — zero cloud, pure stdlib.
"""

import json
import os
from datetime import datetime, timezone


class TrendStore:
    """Append-only local history of device status checks."""

    def __init__(self, path=None):
        self.path = path or os.path.join(
            os.path.dirname(__file__), "history.jsonl")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def record(self, device_name, status, latency_ms=None):
        """Append one check result. status: 'up' | 'down' | 'degraded'"""
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "device": device_name,
            "status": status,
            "latency_ms": latency_ms,
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def history(self, device_name=None, limit=100):
        """Return last N entries (optionally for one device), newest first."""
        entries = []
        if not os.path.exists(self.path):
            return entries
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if device_name is None or e.get("device") == device_name:
                    entries.append(e)
        return entries[-limit:][::-1]

    def uptime_summary(self, device_name, lookback=24 * 60):
        """Percent of checks 'up' in the last `lookback` entries (approx)."""
        entries = self.history(device_name, limit=lookback)
        if not entries:
            return None
        up = sum(1 for e in entries if e.get("status") == "up")
        return {"checked": len(entries), "up": up,
                "uptime_pct": round(100.0 * up / len(entries), 1)}
