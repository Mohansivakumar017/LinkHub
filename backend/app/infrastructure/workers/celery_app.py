from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()


def _cleanup_schedule() -> crontab:
    fields = settings.cleanup_schedule_cron.split()
    if len(fields) != 5:
        raise ValueError("cleanup_schedule_cron must contain five cron fields")
    return crontab(
        minute=fields[0],
        hour=fields[1],
        day_of_month=fields[2],
        month_of_year=fields[3],
        day_of_week=fields[4],
    )


def _cron_schedule(value: str) -> crontab:
    fields = value.split()
    if len(fields) != 5:
        raise ValueError("schedule must contain five cron fields")
    return crontab(
        minute=fields[0],
        hour=fields[1],
        day_of_month=fields[2],
        month_of_year=fields[3],
        day_of_week=fields[4],
    )


celery_app = Celery(
    "linkhub",
    broker=settings.redis_dsn,
    backend=settings.redis_dsn if settings.celery_result_backend_enabled else None,
    include=["app.infrastructure.workers.tasks"],
)
celery_app.conf.update(
    task_default_queue="linkhub",
    task_routes={
        "workers.send_email": {"queue": "emails"},
        "workers.build_analytics_report": {"queue": "analytics"},
        "workers.cleanup_expired_resources": {"queue": "maintenance"},
        "workers.notify_expiring_urls": {"queue": "maintenance"},
        "workers.send_weekly_reports": {"queue": "analytics"},
    },
    beat_schedule={
        "cleanup-expired-resources": {
            "task": "workers.cleanup_expired_resources",
            "schedule": _cleanup_schedule(),
        },
        "notify-expiring-urls": {
            "task": "workers.notify_expiring_urls",
            "schedule": crontab(minute=0, hour=9),
        },
        "send-weekly-reports": {
            "task": "workers.send_weekly_reports",
            "schedule": _cron_schedule(settings.weekly_report_schedule_cron),
        },
    },
)
