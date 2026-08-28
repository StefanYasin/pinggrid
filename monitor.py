"""
PingGrid - main monitoring loop.

First run auto-configures: if config.yaml is missing, the local network is
detected (gateway, subnet sweep) and a working config is written for you.

Alerts are state-change driven: a device going down fires CRITICAL once,
recovery fires INFO once, and still-down reminders repeat on a cooldown.
No more re-alerting every cycle for the same outage.
"""

import argparse
import os
import threading
import time
import webbrowser

from autoconfig import load_config, DEFAULT_CONFIG_PATH
from checker import check_device
from alerts import dispatch_alert
from logger import get_logger

# Shared status cache: monitor thread writes, dashboard thread reads.
_status_cache = []
_status_lock = threading.Lock()


def set_status_cache(results):
    global _status_cache
    with _status_lock:
        _status_cache = results


def get_status_cache():
    with _status_lock:
        return list(_status_cache)


class AlertState:
    """Tracks per-device state so alerts fire on transitions, not every cycle.

    Attributes:
        repeat_interval_s: minimum seconds between repeat CRITICAL alerts
            while a device stays down (None = alert only on the transition).
        down_since: device name -> timestamp it went down.
        was_down: device name -> bool (previous cycle).
        was_latent: device name -> bool (previous cycle latency breach).
        was_port_open: device name -> {port: bool} (previous cycle).
    """

    def __init__(self, repeat_interval_s=None):
        self.repeat_interval_s = repeat_interval_s
        self.down_since = {}
        self.was_down = {}
        self.was_latent = {}
        self.was_port_open = {}

    def evaluate(self, device, result, thresholds, now=None):
        """Return a list of (severity, message) alerts for this check.

        Pure logic, no side effects - unit-testable.
        """
        now = now or time.time()
        name = device["name"]
        alerts = []
        alive = result["ping"]["alive"]
        max_rtt = thresholds.get("max_response_time", 100)

        if not alive:
            first_down = not self.was_down.get(name, False)
            if first_down:
                self.down_since[name] = now
                self.was_down[name] = True
                error = result["ping"]["error"] or "not responding"
                alerts.append(("CRITICAL", f"Device down - {error}"))
            elif self.repeat_interval_s:
                down_for = now - self.down_since.get(name, now)
                if down_for >= self.repeat_interval_s:
                    minutes = int(down_for // 60)
                    alerts.append(("CRITICAL", f"Still down after {minutes} min"))
                    # reset the timer so the reminder repeats on schedule
                    self.down_since[name] = now
            return alerts

        # Device is alive.
        recovered = self.was_down.get(name, False)
        if recovered:
            self.was_down[name] = False
            self.down_since.pop(name, None)
            alerts.append(("INFO", "Device recovered"))

        rtt = result["ping"]["rtt_ms"]
        if rtt is not None and rtt > max_rtt:
            if not self.was_latent.get(name, False):
                self.was_latent[name] = True
                alerts.append(("WARNING", f"High latency - {rtt}ms > {max_rtt}ms"))
        else:
            if self.was_latent.get(name, False):
                self.was_latent[name] = False
                alerts.append(("INFO", "Latency back to normal"))

        prev_ports = self.was_port_open.get(name, {})
        for port_result in result["ports"]:
            port = port_result["port"]
            is_open = port_result["open"]
            was_open = prev_ports.get(port)
            if was_open is not None and was_open != is_open:
                if is_open:
                    alerts.append(("INFO", f"Port {port} now open"))
                else:
                    alerts.append(("WARNING", f"Port {port} closed - {port_result['error']}"))
            prev_ports[port] = is_open
        self.was_port_open[name] = prev_ports

        return alerts


def run_monitor_cycle(config, log, state):
    """Run one full monitoring cycle across all devices.

    Returns a summary dict: {total, up, down, avg_rtt_ms}.
    """
    thresholds = config.get("thresholds", {})
    alerts_cfg = config.get("alerts", {})
    results = []

    for device in config.get("devices", []):
        result = check_device(
            device,
            ping_timeout=thresholds.get("ping_timeout", 3),
            port_timeout=thresholds.get("port_timeout", 2),
        )
        results.append(result)
        alerts = state.evaluate(device, result, thresholds)

        for severity, message in alerts:
            dispatch_alert(alerts_cfg, device["name"], message, severity)

    set_status_cache(results)

    up = sum(1 for r in results if r["ping"]["alive"])
    rtts = [r["ping"]["rtt_ms"] for r in results if r["ping"]["rtt_ms"] is not None]
    avg = round(sum(rtts) / len(rtts), 1) if rtts else None
    return {"total": len(results), "up": up, "down": len(results) - up,
            "avg_rtt_ms": avg}


def start_dashboard(config):
    """Start the Flask dashboard in a background thread and open the browser."""
    import dashboard
    dashboard.config = config
    dashboard.set_status_provider(get_status_cache)
    dash = config.get("dashboard", {})
    host = dash.get("host", "0.0.0.0")
    port = dash.get("port", 5000)
    threading.Thread(
        target=dashboard.app.run,
        kwargs={"host": host, "port": port, "debug": False,
                "use_reloader": False},
        daemon=True,
    ).start()
    url = f"http://localhost:{port}"
    if dash.get("auto_open", True):
        try:
            webbrowser.open(url)
        except Exception:
            pass
    return url


def main():
    parser = argparse.ArgumentParser(description="PingGrid network monitor")
    parser.add_argument("--reset-config", action="store_true",
                        help="Delete config.yaml and rediscover the network")
    parser.add_argument("--once", action="store_true",
                        help="Run a single monitoring cycle and exit")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH,
                        help=f"Config file path (default: {DEFAULT_CONFIG_PATH})")
    parser.add_argument("--no-dashboard", action="store_true",
                        help="Run headless (no web dashboard, no browser)")
    args = parser.parse_args()

    if args.reset_config and os.path.exists(args.config):
        os.remove(args.config)
        print(f"Removed {args.config} - will rediscover on next run")

    config = load_config(args.config)

    log_config = config.get("logging", {})
    log = get_logger(
        "monitor",
        level=log_config.get("level", "INFO"),
        log_file=log_config.get("file", "monitor.log"),
        max_size_mb=log_config.get("max_size_mb", 5),
        backup_count=log_config.get("backup_count", 3),
    )

    log.info("PingGrid starting up")
    devices = config.get("devices", [])
    log.info(f"Monitoring {len(devices)} device(s)")

    repeat_min = config.get("alerting", {}).get("repeat_interval_minutes")
    state = AlertState(repeat_interval_s=repeat_min * 60 if repeat_min else None)
    interval = config.get("monitor", {}).get("interval_seconds", 30)

    if not args.no_dashboard and not args.once:
        url = start_dashboard(config)
        log.info(f"Dashboard: {url}")

    log.info(f"Interval: {interval}s")

    try:
        while True:
            summary = run_monitor_cycle(config, log, state)
            avg = f", avg {summary['avg_rtt_ms']}ms" if summary["avg_rtt_ms"] is not None else ""
            log.info(f"Cycle: {summary['up']}/{summary['total']} up, "
                     f"{summary['down']} down{avg}")
            if args.once:
                log.info("Single cycle complete")
                break
            time.sleep(interval)
    except KeyboardInterrupt:
        log.info("PingGrid shutting down")


if __name__ == "__main__":
    main()
