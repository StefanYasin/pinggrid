<div align="center">

[![Stars](https://img.shields.io/github/stars/StefanYasin/pinggrid?style=flat)]
[![License](https://img.shields.io/github/license/StefanYasin/pinggrid?style=flat)]
[![Issues](https://img.shields.io/github/issues/StefanYasin/pinggrid?style=flat)]
[![Last commit](https://img.shields.io/github/last-commit/StefanYasin/pinggrid?style=flat)]
[![Language](https://img.shields.io/github/languages/top/StefanYasin/pinggrid?style=flat)]

</div>

# PingGrid

A lightweight, self-contained network monitoring tool built in Python. It monitors device availability, tracks response times, checks open ports, and alerts when things go down. Designed to be simple to deploy in a homelab or small business environment.

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-active-brightgreen)

---

## Why This Exists

Most network monitoring tools are either too heavy (Nagios, Zabbix) or too simple (a cron job with a ping script). This sits in the middle: enough structure to be useful, light enough to run on a Raspberry Pi or any Linux box without a database.

**PingGrid configures itself.** On first run it detects your machine, finds your default gateway, sweeps the local subnet for live hosts, and writes a working `config.yaml` for you. No YAML hand-editing required to get started.

## Features

- **Auto-configuration** — first run detects your network (gateway, local IP, live hosts) and writes a working config
- **Device availability monitoring** via ICMP ping
- **Response time tracking** with historical averages
- **Port scanning** to verify services are listening (SSH, HTTP, RDP, etc.)
- **State-change alerting** — alerts fire when a device goes down or recovers, not every cycle (with optional repeat reminders)
- **Alerting** via email, webhook, Telegram, or console output
- **Dashboard** with a simple local web view
- **Local trend history** — append-only JSONL history with uptime summaries, zero cloud
- **Logging** with rotating file handler

## Quick Start

```bash
git clone https://github.com/StefanYasin/pinggrid.git
cd pinggrid
pip install -r requirements.txt

# Run the monitor - config.yaml is auto-created from your network on first
# run, and the web dashboard starts at http://localhost:5000 in the same
# process (your browser opens automatically).
python monitor.py
```

That's it. One command: PingGrid finds your gateway and subnet, sweeps for
live hosts, starts monitoring, and opens the dashboard. The dashboard shows
live status from the monitor's cached results - no per-request pings.

### What auto-config creates

```yaml
devices:
  - name: Nitro              # your machine, from hostname
    host: 192.168.2.100
    ports: []
  - name: Gateway            # your default gateway, auto-detected
    host: 192.168.2.1
    ports: [80, 443]
  - name: Host 192.168.2.10  # live hosts found by the subnet sweep
    host: 192.168.2.10
    ports: []
```

Edit `config.yaml` any time to add/remove devices, ports, or alert channels. Rerun with `--reset-config` to rediscover your network from scratch. An unedited copy of the example config is detected and replaced automatically (backed up to `config.yaml.bak`).

## CLI

```bash
python monitor.py                # monitor + dashboard, browser auto-opens
python monitor.py --no-dashboard # headless: terminal only (servers/cron)
python monitor.py --once         # single check cycle and exit (cron-friendly)
python monitor.py --reset-config # delete config.yaml and rediscover
python dashboard.py              # standalone dashboard (no monitor attached)
```

## Alerts

Alerts are **state-change driven**: a device going down fires `CRITICAL` once, recovery fires `INFO` once, and high latency or closed ports alert only on transition. If a device stays down, a reminder repeats every `alerting.repeat_interval_minutes` (default 15).

Channels are configured under `alerts:` in `config.yaml` — enable console, email (SMTP), webhook, or Telegram. Telegram needs a bot token from [@BotFather](https://t.me/BotFather) and your chat ID (via [@userinfobot](https://t.me/userinfobot)).

## Architecture

```
pinggrid/
├── monitor.py          # Main loop + state-change alerting + embedded dashboard
├── autoconfig.py       # Network discovery + first-run config generation
├── config.yaml         # Auto-created on first run
├── alerts.py           # Alert dispatch (console, email, webhook, telegram)
├── dashboard.py        # Flask web dashboard (embedded in monitor, or standalone)
├── checker.py          # Ping and port check logic
├── logger.py           # Rotating log handler
├── trends.py           # Local JSONL history + uptime summaries
├── requirements.txt
└── README.md
```

## Tech Stack

`Python 3.10+` - `PyYAML` - `Flask` - `icmplib` - `requests`

## What It Demonstrates

- **Networking fundamentals**: ICMP, TCP, port scanning, response time analysis, network discovery
- **Python architecture**: clean module separation, config-driven design, error handling
- **Monitoring and alerting**: state-change detection, threshold logic, multi-channel alerting, log rotation
- **Web dashboard**: Flask, real-time status, responsive layout
- **DevOps practices**: auto-configuration, logging, health checks

## License

MIT

## Author

**Stefan Yasin** - Technical Operations & Customer Success
[LinkedIn](https://linkedin.com/in/stefanyasin) - [GitHub](https://github.com/stefanyasin)
