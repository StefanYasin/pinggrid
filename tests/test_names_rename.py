# tests/test_names_rename.py
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import yaml

import autoconfig
import dashboard


# ---------- name resolution ----------

def test_dns_name_success(monkeypatch):
    def fake_gethostbyaddr(ip):
        return ("livingroom.lan", [], [ip])
    monkeypatch.setattr(autoconfig.socket, "gethostbyaddr", fake_gethostbyaddr)
    assert autoconfig._dns_name("192.168.2.10") == "livingroom"


def test_dns_name_failure_returns_none(monkeypatch):
    import socket as socket_mod
    def fail(ip):
        raise socket_mod.herror(1, "Unknown host")
    monkeypatch.setattr(autoconfig.socket, "gethostbyaddr", fail)
    assert autoconfig._dns_name("192.168.2.99") is None


def test_netbios_name_parse(monkeypatch):
    def fake_run(*a, **k):
        return SimpleNamespace(stdout="\n   Nitro-PC          <00>  UNIQUE          192.168.2.10\n")
    monkeypatch.setattr(autoconfig.subprocess, "run", fake_run)
    assert autoconfig._netbios_name("192.168.2.10") == "Nitro-PC"


def test_netbios_name_no_match(monkeypatch):
    def fake_run(*a, **k):
        return SimpleNamespace(stdout="Host not found.\n")
    monkeypatch.setattr(autoconfig.subprocess, "run", fake_run)
    assert autoconfig._netbios_name("192.168.2.99") is None


def test_resolve_hostnames_merges_dns_and_netbios(monkeypatch):
    monkeypatch.setattr(autoconfig, "_dns_name", lambda ip: "dns-name" if ip == "10.0.0.2" else None)
    monkeypatch.setattr(autoconfig, "_netbios_name", lambda ip: "nb-name" if ip == "10.0.0.3" else None)
    names = autoconfig.resolve_hostnames(["10.0.0.2", "10.0.0.3", "10.0.0.4"])
    assert names == {"10.0.0.2": "dns-name", "10.0.0.3": "nb-name"}


def test_auto_configure_uses_resolved_names(tmp_path, monkeypatch):
    monkeypatch.setattr(autoconfig, "detect_local_ip", lambda: "192.168.2.100")
    monkeypatch.setattr(autoconfig, "detect_gateway", lambda: "192.168.2.1")
    monkeypatch.setattr(autoconfig, "ping_sweep", lambda *a, **k: ["192.168.2.20", "192.168.2.30"])
    monkeypatch.setattr(autoconfig, "resolve_hostnames", lambda ips: {"192.168.2.20": "Printer"})
    monkeypatch.setattr(autoconfig.socket, "gethostname", lambda: "nitro")

    cfg = autoconfig.auto_configure(str(tmp_path / "config.yaml"))
    names = {d["host"]: d["name"] for d in cfg["devices"]}
    assert names["192.168.2.20"] == "Printer"          # resolved name used
    assert names["192.168.2.30"] == "Host 192.168.2.30"  # fallback intact


# ---------- dashboard rename ----------

def _setup_dashboard(tmp_path):
    dashboard.CONFIG_PATH = str(tmp_path / "config.yaml")
    dashboard.config = {
        "devices": [{"name": "A", "host": "10.0.0.1", "ports": []}],
        "dashboard": {"refresh_seconds": 30},
    }
    return dashboard.app.test_client()


def test_rename_persists_to_config(tmp_path):
    client = _setup_dashboard(tmp_path)
    resp = client.post("/rename", data={"host": "10.0.0.1", "name": "Living Room TV"})
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True

    with open(dashboard.CONFIG_PATH) as f:
        saved = yaml.safe_load(f)
    assert saved["devices"][0]["name"] == "Living Room TV"
    # live config updated too
    assert dashboard.config["devices"][0]["name"] == "Living Room TV"
    dashboard.config = None


def test_rename_unknown_host_404(tmp_path):
    client = _setup_dashboard(tmp_path)
    resp = client.post("/rename", data={"host": "10.9.9.9", "name": "X"})
    assert resp.status_code == 404
    dashboard.config = None


def test_rename_missing_name_400(tmp_path):
    client = _setup_dashboard(tmp_path)
    resp = client.post("/rename", data={"host": "10.0.0.1", "name": "  "})
    assert resp.status_code == 400
    dashboard.config = None
