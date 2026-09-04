import pytest

from browser.state import inspect_page_state
from tests.fakes import FakeElement, FakePage


@pytest.mark.asyncio
async def test_normal_page_is_ready():
    status = await inspect_page_state(FakePage())
    assert status == {
        "connected": True,
        "url": "https://example.com",
        "title": "Example",
        "manual_interaction_required": False,
        "ready": True,
        "reason": "Normal page state",
    }


@pytest.mark.asyncio
async def test_visible_captcha_requires_human():
    page = FakePage(selectors={".g-recaptcha": FakeElement()})
    status = await inspect_page_state(page)
    assert status["manual_interaction_required"] is True
    assert status["ready"] is False
    assert "CAPTCHA" in status["reason"]


@pytest.mark.asyncio
async def test_verification_text_requires_human():
    status = await inspect_page_state(FakePage(body="Verify you are human"))
    assert status["manual_interaction_required"] is True
    assert status["ready"] is False


@pytest.mark.asyncio
async def test_title_error_is_disconnected():
    class BrokenTitlePage(FakePage):
        async def title(self):
            raise RuntimeError("title unavailable")

    status = await inspect_page_state(BrokenTitlePage())
    assert status["connected"] is False
    assert status["manual_interaction_required"] is False
    assert status["ready"] is False
    assert "title unavailable" in status["reason"]


@pytest.mark.asyncio
async def test_cloudflare_title_requires_human():
    status = await inspect_page_state(FakePage(title="Just a moment..."))
    assert status["manual_interaction_required"] is True
    assert status["ready"] is False
    assert "Cloudflare" in status["reason"]


@pytest.mark.asyncio
async def test_visible_cloudflare_selector_requires_human():
    page = FakePage(selectors={"div#cf-turnstile": FakeElement()})
    status = await inspect_page_state(page)
    assert status["manual_interaction_required"] is True
    assert status["ready"] is False
    assert "Cloudflare" in status["reason"]


@pytest.mark.asyncio
async def test_hidden_captcha_allows_ready_state():
    page = FakePage(selectors={".g-recaptcha": FakeElement(visible=False)})
    status = await inspect_page_state(page)
    assert status["manual_interaction_required"] is False
    assert status["ready"] is True


@pytest.mark.asyncio
async def test_javascript_and_cookies_prompt_requires_human():
    page = FakePage(body="Enable JavaScript and cookies to continue")
    status = await inspect_page_state(page)
    assert status["manual_interaction_required"] is True
    assert status["ready"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_point", ["query_selector", "evaluate"])
async def test_inspection_error_is_not_reported_as_ready(failure_point):
    class BrokenInspectionPage(FakePage):
        async def query_selector(self, selector):
            if failure_point == "query_selector":
                raise RuntimeError("selector inspection failed")
            return await super().query_selector(selector)

        async def evaluate(self, script):
            if failure_point == "evaluate":
                raise RuntimeError("body inspection failed")
            return await super().evaluate(script)

    status = await inspect_page_state(BrokenInspectionPage())
    assert status["connected"] is False
    assert status["manual_interaction_required"] is False
    assert status["ready"] is False
    assert "inspection error" in status["reason"].lower()
