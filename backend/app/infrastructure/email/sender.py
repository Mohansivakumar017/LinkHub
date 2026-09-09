import asyncio
import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage as SMTPMessage
from typing import Protocol

from app.core.config import get_settings

logger = logging.getLogger(__name__)
@dataclass(frozen=True)
class EmailMessage:
    to_email: str
    subject: str
    body: str


class EmailSender(Protocol):
    async def send(self, message: EmailMessage) -> None:
        ...


class StructuredLogEmailSender:
    async def send(self, message: EmailMessage) -> None:
        logger.info(
            "email_dispatched",
            extra={
                "to_email": message.to_email,
                "subject": message.subject,
                "body": "[redacted]",
            },
        )


class SMTPEmailSender:
    """Send email through SMTP without blocking the async event loop."""

    async def send(self, message: EmailMessage) -> None:
        settings = get_settings()
        if not settings.smtp_host:
            await StructuredLogEmailSender().send(message)
            return
        smtp_host = settings.smtp_host
        await asyncio.to_thread(
            self._send_sync_with_host,
            smtp_host,
            message,
        )

    def _send_sync_with_host(self, host: str, message: EmailMessage) -> None:
        settings = get_settings()
        email = SMTPMessage()
        email["Subject"] = message.subject
        email["From"] = settings.smtp_from_email
        email["To"] = message.to_email
        email.set_content(message.body)
        with smtplib.SMTP(host, settings.smtp_port, timeout=10) as client:
            if settings.smtp_use_tls:
                client.starttls()
            if settings.smtp_username and settings.smtp_password:
                client.login(settings.smtp_username, settings.smtp_password)
            client.send_message(email)


class BackgroundEmailSender:
    async def send(self, message: EmailMessage) -> None:
        settings = get_settings()
        if not settings.celery_enabled or not settings.celery_email_enabled:
            await SMTPEmailSender().send(message)
            return

        from app.infrastructure.workers.celery_app import celery_app

        celery_app.send_task(
            "workers.send_email",
            args=[message.to_email, message.subject, message.body],
        )
