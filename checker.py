"""
Network checker module - handles ICMP ping and TCP port checks.
"""

import socket
import time
from icmplib import ping


def check_ping(host, timeout=3):
    """Ping a host and return availability status and response time."""
    try:
        result = ping(host, count=1, timeout=timeout)
        if result.is_alive:
            return {
                "host": host,
                "alive": True,
                "rtt_ms": round(result.avg_rtt, 2),
                "error": None
            }
        return {
            "host": host,
            "alive": False,
            "rtt_ms": None,
            "error": "Host not responding"
        }
    except Exception as e:
        return {
            "host": host,
            "alive": False,
            "rtt_ms": None,
            "error": str(e)
        }


def check_port(host, port, timeout=2):
    """Check if a TCP port is open on the target host."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        start = time.time()
        result = sock.connect_ex((host, port))
        rtt = round((time.time() - start) * 1000, 2)
        sock.close()

        return {
            "host": host,
            "port": port,
            "open": result == 0,
            "rtt_ms": rtt if result == 0 else None,
            "error": None if result == 0 else f"Connection refused (code {result})"
        }
    except Exception as e:
        return {
            "host": host,
            "port": port,
            "open": False,
            "rtt_ms": None,
            "error": str(e)
        }


def check_device(device, ping_timeout=3, port_timeout=2):
    """Run full check on a device: ping + all configured ports."""
    host = device["host"]
    ports = device.get("ports", [])

    ping_result = check_ping(host, ping_timeout)
    port_results = []

    for port in ports:
        port_results.append(check_port(host, port, port_timeout))

    return {
        "name": device["name"],
        "host": host,
        "ping": ping_result,
        "ports": port_results,
        "timestamp": time.time()
    }
