"""
PingGrid web dashboard - served two ways:

1. Embedded (default): `python monitor.py` starts the monitor loop AND
   serves this dashboard on http://localhost:5000 in the same process,
   showing the monitor's cached results (no per-request pings).
2. Standalone: `python dashboard.py` runs it against config.yaml on its
   own, checking devices per request (read-only view without a monitor).
"""

import threading
from datetime import datetime

from flask import Flask, render_template_string

from autoconfig import load_config, DEFAULT_CONFIG_PATH
from checker import check_device
from logger import get_logger

log = get_logger(__name__)

app = Flask(__name__)
config = None
_status_provider = None      # injected by monitor.py in embedded mode
_cache_lock = threading.Lock()

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>PingGrid</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><rect width='16' height='16' rx='3' fill='%230d1117'/><circle cx='8' cy='8' r='5' fill='none' stroke='%233fb950' stroke-width='2'/><circle cx='8' cy='8' r='1.5' fill='%233fb950'/></svg>">
    <meta http-equiv="refresh" content="{{ refresh }}">
    <style>
        :root { color-scheme: dark; }
        body { font-family: ui-monospace, 'Cascadia Mono', Consolas, monospace;
               background: #0d1117; color: #e6edf3; margin: 0; padding: 24px; }
        h1 { font-size: 20px; margin: 0 0 4px; color: #f0f6fc; }
        .sub { color: #8b949e; font-size: 12px; margin-bottom: 20px; }
        .summary { display: flex; gap: 16px; margin-bottom: 20px; }
        .pill { padding: 8px 14px; border-radius: 6px; font-size: 14px;
                background: #161b22; border: 1px solid #30363d; }
        .pill b { color: #58a6ff; }
        .pill.up b { color: #3fb950; }
        .pill.down b { color: #f85149; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }
        .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 14px 16px; }
        .card h3 { margin: 0 0 6px; font-size: 15px; }
        .host { color: #8b949e; font-size: 12px; }
        .status { display: inline-block; padding: 2px 8px; border-radius: 4px;
                  font-size: 12px; font-weight: 600; margin-left: 8px; }
        .up { background: rgba(63,185,80,.15); color: #3fb950; }
        .down { background: rgba(248,81,73,.15); color: #f85149; }
        .rtt { color: #8b949e; font-size: 12px; }
        .ports { margin-top: 8px; font-size: 12px; }
        .port-open { color: #3fb950; }
        .port-closed { color: #f85149; }
    </style>
</head>
<body>
    <h1>PingGrid</h1>
    <div class="sub">Last updated: {{ timestamp }} &middot; auto-refresh {{ refresh }}s</div>
    <div class="summary">
        <span class="pill up"><b>{{ up }}</b> up</span>
        <span class="pill down"><b>{{ down }}</b> down</span>
        <span class="pill"><b>{{ total }}</b> devices</span>
    </div>
    <div class="grid">
    {% for device in devices %}
        <div class="card">
            <h3>{{ device.name }} <span class="host">{{ device.host }}</span>
                <span class="status {{ 'up' if device.ping.alive else 'down' }}">
                    {{ 'UP' if device.ping.alive else 'DOWN' }}</span></h3>
            {% if device.ping.rtt_ms %}<div class="rtt">{{ device.ping.rtt_ms }}ms</div>{% endif %}
            {% if device.ports %}
            <div class="ports">{% for p in device.ports %}
                <span class="port-{{ 'open' if p.open else 'closed' }}">{{ p.port }}:{{ 'open' if p.open else 'closed' }}</span>{% if not loop.last %} &middot; {% endif %}
            {% endfor %}</div>
            {% endif %}
        </div>
    {% endfor %}
    </div>
</body>
</html>"""


def set_status_provider(provider):
    """Inject a status provider (monitor.py embedded mode)."""
    global _status_provider
    _status_provider = provider


def get_device_status(cfg):
    """Status list from the injected provider, or direct checks standalone."""
    if _status_provider is not None:
        try:
            data = _status_provider()
            if data:
                return data
        except Exception:
            pass
    results = []
    for device in cfg.get("devices", []):
        results.append(check_device(device))
    return results


@app.route("/")
def index():
    cfg = config or {}
    devices = get_device_status(cfg)
    up = sum(1 for d in devices if d["ping"]["alive"])
    down = len(devices) - up
    return render_template_string(
        HTML_TEMPLATE,
        devices=devices,
        up=up,
        down=down,
        total=len(devices),
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        refresh=cfg.get("dashboard", {}).get("refresh_seconds", 30),
    )


def main():
    global config
    config = load_config()
    dash = config.get("dashboard", {})
    host = dash.get("host", "0.0.0.0")
    port = dash.get("port", 5000)
    log.info(f"Dashboard (standalone) on http://localhost:{port}")
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
