# tests/test_trends.py
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trends import TrendStore


def test_record_and_history():
    with tempfile.TemporaryDirectory() as tmp:
        store = TrendStore(path=os.path.join(tmp, "h.jsonl"))
        store.record("router", "up", 12)
        store.record("router", "down", None)
        store.record("nas", "up", 8)
        hist = store.history()
        assert len(hist) == 3
        assert hist[0]["device"] == "nas"  # newest first


def test_uptime_summary():
    with tempfile.TemporaryDirectory() as tmp:
        store = TrendStore(path=os.path.join(tmp, "h.jsonl"))
        for i in range(10):
            store.record("router", "up" if i < 9 else "down")
        summary = store.uptime_summary("router")
        assert summary["uptime_pct"] == 90.0
        assert summary["checked"] == 10


def test_empty_store():
    with tempfile.TemporaryDirectory() as tmp:
        store = TrendStore(path=os.path.join(tmp, "none.jsonl"))
        assert store.history() == []
        assert store.uptime_summary("x") is None
