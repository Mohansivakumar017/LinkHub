from datetime import UTC, datetime

from app.infrastructure.db.base import utcnow_naive


def test_utcnow_naive_returns_utc_without_timezone_metadata() -> None:
    value = utcnow_naive()

    assert isinstance(value, datetime)
    assert value.tzinfo is None
    assert (datetime.now(UTC).replace(tzinfo=None) - value).total_seconds() < 5
