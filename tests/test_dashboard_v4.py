# tests/test_dashboard_v4.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import yaml

import monitor
import dashboard


class _NullLog:
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass


def test_rtt_history_attached(monkeypatch):
    monitor._history.clear()
    monitor._rtt_history.clear()
    config = {"devices": [{"name": "A", "host": "10.0.0.1", "ports": [], "group": "Servers"}],
              "thresholds": {}, "alerts": {}}
    def fake_check(device, **kw):
        return {"name": device["name"], "host": device["host"],
                "ping": {"alive": True, "rtt_ms": 12.5, "error": None},
                "ports": [], "timestamp": 0}
    monkeypatch.setattr(monitor, "check_device", fake_check)
    state = monitor.AlertState()
    monitor.run_monitor_cycle(config, _NullLog(), state)
    cache = monitor.get_status_cache()
    assert cache[0]["rtt_history"] == [12.5]
    assert cache[0]["group"] == "Servers"


def _device(name, host, state="up", **extra):
    d = {"name": name, "host": host,
         "ping": {"alive": state == "up", "rtt_ms": 1.2 if state == "up" else None,
                  "error": None if state == "up" else "timeout"},
         "ports": [], "maintenance": state == "maint", "paused": state == "paused",
         "history": [True, True], "rtt_history": [1.0, 1.4],
         "hist_str": "1,1", "rtts_str": "1.0,1.4"}
    d.update(extra)
    return d


def test_grouped_render():
    devices = [
        _device("Nitro", "192.168.2.100", group="Servers"),
        _device("NAS", "192.168.2.50", state="down", group="Servers"),
        _device("Printer", "192.168.2.60", group="IoT"),
    ]
    dashboard.config = {"devices": devices, "dashboard": {"refresh_seconds": 30}}
    dashboard.set_status_provider(lambda: devices)
    client = dashboard.app.test_client()
    body = client.get("/").data.decode()
    assert "group-name" in body
    assert ">Servers<" in body and ">IoT<" in body
    # Servers group contains a down device -> worst pill DOWN
    assert "group-head" in body
    dashboard.set_status_provider(None)
    dashboard.config = None


def test_maintenance_toggle_persists(tmp_path):
    dashboard.CONFIG_PATH = str(tmp_path / "config.yaml")
    dashboard.config = {
        "devices": [{"name": "A", "host": "10.0.0.1", "ports": []}],
        "dashboard": {"refresh_seconds": 30},
    }
    client = dashboard.app.test_client()
    resp = client.post("/maintenance", data={"host": "10.0.0.1", "enable": "1"})
    assert resp.status_code == 200
    assert resp.get_json()["maintenance"] is True
    with open(dashboard.CONFIG_PATH) as f:
        saved = yaml.safe_load(f)
    assert saved["devices"][0]["maintenance"] is True

    resp2 = client.post("/maintenance", data={"host": "10.0.0.1", "enable": "0"})
    assert resp2.get_json()["maintenance"] is False
    dashboard.config = None


def test_maintenance_unknown_host_404(tmp_path):
    dashboard.CONFIG_PATH = str(tmp_path / "config.yaml")
    dashboard.config = {"devices": [{"name": "A", "host": "10.0.0.1", "ports": []}],
                        "dashboard": {"refresh_seconds": 30}}
    client = dashboard.app.test_client()
    resp = client.post("/maintenance", data={"host": "10.9.9.9", "enable": "1"})
    assert resp.status_code == 404
    dashboard.config = None


def test_flat_render_when_no_groups():
    devices = [_device("Nitro", "192.168.2.100")]
    dashboard.config = {"devices": devices, "dashboard": {"refresh_seconds": 30}}
    dashboard.set_status_provider(lambda: devices)
    client = dashboard.app.test_client()
    body = client.get("/").data.decode()
    assert "<div class=\"group\">" not in body   # stays flat (CSS class def is fine)
    assert "click card for details" in body  # drawer hint present
    assert "Mute alerts (maintenance)" in body
    dashboard.set_status_provider(None)
    dashboard.config = None
