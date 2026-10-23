import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.jobs.maturity import get_effective_today, run_maturity_check

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def scheduled_maturity_job() -> None:
    """Scheduled task that runs maturity checks at the configured interval.
    Idempotent and safe: uses own database session, rolls back on error, and always closes session.
    """
    logger.info("Executing scheduled FDR maturity check job...")
    db = SessionLocal()
    try:
        today = get_effective_today()
        results = run_maturity_check(db=db, today=today)
        db.commit()
        logger.info(
            f"Scheduled maturity check completed: evaluated={results.get('total_active_evaluated', 0)}, "
            f"marked_due={results.get('marked_renewal_due', 0)}, marked_matured={results.get('marked_matured', 0)}, "
            f"notifications={results.get('notifications_created', 0)}"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error during scheduled maturity check execution: {e}", exc_info=True)
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    """Starts the background scheduler once per process if not already running."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        logger.info("Scheduler already running.")
        return _scheduler

    _scheduler = BackgroundScheduler(daemon=True)
    interval_hours = max(1, settings.MATURITY_CHECK_INTERVAL_HOURS)

    _scheduler.add_job(
        func=scheduled_maturity_job,
        trigger=IntervalTrigger(hours=interval_hours),
        id="fdr_maturity_monitoring_job",
        name="FDR Maturity Monitoring & Proactive Notifications",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(f"Maturity monitoring background scheduler started (Interval: {interval_hours}h).")
    return _scheduler


def shutdown_scheduler() -> None:
    """Shuts down the background scheduler gracefully."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Maturity monitoring background scheduler shut down.")
        _scheduler = None
