"""
Network auto-discovery: build a working config.yaml with zero manual setup.

Detects the local machine's IP and default gateway from the OS routing table,
sweeps the local subnet for live hosts, and writes a ready-to-run config.
Used on first run (no config.yaml) and by `--reset-config`.
"""

import ipaddress
import os
import re
import socket
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import yaml
from icmplib import ping

DEFAULT_CONFIG_PATH = "config.yaml"


def detect_local_ip():
    """Best-effort local IPv4 via a UDP connect (sends no packets)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def detect_gateway():
    """Detect the default gateway from the OS routing table."""
    try:
        if sys.platform == "win32":
            out = subprocess.run(
                ["route", "print", "0.0.0.0"],
                capture_output=True, text=True, timeout=5,
            ).stdout
            for line in out.splitlines():
                m = re.search(r"0\.0\.0\.0\s+0\.0\.0\.0\s+(\d+\.\d+\.\d+\.\d+)", line)
                if m:
                    return m.group(1)
        else:
            out = subprocess.run(
                ["ip", "route"], capture_output=True, text=True, timeout=5,
            ).stdout
            for line in out.splitlines():
                parts = line.split()
                if parts[:2] == ["default", "via"]:
                    return parts[2]
    except Exception:
        pass
    return None


def _ping_host(host, timeout):
    """One ICMP probe; falls back to unprivileged sockets on Windows."""
    try:
        return ping(host, count=1, timeout=timeout, privileged=True).is_alive
    except PermissionError:
        try:
            return ping(host, count=1, timeout=timeout, privileged=False).is_alive
        except Exception:
            return False
    except Exception:
        return False


def ping_sweep(subnet, timeout=0.3, max_hosts=16, workers=64):
    """Parallel ICMP sweep of a subnet; returns live host IPs (capped)."""
    net = ipaddress.ip_network(subnet, strict=False)
    live = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {
            ex.submit(_ping_host, str(ip), timeout): str(ip)
            for ip in net.hosts()
        }
        for fut in as_completed(futures):
            ip = futures[fut]
            try:
                if fut.result():
                    live.append(ip)
            except Exception:
                pass
            if len(live) >= max_hosts:
                break
    return live


def build_default_config(devices):
    """Default config structure with the discovered device list."""
    return {
        "devices": devices,
        "monitor": {"interval_seconds": 30},
        "thresholds": {
            "ping_timeout": 3,
            "port_timeout": 2,
            "max_response_time": 100,
        },
        "alerting": {"repeat_interval_minutes": 15},
        "alerts": {
            "email": {
                "enabled": False, "smtp_server": "", "smtp_port": 587,
                "username": "", "password": "", "recipients": [],
            },
            "webhook": {"enabled": False, "url": ""},
            "telegram": {"enabled": False, "bot_token": "", "chat_id": ""},
            "console": {"enabled": True},
        },
        "logging": {
            "level": "INFO", "file": "monitor.log",
            "max_size_mb": 5, "backup_count": 3,
        },
        "dashboard": {"host": "0.0.0.0", "port": 5000, "refresh_seconds": 30},
    }


def auto_configure(path=DEFAULT_CONFIG_PATH, max_discovered=10):
    """
    Discover the network and write a working config.yaml.

    Always monitors this machine and the default gateway, then adds live
    hosts found by a quick subnet sweep. Returns the generated config dict.
    """
    local_ip = detect_local_ip()
    gateway = detect_gateway()
    hostname = socket.gethostname().split(".")[0] or "This Machine"

    devices = [{"name": hostname, "host": local_ip, "ports": []}]
    if gateway:
        devices.append({"name": "Gateway", "host": gateway, "ports": [80, 443]})

    # Sweep the subnet only for private (RFC1918) local IPs.
    try:
        if ipaddress.ip_address(local_ip).is_private:
            subnet = str(ipaddress.ip_network(f"{local_ip}/24", strict=False))
            known = {local_ip, gateway}
            for ip in ping_sweep(subnet, max_hosts=max_discovered):
                if ip not in known:
                    devices.append({"name": f"Host {ip}", "host": ip, "ports": []})
    except Exception:
        pass

    config = build_default_config(devices)
    with open(path, "w") as f:
        yaml.safe_dump(config, f, sort_keys=False)
    return config


def load_config(path=DEFAULT_CONFIG_PATH):
    """
    Load config.yaml; on first run, auto-discover the network and create it.
    """
    if os.path.exists(path):
        with open(path, "r") as f:
            return yaml.safe_load(f)

    print(f"No config found at {path} - detecting your network...", flush=True)
    config = auto_configure(path)
    print(f"Created {path} with {len(config['devices'])} device(s):", flush=True)
    for d in config["devices"]:
        print(f"  - {d['name']} ({d['host']})", flush=True)
    print("Edit it any time, or run with --reset-config to rediscover.\n", flush=True)
    return config
