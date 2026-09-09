import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.core.config import get_settings
from app.infrastructure.cache.url_cache import RedisURLCache
from app.infrastructure.db.models.organization import Organization
from app.infrastructure.db.models.url import URL
from app.infrastructure.db.models.user import User
from app.infrastructure.db.session import AsyncSessionLocal
from app.infrastructure.email.sender import (
    BackgroundEmailSender,
    EmailMessage,
    SMTPEmailSender,
    StructuredLogEmailSender,  # noqa: F401
)
from app.infrastructure.repositories.click_repository import ClickRepository
from app.infrastructure.repositories.refresh_token_repository import (
    RefreshTokenRepository,
)
from app.infrastructure.repositories.url_repository import URLRepository
from app.infrastructure.workers.celery_app import celery_app


def _run(coroutine: Any) -> Any:
    return asyncio.run(coroutine)


@celery_app.task(name="workers.send_email", ignore_result=True)
def send_email(to_email: str, subject: str, body: str) -> None:
    """Deliver an email through the configured infrastructure sender."""
    _run(SMTPEmailSender().send(EmailMessage(to_email, subject, body)))


async def _cleanup() -> dict[str, int]:
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        urls = URLRepository(session)
        expired_short_codes = await urls.get_expired_short_codes()
        expired_urls = await urls.archive_expired()
        expired_tokens = await RefreshTokenRepository(session).delete_expired()
        deleted_clicks = await ClickRepository(session).delete_older_than(
            settings.cleanup_click_retention_days
        )
        await session.commit()
        cache = RedisURLCache()
        for short_code in expired_short_codes:
            await cache.delete(short_code)
        return {
            "expired_urls": expired_urls,
            "expired_tokens": expired_tokens,
            "deleted_clicks": deleted_clicks,
        }


@celery_app.task(name="workers.cleanup_expired_resources")
def cleanup_expired_resources() -> dict[str, int]:
    """Archive expired URLs and remove expired tokens and old click events."""
    return _run(_cleanup())


async def _build_analytics_report(
    organization_id: UUID, days: int, limit: int
) -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        clicks = ClickRepository(session)
        return {
            "organization_id": str(organization_id),
            "overview": await clicks.get_org_overview(organization_id, days),
            "time_series": await clicks.get_time_series(organization_id, days),
            "top_links": await clicks.get_top_links(organization_id, days, limit),
        }


@celery_app.task(name="workers.build_analytics_report")
def build_analytics_report(
    organization_id: str, days: int = 30, limit: int = 10
) -> dict[str, Any]:
    """Build a report without holding an API request open for analytics queries."""
    return _run(_build_analytics_report(UUID(organization_id), days, limit))


async def _notify_expiring_urls() -> int:
    settings = get_settings()
    now = datetime.now(UTC).replace(tzinfo=None)
    deadline = now + timedelta(days=settings.expiration_notification_days)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(URL, User)
            .join(User, User.id == URL.owner_user_id)
            .where(
                URL.expires_at > now,
                URL.expires_at <= deadline,
                URL.expiration_notified_at.is_(None),
                URL.is_deleted.is_(False),
                URL.is_archived.is_(False),
                User.is_active.is_(True),
                User.is_email_verified.is_(True),
            )
            .with_for_update(of=URL, skip_locked=True)
        )
        rows = result.all()
        for url, user in rows:
            await BackgroundEmailSender().send(
                EmailMessage(
                    to_email=user.email,
                    subject=f"LinkHub link expires soon: {url.short_code}",
                    body=(
                        f"Your link {url.short_code} expires at "
                        f"{url.expires_at.isoformat()}. Update it before expiration."
                    ),
                )
            )
            url.expiration_notified_at = now
        await session.commit()
        return len(rows)


@celery_app.task(name="workers.notify_expiring_urls", ignore_result=True)
def notify_expiring_urls() -> int:
    """Notify verified owners about links expiring within the configured window."""
    return _run(_notify_expiring_urls())


async def _send_weekly_reports() -> int:
    sent = 0
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Organization, User)
            .join(User, User.id == Organization.owner_user_id)
            .where(User.is_active.is_(True), User.is_email_verified.is_(True))
        )
        for organization, owner in result.all():
            report = await _build_analytics_report(organization.id, 7, 5)
            overview = report["overview"]
            top_links = ", ".join(
                f"{link['short_code']} ({link['clicks']})"
                for link in report["top_links"]
            ) or "No clicks recorded"
            await BackgroundEmailSender().send(
                EmailMessage(
                    to_email=owner.email,
                    subject=f"LinkHub weekly report: {organization.name}",
                    body=(
                        f"Weekly clicks: {overview['total_clicks']}\n"
                        f"Unique visitors: {overview['unique_clicks']}\n"
                        f"Top links: {top_links}"
                    ),
                )
            )
            sent += 1
    return sent


@celery_app.task(name="workers.send_weekly_reports", ignore_result=True)
def send_weekly_reports() -> int:
    """Send each organization owner a seven-day analytics summary."""
    return _run(_send_weekly_reports())
