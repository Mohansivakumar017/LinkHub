from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.infrastructure.repositories.click_repository import ClickRepository


class FakeResult:
    def __init__(self, rows) -> None:
        self._rows = rows

    def all(self):
        return self._rows


class FakeSession:
    async def execute(self, _query):
        return FakeResult(
            [
                SimpleNamespace(
                    id=uuid4(),
                    short_code="campaign",
                    original_url="https://example.com/old",
                    title="Old campaign",
                    is_deleted=True,
                    _mapping={"count": 1},
                ),
                SimpleNamespace(
                    id=uuid4(),
                    short_code="campaign",
                    original_url="https://example.com/new",
                    title="New campaign",
                    is_deleted=False,
                    _mapping={"count": 2},
                ),
            ]
        )


@pytest.mark.asyncio
async def test_top_links_distinguishes_deleted_and_reused_alias_records() -> None:
    repository = ClickRepository(FakeSession())

    rows = await repository.get_top_links(uuid4())

    assert len(rows) == 2
    assert rows[0]["short_code"] == rows[1]["short_code"] == "campaign"
    assert rows[0]["url_id"] != rows[1]["url_id"]
    assert rows[0]["is_deleted"] is True
    assert rows[1]["is_deleted"] is False
    assert rows[0]["clicks"] == 1
    assert rows[1]["clicks"] == 2
