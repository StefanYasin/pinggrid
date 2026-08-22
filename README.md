# Network Monitor Dashboard

A lightweight, self-contained network monitoring tool built in Python. It monitors device availability, tracks response times, checks open ports, and sends alerts when things go down. Designed to be simple to deploy in a homelab or small business environment.

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-active-brightgreen)

---

## Why This Exists

Most network monitoring tools are either too heavy (Nagios, Zabbix) or too simple (a cron job with a ping script). This sits in the middle: enough structure to be useful, light enough to run on a Raspberry Pi or any Linux box without a database.

It was built to demonstrate practical networking and scripting skills: TCP/IP, ICMP, port scanning, logging, alerting, and clean Python architecture.

## Features

- **Telegram alerts** (roadmap #1) — push alerts to your phone via bot
- **Local trend history** (roadmap #1) — append-only JSONL history with uptime summaries, zero cloud


- **Device availability monitoring** via ICMP ping
- **Response time tracking** with historical averages
- **Port scanning** to verify services are listening (SSH, HTTP, RDP, etc.)
- **Alerting** via email, webhook, or console output
- **Dashboard** with a simple local web view
- **Configuration** via a single YAML file
- **Logging** with rotating file handler

## Architecture

```
network-monitor-dashboard/
├── monitor.py          # Main monitoring loop
├── config.yaml         # Device list, thresholds, alert config
├── alerts.py           # Alert dispatch (email, webhook, console)
├── dashboard.py        # Flask web dashboard
├── checker.py          # Ping and port check logic
├── logger.py           # Rotating log handler
├── requirements.txt
└── README.md
```

## Quick Start

```bash
git clone https://github.com/StefanYasin/network-monitor-dashboard.git
cd network-monitor-dashboard
pip install -r requirements.txt

# Edit config.yaml with your devices
cp config.yaml.example config.yaml

# Run the monitor
python monitor.py

# View the dashboard
python dashboard.py
# Open http://localhost:5000
```

## Configuration

```yaml
# config.yaml
devices:
  - name: "Core Switch"
    host: "192.168.1.1"
    ports: [22, 80, 443]
  - name: "ESXi Host"
    host: "192.168.1.10"
    ports: [22, 443, 902]
  - name: "Gateway"
    host: "192.168.1.254"
    ports: [22, 80]

thresholds:
  ping_timeout: 3        # seconds
  port_timeout: 2        # seconds
  max_response_time: 100 # ms before warning

alerts:
  email:
    enabled: false
    smtp_server: ""
    smtp_port: 587
    username: ""
    password: ""
    recipients: []
  webhook:
    enabled: false
    url: ""
  console:
    enabled: true

logging:
  level: "INFO"
  file: "monitor.log"
  max_size_mb: 5
  backup_count: 3

dashboard:
  host: "0.0.0.0"
  port: 5000
  refresh_seconds: 30
```

## Tech Stack

`Python 3.10+` - `PyYAML` - `Flask` - `icmplib` - `python-nmap` - `requests`

## What It Demonstrates

- **Networking fundamentals**: ICMP, TCP, port scanning, response time analysis
- **Python architecture**: clean module separation, config-driven design, error handling
- **Monitoring and alerting**: threshold detection, multi-channel alerting, log rotation
- **Web dashboard**: Flask, real-time status, responsive layout
- **DevOps practices**: config management, logging, health checks

## License

MIT

## Author

**Stefan Yasin** - Technical Operations & Customer Success
[LinkedIn](https://linkedin.com/in/stefanyasin) - [GitHub](https://github.com/stefanyasin)
