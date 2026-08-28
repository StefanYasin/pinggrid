"""
Alert dispatch module - sends alerts via email, webhook, or console.
"""

import logging
import smtplib
import requests
from email.mime.text import MIMEText
from logger import get_logger

log = get_logger(__name__)


def send_console_alert(device_name, message, severity="WARNING"):
    """Log alert to console at its own severity (honored when enabled)."""
    level = getattr(logging, severity.upper(), logging.WARNING)
    log.log(level, f"{device_name}: {message}")


def send_email_alert(config, device_name, message):
    """Send email alert via configured SMTP server."""
    if not config.get("enabled"):
        return

    try:
        msg = MIMEText(f"{device_name}: {message}")
        msg["Subject"] = f"Network Alert: {device_name}"
        msg["From"] = config["username"]
        msg["To"] = ", ".join(config["recipients"])

        with smtplib.SMTP(config["smtp_server"], config["smtp_port"]) as server:
            server.starttls()
            server.login(config["username"], config["password"])
            server.send_message(msg)
        log.info(f"Email alert sent for {device_name}")
    except Exception as e:
        log.error(f"Failed to send email alert: {e}")


def send_webhook_alert(config, device_name, message):
    """Send alert to a webhook endpoint."""
    if not config.get("enabled"):
        return

    try:
        payload = {
            "device": device_name,
            "message": message,
            "severity": "warning"
        }
        requests.post(config["url"], json=payload, timeout=5)
        log.info(f"Webhook alert sent for {device_name}")
    except Exception as e:
        log.error(f"Failed to send webhook alert: {e}")


def send_telegram_alert(config, device_name, message):
    """Send alert via Telegram bot API (community roadmap: alert delivery)."""
    if not config.get("enabled"):
        return

    try:
        token = config.get("bot_token", "")
        chat_id = config.get("chat_id", "")
        if not token or not chat_id:
            log.warning("Telegram alert enabled but bot_token/chat_id missing")
            return
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": f"⚠️ [{device_name}] {message}"}
        requests.post(url, json=payload, timeout=5)
        log.info(f"Telegram alert sent for {device_name}")
    except Exception as e:
        log.error(f"Failed to send telegram alert: {e}")


def dispatch_alert(alert_config, device_name, message, severity="WARNING"):
    """Dispatch alert through all enabled channels."""
    console = alert_config.get("console", {})
    if console.get("enabled", True):
        send_console_alert(device_name, message, severity)
    send_email_alert(alert_config.get("email", {}), device_name, message)
    send_webhook_alert(alert_config.get("webhook", {}), device_name, message)
    send_telegram_alert(alert_config.get("telegram", {}), device_name, message)
