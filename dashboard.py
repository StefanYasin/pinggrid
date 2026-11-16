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
        :root {
            color-scheme: dark;
            --bg: #0d1117; --card: #161b22; --border: #30363d;
            --text: #e6edf3; --muted: #8b949e; --accent: #58a6ff;
            --green: #3fb950; --red: #f85149; --amber: #d29922; --blue: #3b82f6;
        }
        [data-theme="light"] {
            color-scheme: light;
            --bg: #f6f8fa; --card: #ffffff; --border: #d0d7de;
            --text: #1f2328; --muted: #57606a;
        }
        body { font-family: ui-monospace, 'Cascadia Mono', Consolas, monospace;
               background: var(--bg); color: var(--text); margin: 0; padding: 24px; }
        .top { display: flex; justify-content: space-between; align-items: center; }
        h1 { font-size: 20px; margin: 0 0 4px; }
        #theme { background: none; border: 1px solid var(--border); color: var(--muted);
                 border-radius: 4px; cursor: pointer; font-size: 12px; padding: 3px 8px; }
        #theme:hover { color: var(--accent); border-color: var(--accent); }
        .sub { color: var(--muted); font-size: 12px; margin-bottom: 14px; }
        .banner { border-radius: 8px; padding: 10px 16px; font-size: 13px; font-weight: 600;
                  margin-bottom: 14px; border: 1px solid var(--border); }
        .banner.ok { background: rgba(63,185,80,.12); color: var(--green); }
        .banner.bad { background: rgba(248,81,73,.12); color: var(--red); }
        .controls { display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
        .controls input, .controls select { background: var(--card); color: var(--text);
                  border: 1px solid var(--border); border-radius: 6px; padding: 6px 10px;
                  font-size: 12px; font-family: inherit; }
        .controls input { flex: 1; min-width: 180px; }
        .summary { display: flex; gap: 16px; margin-bottom: 20px; }
        .pill { padding: 8px 14px; border-radius: 6px; font-size: 14px;
                background: var(--card); border: 1px solid var(--border); }
        .pill b { color: var(--accent); }
        .pill.up b { color: var(--green); }
        .pill.down b { color: var(--red); }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }
        .card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 14px 16px; }
        .card h3 { margin: 0 0 6px; font-size: 15px; }
        .host { color: var(--muted); font-size: 12px; }
        .status { display: inline-block; padding: 2px 8px; border-radius: 4px;
                  font-size: 12px; font-weight: 600; margin-left: 8px; }
        .up { background: rgba(63,185,80,.15); color: var(--green); }
        .down { background: rgba(248,81,73,.15); color: var(--red); }
        .maint { background: rgba(59,130,246,.15); color: var(--blue); }
        .paused { background: rgba(139,148,158,.15); color: var(--muted); }
        .rtt { color: var(--muted); font-size: 12px; }
        .ports { margin-top: 8px; font-size: 12px; }
        .port-open { color: var(--green); }
        .port-closed { color: var(--red); }
        .bars { display: flex; gap: 2px; margin-top: 10px; height: 22px; align-items: flex-end; }
        .bar { width: 3px; flex: 0 0 3px; border-radius: 1px; background: var(--border); }
        .bar.up { background: var(--green); }
        .bar.down { background: var(--red); }
        .bars-label { color: var(--muted); font-size: 10px; margin-top: 3px; }
        .rename { background: none; border: 1px solid var(--border); color: var(--muted);
                  border-radius: 4px; cursor: pointer; font-size: 11px;
                  padding: 1px 6px; margin-left: 8px; vertical-align: middle; }
        .rename:hover { color: var(--accent); border-color: var(--accent); }
        .help { margin-top: 28px; background: var(--card); border: 1px solid var(--border);
                border-radius: 8px; padding: 14px 18px; }
        .help summary { cursor: pointer; color: var(--muted); font-size: 13px; }
        .help summary:hover { color: var(--text); }
        .help h4 { font-size: 13px; margin: 14px 0 4px; }
        .help p { color: var(--muted); font-size: 12px; margin: 0 0 6px; line-height: 1.5; }
        .help code { color: var(--accent); background: var(--bg); padding: 1px 5px; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="top"><h1>PingGrid</h1>
    <button id="theme" title="Toggle light / dark theme">&#9680; theme</button></div>
    <div class="sub">Last updated: {{ timestamp }} &middot; auto-refresh {{ refresh }}s &middot; click &#9998; on a card to rename a device (saved to config.yaml)</div>

    {% if total %}
    <div class="banner {{ 'ok' if down == 0 else 'bad' }}">
        {% if down == 0 %}All systems operational{% else %}{{ down }} of {{ total }} device{{ 's' if total != 1 else '' }} down{% endif %}
    </div>
    {% endif %}

    <div class="controls">
        <input id="search" type="text" placeholder="Search name, IP or port...">
        <select id="filter">
            <option value="all">All</option>
            <option value="down">Down only</option>
            <option value="up">Up only</option>
            <option value="maint">Maintenance / paused</option>
        </select>
        <select id="sort">
            <option value="name">Sort: name</option>
            <option value="status">Sort: status</option>
            <option value="latency">Sort: latency</option>
        </select>
    </div>

    <div class="summary">
        <span class="pill up"><b>{{ up }}</b> up</span>
        <span class="pill down"><b>{{ down }}</b> down</span>
        <span class="pill"><b>{{ total }}</b> devices</span>
    </div>

    <div class="grid" id="grid">
    {% for device in devices %}
        {% set state = 'paused' if device.paused else ('maint' if device.maintenance else ('up' if device.ping.alive else 'down')) %}
        <div class="card" data-name="{{ device.name|lower }}" data-host="{{ device.host }}"
             data-status="{{ state }}" data-rtt="{{ device.ping.rtt_ms or 999999 }}">
            <h3><span class="devname">{{ device.name }}</span>
                <button class="rename" data-host="{{ device.host }}" title="Rename this device">&#9998;</button>
                <span class="status {{ state }}">
                    {{ 'PAUSED' if device.paused else ('MAINTENANCE' if device.maintenance else ('UP' if device.ping.alive else 'DOWN')) }}</span></h3>
            <span class="host">{{ device.host }}</span>
            {% if device.ping.rtt_ms %}<div class="rtt">{{ device.ping.rtt_ms }}ms</div>{% endif %}
            {% if device.ports %}
            <div class="ports">{% for p in device.ports %}
                <span class="port-{{ 'open' if p.open else 'closed' }}">{{ p.port }}:{{ 'open' if p.open else 'closed' }}</span>{% if not loop.last %} &middot; {% endif %}
            {% endfor %}</div>
            {% endif %}
            <div class="bars" title="Last checks: green up, red down">
                {% for alive in device.history or [] %}<span class="bar {{ 'up' if alive else 'down' }}"></span>{% endfor %}
            </div>
            <div class="bars-label">last {{ device.history|length if device.history else 0 }} checks</div>
        </div>
    {% endfor %}
    </div>
    <div id="empty" style="display:none; color: var(--muted); font-size: 13px;">No devices match.</div>

    <details class="help">
        <summary>Help &amp; FAQ</summary>
        <h4>What am I looking at?</h4>
        <p>Every device PingGrid found on your network, checked every {{ refresh }} seconds: ping status, response time, ports, and a history strip of the last 50 checks (green up, red down).</p>
        <h4>How do I rename a device?</h4>
        <p>Click the &#9998; button on its card and type a name you recognize (for example "Living Room TV"). The name is saved to <code>config.yaml</code> and survives restarts.</p>
        <h4>Why do some devices show "Host 192.168.x.x"?</h4>
        <p>Discovery found the device by IP sweep but it did not answer a name lookup (reverse DNS or NetBIOS). Rename it with the pencil button, or add it manually to <code>config.yaml</code>.</p>
        <h4>How do I monitor a device PingGrid did not find?</h4>
        <p>Add it under <code>devices:</code> in <code>config.yaml</code> with a name, host, and optional ports, then restart the monitor.</p>
        <h4>How do I pause alerts for a device (planned reboot)?</h4>
        <p>Set <code>maintenance: true</code> on the device in <code>config.yaml</code>. It keeps being checked (so the dashboard stays honest) but never alerts. Set <code>paused: true</code> to mark it as intentionally offline.</p>
        <h4>Why am I not getting alerts?</h4>
        <p>Alerts fire on state change: a device must go down after being up. Check that <code>alerts.console.enabled</code> is true in <code>config.yaml</code>, or enable telegram/email/webhook channels.</p>
        <h4>Does PingGrid send my data anywhere?</h4>
        <p>No. Everything runs locally on this machine. Only alert channels you enable (telegram, webhook, email) make outbound requests.</p>
    </details>

    <script>
    var theme = localStorage.getItem("pinggrid-theme") || "dark";
    document.documentElement.setAttribute("data-theme", theme);
    document.getElementById("theme").addEventListener("click", function() {
        theme = theme === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-theme", theme);
        localStorage.setItem("pinggrid-theme", theme);
    });

    function applyControls() {
        var q = document.getElementById("search").value.toLowerCase();
        var f = document.getElementById("filter").value;
        var cards = Array.prototype.slice.call(document.querySelectorAll("#grid .card"));
        cards.forEach(function(c) {
            var text = (c.getAttribute("data-name") + " " + c.getAttribute("data-host") +
                        " " + (c.querySelector(".ports") ? c.querySelector(".ports").textContent : "")).toLowerCase();
            var matchQ = !q || text.indexOf(q) !== -1;
            var matchF = f === "all" || (f === "maint" ? (c.getAttribute("data-status") === "maint" || c.getAttribute("data-status") === "paused")
                        : c.getAttribute("data-status") === f);
            c.style.display = (matchQ && matchF) ? "" : "none";
        });
        var visible = cards.filter(function(c){ return c.style.display !== "none"; });
        document.getElementById("empty").style.display = visible.length ? "none" : "";
    }
    function applySort() {
        var s = document.getElementById("sort").value;
        var grid = document.getElementById("grid");
        var cards = Array.prototype.slice.call(document.querySelectorAll("#grid .card"));
        cards.sort(function(a, b) {
            if (s === "latency") { return parseFloat(a.getAttribute("data-rtt")) - parseFloat(b.getAttribute("data-rtt")); }
            if (s === "status") {
                var order = {up: 0, maint: 1, paused: 2, down: 3};
                return (order[a.getAttribute("data-status")] || 4) - (order[b.getAttribute("data-status")] || 4);
            }
            return a.getAttribute("data-name").localeCompare(b.getAttribute("data-name"));
        });
        cards.forEach(function(c) { grid.appendChild(c); });
    }
    document.getElementById("search").addEventListener("input", applyControls);
    document.getElementById("filter").addEventListener("change", applyControls);
    document.getElementById("sort").addEventListener("change", applySort);

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
        result = check_device(device)
        result["maintenance"] = bool(device.get("maintenance"))
        result["paused"] = bool(device.get("paused"))
        result["history"] = []
        results.append(result)
    return results


@app.route("/")
def index():
    cfg = config or {}
    devices = get_device_status(cfg)
    up = sum(1 for d in devices if d["ping"]["alive"] and not d.get("paused"))
    down = sum(1 for d in devices if not d["ping"]["alive"] and not d.get("paused") and not d.get("maintenance"))
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
