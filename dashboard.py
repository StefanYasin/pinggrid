"""
PingGrid web dashboard - served two ways:

1. Embedded (default): `python monitor.py` starts the monitor loop AND
   serves this dashboard on http://localhost:5000 in the same process,
   showing the monitor's cached results (no per-request pings).
2. Standalone: `python dashboard.py` runs it against config.yaml on its
   own, checking devices per request (read-only view without a monitor).

Devices can be renamed from the dashboard (the pencil button on each
card); names are written back to config.yaml so they survive restarts.
"""

import threading
from datetime import datetime

import yaml
from flask import Flask, jsonify, render_template_string, request

from autoconfig import load_config, DEFAULT_CONFIG_PATH
from checker import check_device
from logger import get_logger

log = get_logger(__name__)

app = Flask(__name__)
config = None
CONFIG_PATH = DEFAULT_CONFIG_PATH   # where /rename persists names
_status_provider = None             # injected by monitor.py in embedded mode
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
        .rename { background: none; border: 1px solid #30363d; color: #8b949e;
                  border-radius: 4px; cursor: pointer; font-size: 11px;
                  padding: 1px 6px; margin-left: 8px; vertical-align: middle; }
        .rename:hover { color: #58a6ff; border-color: #58a6ff; }
        .help { margin-top: 28px; background: #161b22; border: 1px solid #30363d;
                border-radius: 8px; padding: 14px 18px; }
        .help summary { cursor: pointer; color: #8b949e; font-size: 13px; }
        .help summary:hover { color: #e6edf3; }
        .help h4 { color: #f0f6fc; font-size: 13px; margin: 14px 0 4px; }
        .help p { color: #8b949e; font-size: 12px; margin: 0 0 6px; line-height: 1.5; }
        .help code { color: #58a6ff; background: #0d1117; padding: 1px 5px; border-radius: 4px; }
    </style>
</head>
<body>
    <h1>PingGrid</h1>
    <div class="sub">Last updated: {{ timestamp }} &middot; auto-refresh {{ refresh }}s &middot; click &#9998; on a card to rename a device (saved to config.yaml)</div>
    <div class="summary">
        <span class="pill up"><b>{{ up }}</b> up</span>
        <span class="pill down"><b>{{ down }}</b> down</span>
        <span class="pill"><b>{{ total }}</b> devices</span>
    </div>
    <div class="grid">
    {% for device in devices %}
        <div class="card">
            <h3><span class="devname">{{ device.name }}</span>
                <button class="rename" data-host="{{ device.host }}" title="Rename this device">&#9998;</button>
                <span class="status {{ 'up' if device.ping.alive else 'down' }}">
                    {{ 'UP' if device.ping.alive else 'DOWN' }}</span></h3>
            <span class="host">{{ device.host }}</span>
            {% if device.ping.rtt_ms %}<div class="rtt">{{ device.ping.rtt_ms }}ms</div>{% endif %}
            {% if device.ports %}
            <div class="ports">{% for p in device.ports %}
                <span class="port-{{ 'open' if p.open else 'closed' }}">{{ p.port }}:{{ 'open' if p.open else 'closed' }}</span>{% if not loop.last %} &middot; {% endif %}
            {% endfor %}</div>
            {% endif %}
        </div>
    {% endfor %}
    </div>

    <details class="help">
        <summary>Help &amp; FAQ</summary>
        <h4>What am I looking at?</h4>
        <p>Every device PingGrid found on your network, checked every {{ refresh }} seconds: ping status, response time, and any ports you configured for it.</p>
        <h4>How do I rename a device?</h4>
        <p>Click the &#9998; button on its card and type a name you recognize (for example "Living Room TV"). The name is saved to <code>config.yaml</code> and survives restarts.</p>
        <h4>Why do some devices show "Host 192.168.x.x"?</h4>
        <p>Discovery found the device by IP sweep but it did not answer a name lookup (reverse DNS or NetBIOS). Rename it with the pencil button, or add it manually to <code>config.yaml</code>.</p>
        <h4>How do I monitor a device PingGrid did not find?</h4>
        <p>Add it under <code>devices:</code> in <code>config.yaml</code> with a name, host, and optional ports, then restart the monitor.</p>
        <h4>Why am I not getting alerts?</h4>
        <p>Alerts fire on state change: a device must go down after being up. Check that <code>alerts.console.enabled</code> is true in <code>config.yaml</code>, or enable telegram/email/webhook channels.</p>
        <h4>Does PingGrid send my data anywhere?</h4>
        <p>No. Everything runs locally on this machine. Only alert channels you enable (telegram, webhook, email) make outbound requests.</p>
    </details>

    <script>
    document.querySelectorAll("button.rename").forEach(function(btn) {
        btn.addEventListener("click", function() {
            var host = btn.getAttribute("data-host");
            var card = btn.closest(".card");
            var current = card.querySelector(".devname").textContent.trim();
            var name = prompt("Name for " + host + ":", current);
            if (!name || !name.trim()) { return; }
            fetch("/rename", {
                method: "POST",
                headers: {"Content-Type": "application/x-www-form-urlencoded"},
                body: "host=" + encodeURIComponent(host) + "&name=" + encodeURIComponent(name.trim())
            })
            .then(function(r) { return r.json(); })
            .then(function(j) { if (j.ok) { location.reload(); } else { alert(j.error || "Rename failed"); } })
            .catch(function() { alert("Rename failed: dashboard not reachable"); });
        });
    });
    </script>
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


@app.route("/rename", methods=["POST"])
def rename():
    """Rename a device; persists to config.yaml so it survives restarts."""
    cfg = config or {}
    host = (request.form.get("host") or "").strip()
    new_name = (request.form.get("name") or "").strip()[:40]
    if not host or not new_name:
        return jsonify({"ok": False, "error": "host and name are required"}), 400

    target = None
    for device in cfg.get("devices", []):
        if device.get("host") == host:
            target = device
            break
    if target is None:
        return jsonify({"ok": False, "error": f"no device with host {host}"}), 404

    target["name"] = new_name
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.safe_dump(cfg, f, sort_keys=False)
    except OSError as e:
        return jsonify({"ok": False, "error": f"could not save config: {e}"}), 500

    log.info(f"Renamed {host} to '{new_name}' (saved to {CONFIG_PATH})")
    return jsonify({"ok": True, "name": new_name})


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
