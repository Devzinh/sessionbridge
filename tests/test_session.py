import asyncio
import math
from types import SimpleNamespace

import pytest
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from browser import session as session_module
from browser.session import SessionBridge
from tests.fakes import FakePage


@pytest.mark.parametrize("url", ["", "example.com", "file:///tmp/a", "javascript:alert(1)"])
@pytest.mark.asyncio
async def test_open_url_rejects_invalid_urls_before_connection(url):
    session = SessionBridge()

    async def fail_if_called():
        raise AssertionError("CDP connection must not be attempted")

    session.ensure_active = fail_if_called

    with pytest.raises(ValueError, match="absolute HTTP or HTTPS URL"):
        await session.open_url(url)


@pytest.mark.parametrize("url", ["http://example.com", "https://example.com/path"])
def test_validate_http_url_accepts_absolute_http_urls(url):
    assert session_module.validate_http_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        None,
        1,
        "   ",
        "http://:80",
        "https://user:secret@example.com",
        "https://example.com:bad",
        "https://example.com ",
        "https://exa mple.com",
        "https://example.com\n.evil",
    ],
)
@pytest.mark.asyncio
async def test_open_url_rejects_malformed_or_credentialed_urls_before_connection(url):
    session = SessionBridge()

    async def fail_if_called():
        raise AssertionError("CDP connection must not be attempted")

    session.ensure_active = fail_if_called

    with pytest.raises(ValueError, match="absolute HTTP or HTTPS URL"):
        await session.open_url(url)


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1:8080", "https://[::1]/path", "https://example.com:443/path"],
)
def test_validate_http_url_accepts_common_hosts(url):
    assert session_module.validate_http_url(url) == url


@pytest.mark.parametrize("max_length", [0, -1, 100001, 1.5, "4", True])
@pytest.mark.asyncio
async def test_get_content_rejects_max_length_outside_supported_range(max_length):
    session = SessionBridge()

    async def fail_if_called():
        raise AssertionError("CDP connection must not be attempted")

    session.ensure_active = fail_if_called

    with pytest.raises(ValueError, match="between 1 and 100000"):
        await session.get_content(max_length=max_length)


@pytest.mark.asyncio
async def test_get_content_length_matches_truncated_text():
    session = SessionBridge()
    page = FakePage(body="abcdefghij")

    async def active_page(timeout_seconds=None):
        return page

    session.ensure_active = active_page

    content = await session.get_content(max_length=4)

    assert content["text"] == "abcd"
    assert content["length"] == 4


@pytest.mark.parametrize(
    ("timeout_seconds", "poll_interval"),
    [
        (0, 1),
        (-1, 1),
        (1, 0),
        (1, -0.1),
        (True, 1),
        (1, "1"),
        (1, math.nan),
        (1, math.inf),
    ],
)
@pytest.mark.asyncio
async def test_wait_for_human_rejects_non_positive_timing_values(
    timeout_seconds, poll_interval
):
    session = SessionBridge()

    async def fail_if_called():
        raise AssertionError("CDP connection must not be attempted")

    session.ensure_active = fail_if_called

    with pytest.raises(ValueError, match="greater than zero"):
        await session.wait_for_human(timeout_seconds, poll_interval)


