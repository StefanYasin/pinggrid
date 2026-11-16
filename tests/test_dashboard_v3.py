# tests/test_dashboard_v3.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import monitor
import dashboard


class _NullLog:
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass


def _device(name, host, **flags):
    return {"name": name, "host": host, "ports": [], **flags}


def _fake_check(alive=True, rtt_ms=5):
    def _check(device, **kw):
        return {"name": device["name"], "host": device["host"],
                "ping": {"alive": alive, "rtt_ms": rtt_ms if alive else None,
                         "error": None if alive else "timeout"},
                "ports": [], "timestamp": 0}
    return _check


def test_cycle_attaches_history_and_flags(monkeypatch):
    monitor._history.clear()  # module-level deque persists between tests
    config = {"devices": [_device("A", "10.0.0.1")], "thresholds": {}, "alerts": {}}
    monkeypatch.setattr(monitor, "check_device", _fake_check())
    state = monitor.AlertState()
    monitor.run_monitor_cycle(config, _NullLog(), state)
    cache = monitor.get_status_cache()
    assert cache[0]["history"] == [True]
    assert cache[0]["maintenance"] is False
    assert cache[0]["paused"] is False


def test_history_accumulates_across_cycles(monkeypatch):
    monitor._history.clear()
    config = {"devices": [_device("A", "10.0.0.1")], "thresholds": {}, "alerts": {}}
    monkeypatch.setattr(monitor, "check_device", _fake_check())
    state = monitor.AlertState()
    monitor.run_monitor_cycle(config, _NullLog(), state)
    monitor.run_monitor_cycle(config, _NullLog(), state)
    cache = monitor.get_status_cache()
    assert cache[0]["history"] == [True, True]


def test_maintenance_suppresses_alerts_but_still_checks(monkeypatch):
    config = {"devices": [_device("M", "10.0.0.2", maintenance=True)],
              "thresholds": {}, "alerts": {}}
    monkeypatch.setattr(monitor, "check_device", _fake_check(alive=False))
    sent = []
    monkeypatch.setattr(monitor, "dispatch_alert",
                        lambda cfg, name, msg, sev: sent.append((name, sev)))
    state = monitor.AlertState()
    monitor.run_monitor_cycle(config, _NullLog(), state)
    assert sent == []                          # no alerts during maintenance
    cache = monitor.get_status_cache()
    assert cache[0]["maintenance"] is True
    assert cache[0]["ping"]["alive"] is False  # still checked: dashboard honest


def test_paused_suppresses_alerts(monkeypatch):
    config = {"devices": [_device("P", "10.0.0.3", paused=True)],
              "thresholds": {}, "alerts": {}}
    monkeypatch.setattr(monitor, "check_device", _fake_check(alive=False))
    sent = []
    monkeypatch.setattr(monitor, "dispatch_alert",
                        lambda cfg, name, msg, sev: sent.append((name, sev)))
    state = monitor.AlertState()
    monitor.run_monitor_cycle(config, _NullLog(), state)
    assert sent == []
    assert monitor.get_status_cache()[0]["paused"] is True


def test_dashboard_renders_banner_states_and_controls():
    devices = [
        {"name": "Nitro", "host": "192.168.2.100",
         "ping": {"alive": True, "rtt_ms": 1.2, "error": None}, "ports": [],
         "maintenance": False, "paused": False, "history": [True, True]},
        {"name": "Broken", "host": "192.168.2.99",
         "ping": {"alive": False, "rtt_ms": None, "error": "timeout"}, "ports": [],
         "maintenance": False, "paused": False, "history": [True, False]},
        {"name": "Rebooting", "host": "192.168.2.98",
         "ping": {"alive": False, "rtt_ms": None, "error": "timeout"}, "ports": [],
         "maintenance": True, "paused": False, "history": []},
    ]
    dashboard.config = {"devices": devices, "dashboard": {"refresh_seconds": 30}}
    dashboard.set_status_provider(lambda: devices)
    client = dashboard.app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "1 of 3 devices down" in body       # banner: Broken counts, Rebooting does not
    assert "MAINTENANCE" in body               # state pill
    assert "bar up" in body                    # heartbeat strip
    assert "Sort: name" in body                # control row
    assert "Help &amp; FAQ" in body
    dashboard.set_status_provider(None)
    dashboard.config = None


def test_dashboard_all_operational_banner():
    devices = [{"name": "Nitro", "host": "192.168.2.100",
                "ping": {"alive": True, "rtt_ms": 1.2, "error": None}, "ports": [],
                "maintenance": False, "paused": False, "history": [True]}]
    dashboard.config = {"devices": devices, "dashboard": {"refresh_seconds": 30}}
    dashboard.set_status_provider(lambda: devices)
    client = dashboard.app.test_client()
    body = client.get("/").data.decode()
    assert "All systems operational" in body
    dashboard.set_status_provider(None)
    dashboard.config = None
