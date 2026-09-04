import pytest

from scripts.smoke_test import main


class FakeSession:
    def __init__(
        self,
        opened: dict,
        content_url: str = "https://example.com/",
    ) -> None:
        self.opened = opened
        self.content_url = content_url
        self.closed = False
        self.requested_url = ""
        self.max_length = 0

    async def open_url(self, url: str) -> dict:
        self.requested_url = url
        return self.opened

    async def get_content(self, max_length: int) -> dict:
        self.max_length = max_length
        return {
            "url": self.content_url,
            "title": "Example Domain",
            "text": "not printed",
            "length": 11,
        }

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_smoke_succeeds_and_closes(capsys: pytest.CaptureFixture[str]) -> None:
    session = FakeSession({"connected": True, "ready": True})

    await main(session_factory=lambda: session)

    assert session.requested_url == "https://example.com"
    assert session.max_length == 500
    assert session.closed is True
    output = capsys.readouterr().out
    assert "content_length" in output
    assert "not printed" not in output


@pytest.mark.asyncio
async def test_smoke_closes_when_open_fails() -> None:
    session = FakeSession({"connected": False, "ready": False})

    with pytest.raises(AssertionError):
        await main(session_factory=lambda: session)

    assert session.closed is True


@pytest.mark.asyncio
async def test_smoke_rejects_unexpected_redirect_host_and_closes() -> None:
    session = FakeSession(
        {"connected": True, "ready": True},
        content_url="https://example.com.evil/redirect",
    )

    with pytest.raises(AssertionError, match="expected example.com URL"):
        await main(session_factory=lambda: session)

    assert session.closed is True