@pytest.mark.asyncio
async def test_wait_for_human_returns_complete_ready_state(monkeypatch):
    session = SessionBridge()
    page = FakePage()
    states = iter(
        [
            {
                "connected": True,
                "url": "https://example.com/challenge",
                "title": "Challenge",
                "manual_interaction_required": True,
                "reason": "Human verification required",
                "ready": False,
            },
            {
                "connected": True,
                "url": "https://example.com/home",
                "title": "Home",
                "manual_interaction_required": False,
                "reason": "Normal page state",
                "ready": True,
            },
        ]
    )

    async def active_page(timeout_seconds=None):
        return page

    async def inspect(_page):
        return next(states)

    async def no_sleep(_seconds):
        return None

    monotonic_values = iter([10.0, 10.0, 10.1, 10.1, 10.2])
    session.ensure_active = active_page
    monkeypatch.setattr(session_module, "inspect_page_state", inspect)
    monkeypatch.setattr(session_module.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(
        session_module,
        "time",
        SimpleNamespace(
            monotonic=lambda: next(monotonic_values),
            time=lambda: (_ for _ in ()).throw(
                AssertionError("time.time must not be used")
            ),
        ),
    )

    result = await session.wait_for_human(timeout_seconds=5, poll_interval=0.1)

    assert result == {
        "connected": True,
        "url": "https://example.com/home",
        "title": "Home",
        "manual_interaction_required": False,
        "reason": "Normal page state",
        "ready": True,
        "success": True,
    }


@pytest.mark.asyncio
async def test_wait_for_human_timeout_returns_complete_final_state(monkeypatch):
    session = SessionBridge()
    page = FakePage()
    final_state = {
        "connected": True,
        "url": "https://example.com/challenge",
        "title": "Challenge",
        "manual_interaction_required": True,
        "reason": "Human verification required",
        "ready": False,
    }

    async def active_page(timeout_seconds=None):
        return page

    async def inspect(_page):
        return final_state.copy()

    session.ensure_active = active_page
    monkeypatch.setattr(session_module, "inspect_page_state", inspect)
    monotonic_values = iter([10.0, 10.0, 11.0])
    monkeypatch.setattr(
        session_module,
        "time",
        SimpleNamespace(monotonic=lambda: next(monotonic_values)),
    )

    result = await session.wait_for_human(timeout_seconds=1, poll_interval=0.1)

    assert result["success"] is False
    assert result["connected"] is True
    assert result["url"] == final_state["url"]
    assert result["title"] == final_state["title"]
    assert result["manual_interaction_required"] is True
    assert result["ready"] is False
    assert "Timed out after 1 second waiting" in result["reason"]
    assert "Human verification required" in result["reason"]


@pytest.mark.asyncio
async def test_wait_for_human_caps_sleep_to_remaining_timeout(monkeypatch):
    session = SessionBridge()
    page = FakePage()
    blocked_state = {
        "connected": True,
        "url": "https://example.com/challenge",
        "title": "Challenge",
        "manual_interaction_required": True,
        "reason": "Human verification required",
        "ready": False,
    }
    requested_sleeps = []

    async def active_page(timeout_seconds=None):
        return page

    async def inspect(_page):
        return blocked_state.copy()

    async def record_sleep(seconds):
        requested_sleeps.append(seconds)

    monotonic_values = iter([10.0, 10.0, 10.75, 11.0])
    session.ensure_active = active_page
    monkeypatch.setattr(session_module, "inspect_page_state", inspect)
    monkeypatch.setattr(session_module.asyncio, "sleep", record_sleep)
    monkeypatch.setattr(
        session_module,
        "time",
        SimpleNamespace(monotonic=lambda: next(monotonic_values)),
    )

    await session.wait_for_human(timeout_seconds=1, poll_interval=5)

    assert requested_sleeps == [0.25]


@pytest.mark.asyncio
async def test_wait_for_human_does_not_accept_ready_state_after_deadline(monkeypatch):
    session = SessionBridge()
    page = FakePage()
    states = iter(
        [
            {
                "connected": True,
                "url": "https://example.com/challenge",
                "title": "Challenge",
                "manual_interaction_required": True,
                "reason": "Human verification required",
                "ready": False,
            },
            {
                "connected": True,
                "url": "https://example.com/home",
                "title": "Home",
                "manual_interaction_required": False,
                "reason": "Normal page state",
                "ready": True,
            },
        ]
    )

    async def active_page(timeout_seconds=None):
        return page

    async def inspect(_page):
        return next(states)

    async def no_sleep(_seconds):
        return None

    monotonic_values = iter([10.0, 10.5, 11.0])
    session.ensure_active = active_page
    monkeypatch.setattr(session_module, "inspect_page_state", inspect)
    monkeypatch.setattr(session_module.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(
        session_module,
        "time",
        SimpleNamespace(monotonic=lambda: next(monotonic_values)),
    )

    result = await session.wait_for_human(timeout_seconds=1, poll_interval=0.5)

    assert result["success"] is False
    assert result["url"] == "https://example.com/challenge"
    assert result["title"] == "Challenge"
    assert result["ready"] is False
    assert "Timed out after 1 second" in result["reason"]
    assert "Human verification required" in result["reason"]


@pytest.mark.asyncio
async def test_wait_for_human_rechecks_deadline_after_ready_inspection(monkeypatch):
    session = SessionBridge()
    page = FakePage()
    monotonic_values = iter([10.0, 10.0, 11.1])

    async def active_page(timeout_seconds=None):
        return page

    async def inspect(_page):
        return {
            "connected": True,
            "url": "https://example.com/home",
            "title": "Home",
            "manual_interaction_required": False,
            "reason": "Normal page state",
            "ready": True,
        }

    session.ensure_active = active_page
    monkeypatch.setattr(session_module, "inspect_page_state", inspect)
    monkeypatch.setattr(
        session_module,
        "time",
        SimpleNamespace(monotonic=lambda: next(monotonic_values)),
    )

    result = await session.wait_for_human(timeout_seconds=1, poll_interval=0.1)

    assert result["success"] is False
    assert result["ready"] is True
    assert result["url"] == "https://example.com/home"
    assert "Timed out after 1 second" in result["reason"]


@pytest.mark.asyncio
async def test_wait_for_human_times_out_when_inspection_never_finishes(monkeypatch):
    session = SessionBridge()
    page = FakePage()
    never_finishes = session_module.asyncio.Event()

    async def active_page(timeout_seconds=None):
        return page

    async def inspect(_page):
        await never_finishes.wait()

    session.ensure_active = active_page
    monkeypatch.setattr(session_module, "inspect_page_state", inspect)

    result = await session.wait_for_human(timeout_seconds=0.01, poll_interval=0.005)

    assert result["success"] is False
    assert result["connected"] is False
    assert result["url"] == ""
    assert result["title"] == ""
    assert result["manual_interaction_required"] is False
    assert result["ready"] is False
    assert "Timed out after 0.01 seconds" in result["reason"]
    assert "No page state inspection completed" in result["reason"]


@pytest.mark.asyncio
async def test_wait_for_human_deadline_includes_ensure_active():
    session = SessionBridge()

    async def pending_connection(timeout_seconds=None):
        assert timeout_seconds is not None
        await session_module.asyncio.sleep(timeout_seconds)
        raise session_module.asyncio.TimeoutError

    session.ensure_active = pending_connection

    result = await session.wait_for_human(timeout_seconds=0.01, poll_interval=0.005)

    assert result["success"] is False
    assert result["connected"] is False
    assert result["ready"] is False
    assert "Timed out after 0.01 seconds" in result["reason"]


@pytest.mark.asyncio
async def test_wait_for_human_deadline_includes_page_selection():
    session = SessionBridge()
    never_finishes = asyncio.Event()

    class HangingPageSelectionCDP:
        is_connected = False

        async def connect(self, auto_launch=True, timeout_sec=None):
            self.is_connected = True

        async def get_or_create_page(self):
            await never_finishes.wait()

    session.cdp = HangingPageSelectionCDP()

    result = await asyncio.wait_for(
        session.wait_for_human(timeout_seconds=0.01, poll_interval=0.005),
        timeout=0.05,
    )

    assert result["success"] is False
    assert result["connected"] is False
    assert result["ready"] is False
    assert "Timed out after 0.01 seconds" in result["reason"]


@pytest.mark.asyncio
async def test_open_url_inspects_page_after_playwright_timeout(monkeypatch):
    class TimeoutPage(FakePage):
        async def goto(self, url, **kwargs):
            self.url = url
            raise PlaywrightTimeoutError("navigation timed out")

    session = SessionBridge()
    page = TimeoutPage(title="Still loading")

    async def active_page():
        return page

    async def no_sleep(_seconds):
        return None

    session.ensure_active = active_page
    monkeypatch.setattr(session_module.asyncio, "sleep", no_sleep)

    result = await session.open_url("https://example.com/slow")

    assert result["connected"] is True
    assert result["url"] == "https://example.com/slow"
    assert result["ready"] is True


@pytest.mark.asyncio
async def test_open_url_normalizes_non_timeout_playwright_navigation_error():
    class BrokenNavigationPage(FakePage):
        async def goto(self, url, **kwargs):
            self.url = url
            raise PlaywrightError("navigation failed")

    session = SessionBridge()
    page = BrokenNavigationPage(title="Previous page")

    async def active_page():
        return page

    session.ensure_active = active_page

    result = await session.open_url("https://example.com/broken")

    assert result == {
        "connected": False,
        "url": "https://example.com/broken",
        "title": "Previous page",
        "manual_interaction_required": False,
        "reason": "Navigation error: navigation failed",
        "ready": False,
    }


@pytest.mark.asyncio
async def test_open_url_does_not_swallow_unexpected_navigation_error():
    class UnexpectedFailurePage(FakePage):
        async def goto(self, url, **kwargs):
            raise RuntimeError("unexpected failure")

    session = SessionBridge()

    async def active_page():
        return UnexpectedFailurePage()

    session.ensure_active = active_page

    with pytest.raises(RuntimeError, match="unexpected failure"):
        await session.open_url("https://example.com")
