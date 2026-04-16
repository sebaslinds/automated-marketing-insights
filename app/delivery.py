"""Deliver generated reports through email and Slack."""

from __future__ import annotations

import json
import logging
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
LOGGER = logging.getLogger(__name__)


def _is_enabled(value: str | None) -> bool:
    """Return True when an environment flag enables a feature."""
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _format_currency(value: Any) -> str:
    """Format a numeric value as currency for delivery messages."""
    return f"${float(value):,.2f}"


def _format_impressions(value: Any) -> str:
    """Format impression counts for delivery messages."""
    return f"{int(value):,}"


def _format_percentage(value: Any) -> str:
    """Format percentage values for delivery messages."""
    return f"{float(value):.2f}%"


def _format_roas(value: Any) -> str:
    """Format ROAS values for delivery messages."""
    return f"{float(value):.2f}x"


def _normalize_insights(insights: dict[str, Any]) -> list[dict[str, str]]:
    """Return a clean list of insight objects for message rendering."""
    normalized: list[dict[str, str]] = []

    for item in insights.get("insights", []):
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "type": str(item.get("type", "")).strip() or "insight",
                "title": str(item.get("title", "")).strip() or "Untitled insight",
                "message": str(item.get("message", "")).strip() or "No message provided.",
            }
        )

    return normalized


def _build_summary_lines(data: dict[str, Any]) -> list[str]:
    """Build short KPI summary lines for delivery messages."""
    summary = data.get("summary", {})
    return [
        f"Total Spend: {_format_currency(summary.get('total_spend', 0.0))}",
        f"Total Impressions: {_format_impressions(summary.get('total_impressions', 0))}",
        f"Global CTR: {_format_percentage(summary.get('global_ctr', 0.0))}",
        f"Global ROAS: {_format_roas(summary.get('global_roas', 0.0))}",
    ]


def _build_email_body(data: dict[str, Any], insights: dict[str, Any], report_path: str) -> str:
    """Build the plain text email body."""
    lines = [
        "Weekly Marketing Performance Report",
        "",
        "The latest weekly marketing report has been generated successfully.",
        "",
        "KPI Summary:",
        *_build_summary_lines(data),
        "",
        "Insights:",
    ]

    for item in _normalize_insights(insights):
        lines.extend(
            [
                f"- {item['type'].capitalize()}: {item['title']}",
                f"  {item['message']}",
            ]
        )

    lines.extend(
        [
            "",
            f"Local report path: {report_path}",
        ]
    )

    return "\n".join(lines)


def _build_slack_message(data: dict[str, Any], insights: dict[str, Any], report_path: str) -> str:
    """Build the Slack webhook message text."""
    lines = [
        "*Weekly Marketing Performance Report*",
        "",
        "*KPI Summary*",
        *[f"- {line}" for line in _build_summary_lines(data)],
        "",
        "*Insights*",
    ]

    for item in _normalize_insights(insights):
        lines.append(f"- *{item['type'].capitalize()}* | {item['title']}: {item['message']}")

    lines.extend(
        [
            "",
            f"Local report path: `{report_path}`",
        ]
    )

    return "\n".join(lines)


def send_email_report(data: dict[str, Any], insights: dict[str, Any], report_path: str) -> bool:
    """Send the weekly report by email when email delivery is enabled."""
    load_dotenv()

    if not _is_enabled(os.getenv("EMAIL_ENABLED")):
        LOGGER.info("Email delivery is disabled. Skipping email channel.")
        return False

    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    email_from = os.getenv("EMAIL_FROM")
    email_to = os.getenv("EMAIL_TO")

    if not all([smtp_host, smtp_username, smtp_password, email_from, email_to]):
        LOGGER.error("Email delivery is enabled but SMTP configuration is incomplete.")
        return False

    recipients = [address.strip() for address in email_to.split(",") if address.strip()]
    if not recipients:
        LOGGER.error("Email delivery is enabled but EMAIL_TO is empty.")
        return False

    message = MIMEMultipart()
    message["Subject"] = "Weekly Marketing Performance Report"
    message["From"] = email_from
    message["To"] = ", ".join(recipients)
    message.attach(MIMEText(_build_email_body(data, insights, report_path), "plain", "utf-8"))

    report_file = Path(report_path)
    if report_file.exists():
        attachment = MIMEApplication(report_file.read_bytes(), _subtype="html")
        attachment.add_header("Content-Disposition", "attachment", filename=report_file.name)
        message.attach(attachment)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(email_from, recipients, message.as_string())
    except Exception:
        LOGGER.exception("Email delivery failed.")
        return False

    LOGGER.info("Email report sent successfully to %s.", ", ".join(recipients))
    return True


def send_slack_report(data: dict[str, Any], insights: dict[str, Any], report_path: str) -> bool:
    """Send the weekly report to Slack using an incoming webhook."""
    load_dotenv()

    if not _is_enabled(os.getenv("SLACK_ENABLED")):
        LOGGER.info("Slack delivery is disabled. Skipping Slack channel.")
        return False

    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        LOGGER.error("Slack delivery is enabled but SLACK_WEBHOOK_URL is missing.")
        return False

    payload = json.dumps({"text": _build_slack_message(data, insights, report_path)}).encode("utf-8")
    request = Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            status_code = getattr(response, "status", 200)
            if status_code >= 400:
                LOGGER.error("Slack delivery failed with status code %s.", status_code)
                return False
    except (HTTPError, URLError):
        LOGGER.exception("Slack delivery failed.")
        return False
    except Exception:
        LOGGER.exception("Slack delivery failed.")
        return False

    LOGGER.info("Slack report sent successfully.")
    return True


def deliver_report(data: dict[str, Any], insights: dict[str, Any], report_path: str) -> dict[str, bool]:
    """Attempt enabled delivery channels and return a delivery status summary."""
    load_dotenv()

    LOGGER.info("Starting report delivery.")
    results = {
        "email_sent": send_email_report(data, insights, report_path),
        "slack_sent": send_slack_report(data, insights, report_path),
    }
    LOGGER.info("Delivery results: %s", results)
    return results
