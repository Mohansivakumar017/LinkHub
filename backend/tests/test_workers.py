from app.infrastructure.workers import celery_app as celery_module
from app.infrastructure.workers import tasks


def test_celery_routes_background_work_to_dedicated_queues() -> None:
    routes = celery_module.celery_app.conf.task_routes

    assert routes["workers.send_email"]["queue"] == "emails"
    assert routes["workers.build_analytics_report"]["queue"] == "analytics"
    assert routes["workers.cleanup_expired_resources"]["queue"] == "maintenance"
    assert routes["workers.notify_expiring_urls"]["queue"] == "maintenance"
    assert routes["workers.send_weekly_reports"]["queue"] == "analytics"


def test_notification_tasks_are_scheduled() -> None:
    schedule = celery_module.celery_app.conf.beat_schedule

    assert schedule["notify-expiring-urls"]["task"] == "workers.notify_expiring_urls"
    assert schedule["send-weekly-reports"]["task"] == "workers.send_weekly_reports"


def test_send_email_task_uses_email_sender(monkeypatch) -> None:
    dispatched = []

    async def fake_send(_sender, message) -> None:
        dispatched.append(message)

    monkeypatch.setattr(tasks.StructuredLogEmailSender, "send", fake_send)

    tasks.send_email.run("person@example.com", "Subject", "Body")

    assert len(dispatched) == 1
    assert dispatched[0].to_email == "person@example.com"
    assert dispatched[0].subject == "Subject"
