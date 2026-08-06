"""
Lightweight Flask dashboard for the network monitor.
"""

from flask import Flask, render_template_string
import yaml
from checker import check_device
from logger import get_logger

log = get_logger(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Network Monitor</title>
    <meta http-equiv="refresh" content="{{ refresh }}">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .device { background: #fff; padding: 15px; margin: 10px 0; border-radius: 8px;
                  box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .status-up { color: #2e7d32; font-weight: bold; }
        .status-down { color: #c62828; font-weight: bold; }
        .port-open { color: #2e7d32; }
        .port-closed { color: #c62828; }
        h1 { color: #1f3a5f; }
        .rtt { color: #666; font-size: 0.9em; }
        .timestamp { color: #999; font-size: 0.8em; }
    </style>
</head>
<body>
    <h1>Network Monitor Dashboard</h1>
    <p class="timestamp">Last updated: {{ timestamp }}</p>
    {% for device in devices %}
    <div class="device">
        <h3>{{ device.name }} <span class="rtt">({{ device.host }})</span></h3>
        <p>Status:
            <span class="status-{{ 'up' if device.ping.alive else 'down' }}">
                {{ 'UP' if device.ping.alive else 'DOWN' }}
            </span>
            {% if device.ping.rtt_ms %}
            <span class="rtt">- {{ device.ping.rtt_ms }}ms</span>
            {% endif %}
        </p>
        {% if device.ports %}
        <p>Ports:
            {% for port in device.ports %}
            <span class="port-{{ 'open' if port.open else 'closed' }}">
                {{ port.port }}:{{ 'open' if port.open else 'closed' }}
            </span>
            {% if not loop.last %} | {% endif %}
            {% endfor %}
        </p>
        {% endif %}
    </div>
    {% endfor %}
</body>
</html>
"""

app = Flask(__name__)
config = None


def load_config(path="config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def get_device_status(config):
    """Run checks on all devices and return results for dashboard."""
    results = []
    for device in config.get("devices", []):
        result = check_device(device)
        results.append(result)
    return results


@app.route("/")
def index():
    from datetime import datetime
    devices = get_device_status(config)
    return render_template_string(
        HTML_TEMPLATE,
        devices=devices,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        refresh=config.get("dashboard", {}).get("refresh_seconds", 30)
    )


def main():
    global config
    config = load_config()
    dash_config = config.get("dashboard", {})
    host = dash_config.get("host", "0.0.0.0")
    port = dash_config.get("port", 5000)
    log.info(f"Dashboard starting on http://{host}:{port}")
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
