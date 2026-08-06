"""
Network Monitor - main monitoring loop.

Reads device config from config.yaml, runs ping and port checks
on each device at a configured interval, and dispatches alerts
when devices go down or exceed response time thresholds.
"""

import time
import yaml
from checker import check_device
from alerts import dispatch_alert
from logger import get_logger


def load_config(path="config.yaml"):
    """Load configuration from YAML file."""
    try:
        with open(path, "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Config file not found: {path}")
        print("Copy config.yaml.example to config.yaml and edit it.")
        raise


def run_monitor_cycle(config, log):
    """Run one full monitoring cycle across all devices."""
    thresholds = config.get("thresholds", {})
    alerts = config.get("alerts", {})

    for device in config.get("devices", []):
        result = check_device(
            device,
            ping_timeout=thresholds.get("ping_timeout", 3),
            port_timeout=thresholds.get("port_timeout", 2)
        )

        if not result["ping"]["alive"]:
            error_msg = result["ping"]["error"] or "not responding"
            dispatch_alert(alerts, device["name"], f"Device down - {error_msg}", "CRITICAL")
            continue

        rtt = result["ping"]["rtt_ms"]
        max_rtt = thresholds.get("max_response_time", 100)
        if rtt and rtt > max_rtt:
            msg = f"High latency - {rtt}ms exceeds threshold of {max_rtt}ms"
            dispatch_alert(alerts, device["name"], msg, "WARNING")

        for port_result in result["ports"]:
            if not port_result["open"]:
                msg = f"Port {port_result['port']} closed - {port_result['error']}"
                dispatch_alert(alerts, device["name"], msg, "WARNING")

        ports_open = sum(1 for p in result["ports"] if p["open"])
        total_ports = len(result["ports"])
        log.info(f"{device['name']} ({device['host']}): alive, {rtt}ms, {ports_open}/{total_ports} ports open")


def main():
    config = load_config()
    log_config = config.get("logging", {})
    log = get_logger(
        "monitor",
        level=log_config.get("level", "INFO"),
        log_file=log_config.get("file", "monitor.log"),
        max_size_mb=log_config.get("max_size_mb", 5),
        backup_count=log_config.get("backup_count", 3)
    )

    log.info("Network Monitor starting up")
    num_devices = len(config.get("devices", []))
    log.info(f"Monitoring {num_devices} devices")

    interval = config.get("dashboard", {}).get("refresh_seconds", 30)

    try:
        while True:
            run_monitor_cycle(config, log)
            time.sleep(interval)
    except KeyboardInterrupt:
        log.info("Network Monitor shutting down")


if __name__ == "__main__":
    main()
