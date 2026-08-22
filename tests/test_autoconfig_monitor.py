"""Tests for autoconfig: network discovery and first-run config generation."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import autoconfig
from monitor import AlertState


# ---------- autoconfig: config generation ----------

def test_build_default_config_structure():
    devices = [{"name": "Test", "host": "10.0.0.1", "ports": [80]}]
    cfg = autoconfig.build_default_config(devices)
    assert cfg["devices"] == devices
    assert cfg["monitor"]["interval_seconds"] == 30
    assert cfg["thresholds"]["ping_timeout"] == 3
    assert cfg["alerting"]["repeat_interval_minutes"] == 15
    assert cfg["alerts"]["console"]["enabled"] is True
    assert cfg["alerts"]["email"]["enabled"] is False


def test_auto_configure_writes_file(tmp_path, monkeypatch):
    monkeypatch.setattr(autoconfig, "detect_local_ip", lambda: "192.168.1.50")
    monkeypatch.setattr(autoconfig, "detect_gateway", lambda: "192.168.1.1")
    monkeypatch.setattr(autoconfig, "ping_sweep", lambda *a, **k: ["192.168.1.20", "192.168.1.30"])
    monkeypatch.setattr(autoconfig.socket, "gethostname", lambda: "testpc.local")

    path = str(tmp_path / "config.yaml")
    cfg = autoconfig.auto_configure(path)

    names = [d["name"] for d in cfg["devices"]]
    hosts = [d["host"] for d in cfg["devices"]]
    assert "testpc" in names            # hostname, no domain suffix
    assert "Gateway" in names
    assert "192.168.1.1" in hosts
    assert "192.168.1.20" in hosts       # sweep results included
    assert "192.168.1.30" in hosts
    # local machine appears exactly once (as testpc), sweep hosts not duplicated
    assert hosts.count("192.168.1.50") == 1
    assert os.path.exists(path)

    # File parses back as valid YAML.
    import yaml
    with open(path) as f:
        reloaded = yaml.safe_load(f)
    assert len(reloaded["devices"]) == 4


def test_load_config_creates_on_first_run(tmp_path, monkeypatch):
    monkeypatch.setattr(autoconfig, "detect_local_ip", lambda: "10.0.0.5")
    monkeypatch.setattr(autoconfig, "detect_gateway", lambda: "10.0.0.1")
    monkeypatch.setattr(autoconfig, "ping_sweep", lambda *a, **k: [])

    path = str(tmp_path / "config.yaml")
    cfg = autoconfig.load_config(path)
    assert cfg is not None
    assert len(cfg["devices"]) == 2  # this machine + gateway


def test_load_config_reads_existing(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("devices:\n  - name: Custom\n    host: 1.2.3.4\n    ports: []\n")
    cfg = autoconfig.load_config(str(path))
    assert cfg["devices"][0]["name"] == "Custom"


# ---------- AlertState: transition-based dedup ----------

def _device(name="gw"):
    return {"name": name, "host": "192.168.1.1", "ports": [80]}


def _result(alive=True, rtt_ms=10, ports=None):
    return {
        "ping": {"alive": alive, "rtt_ms": rtt_ms, "error": None if alive else "timeout"},
        "ports": ports if ports is not None else [],
    }


def test_down_fires_once_then_quiet():
    state = AlertState()
    dev = _device()
    t = 1000.0

    a1 = state.evaluate(dev, _result(alive=False), {}, now=t)
    assert len(a1) == 1 and a1[0][0] == "CRITICAL"

    # Next 5 cycles: still down, no repeats (repeat disabled).
    for i in range(5):
        a = state.evaluate(dev, _result(alive=False), {}, now=t + i + 1)
        assert a == []


def test_repeat_interval_reminds_while_down():
    state = AlertState(repeat_interval_s=60)
    dev = _device()
    t = 5000.0

    assert len(state.evaluate(dev, _result(alive=False), {}, now=t)) == 1
    # 30s later: quiet
    assert state.evaluate(dev, _result(alive=False), {}, now=t + 30) == []
    # 60s later: reminder
    a = state.evaluate(dev, _result(alive=False), {}, now=t + 90)
    assert len(a) == 1 and "Still down" in a[0][1]


def test_recovery_fires_info():
    state = AlertState()
    dev = _device()
    state.evaluate(dev, _result(alive=False), {}, now=1)
    a = state.evaluate(dev, _result(alive=True), {}, now=2)
    assert any(sev == "INFO" and "recovered" in msg for sev, msg in a)


def test_latency_warns_on_crossing_only():
    state = AlertState()
    dev = _device()
    thr = {"max_response_time": 100}

    assert state.evaluate(dev, _result(rtt_ms=10), thr, now=1) == []
    a = state.evaluate(dev, _result(rtt_ms=250), thr, now=2)
    assert any(sev == "WARNING" and "latency" in msg.lower() for sev, msg in a)
    # still high: quiet
    assert state.evaluate(dev, _result(rtt_ms=300), thr, now=3) == []
    # back to normal: recovery info
    a = state.evaluate(dev, _result(rtt_ms=10), thr, now=4)
    assert any(sev == "INFO" for sev, msg in a)


def test_port_transition_alerts():
    state = AlertState()
    dev = _device()
    thr = {}

    assert state.evaluate(dev, _result(ports=[{"port": 80, "open": True, "error": None}]), thr, now=1) == []
    a = state.evaluate(dev, _result(ports=[{"port": 80, "open": False, "error": "refused"}]), thr, now=2)
    assert any("Port 80" in msg for sev, msg in a)
    assert state.evaluate(dev, _result(ports=[{"port": 80, "open": False, "error": "refused"}]), thr, now=3) == []
