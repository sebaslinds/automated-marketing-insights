"""Schedule the weekly marketing reporting pipeline."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

try:
    from app.analyzer import load_and_analyze_data
    from app.insights import generate_insights
    from app.report import generate_html_report, save_report
except ImportError:
    from analyzer import load_and_analyze_data
    from insights import generate_insights
    from report import generate_html_report, save_report


DEFAULT_CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "campaigns.csv"
DEFAULT_TIMEZONE = ZoneInfo("America/Vancouver")
RUN_ON_START = True
TEST_MODE = False


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
LOGGER = logging.getLogger(__name__)


def _fallback_insights(error: Exception) -> dict[str, list[dict[str, str]]]:
    """Build fallback insights when the OpenAI step fails."""
    return {
        "insights": [
            {
                "type": "victoire",
                "title": "Insights indisponibles",
                "message": "Les KPIs ont ete analyses, mais les insights automatiques n ont pas pu etre generes.",
            },
            {
                "type": "alerte",
                "title": "Generation des insights en echec",
                "message": f"Erreur rencontree pendant la generation: {error}",
            },
            {
                "type": "recommandation",
                "title": "Verifier la configuration",
                "message": "Controlez la cle OpenAI, les dependances et les logs avant la prochaine execution planifiee.",
            },
        ]
    }


def run_weekly_pipeline() -> str:
    """Run the weekly analysis, insight generation, and HTML report workflow."""
    LOGGER.info("Weekly pipeline job started.")

    analysis = load_and_analyze_data(DEFAULT_CSV_PATH)

    try:
        insights = generate_insights(analysis)
    except Exception as exc:
        LOGGER.exception("Insights generation failed. Falling back to placeholder insights.")
        insights = _fallback_insights(exc)

    html = generate_html_report(analysis, insights)
    output_path = save_report(html)

    LOGGER.info("Weekly pipeline job completed. Report saved to %s", output_path)
    return output_path


def _run_pipeline_job() -> None:
    """Scheduler wrapper that prevents silent failures."""
    try:
        run_weekly_pipeline()
    except Exception:
        LOGGER.exception("Weekly pipeline job failed.")


def _build_trigger() -> tuple[CronTrigger, str]:
    """Build the scheduler trigger based on the active mode."""
    if TEST_MODE:
        return (
            CronTrigger(minute="*", timezone=DEFAULT_TIMEZONE),
            f"every 1 minute ({DEFAULT_TIMEZONE.key})",
        )

    return (
        CronTrigger(day_of_week="mon", hour=8, minute=0, timezone=DEFAULT_TIMEZONE),
        f"every Monday at 08:00 ({DEFAULT_TIMEZONE.key})",
    )


def start_scheduler() -> None:
    """Start the blocking weekly scheduler."""
    scheduler = BlockingScheduler(timezone=DEFAULT_TIMEZONE)
    trigger, schedule_description = _build_trigger()

    scheduler.add_job(
        _run_pipeline_job,
        trigger=trigger,
        id="weekly_marketing_report",
        replace_existing=True,
    )

    next_run_dt = trigger.get_next_fire_time(None, datetime.now(DEFAULT_TIMEZONE))
    next_run = next_run_dt.isoformat() if next_run_dt else "unknown"

    LOGGER.info("Scheduler started. Weekly pipeline is scheduled for %s.", schedule_description)
    LOGGER.info("Next scheduled run: %s", next_run)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        LOGGER.info("Scheduler stopped.")
    except Exception:
        LOGGER.exception("Scheduler crashed.")
        raise


if __name__ == "__main__":
    if RUN_ON_START:
        try:
            report_path = run_weekly_pipeline()
            print(report_path)
        except Exception:
            LOGGER.exception("Immediate pipeline run failed.")

    start_scheduler()
