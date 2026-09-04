# SessionBridge MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a tested six-tool MCP server that opens a persistent visible Chrome profile, detects manual-interaction states, and resumes through the same CDP session.

**Architecture:** `server.py` exposes MCP stdio tools and delegates to a singleton `SessionBridge`. Browser launch, CDP lifecycle, and page-state classification remain separate modules. Tests inject small fake page/CDP objects and never launch Chrome; one explicit smoke script exercises the real local browser.

**Tech Stack:** Python 3.14, MCP Python SDK (`FastMCP`), Playwright async API, pytest, pytest-asyncio, Windows Chrome/CDP.

---

## File Map

- Modify `server.py`: expose only approved MCP tools.
- Modify `browser/launcher.py`: bind CDP to loopback and report startup failures.
- Modify `browser/cdp.py`: own Playwright/CDP lifecycle without terminating Chrome.
- Modify `browser/session.py`: validate inputs, normalize results, and coordinate handoff.
- Modify `browser/state.py`: classify challenge, ready, and disconnected states.
- Modify `tools/browser.py`: thin six-tool adapter.
- Delete `tools/workflow.py`: remove out-of-scope automation surface.
- Create `tests/fakes.py`: reusable browser test doubles.
- Create `tests/test_imports.py`: environment/import smoke test.
- Create `tests/test_state.py`: page classification tests.
- Create `tests/test_session.py`: session workflow and validation tests.
- Create `tests/test_tools.py`: adapter contract tests.
- Create `tests/test_server.py`: registered MCP tool surface test.
- Create `pyproject.toml`: runtime metadata and pytest configuration.
- Create `.gitignore`: exclude profile, caches, virtual environment, and screenshots.
- Create `README.md`: Windows setup, Codex configuration, usage, and limitations.
- Create `scripts/smoke_test.py`: deliberate real-browser lifecycle check.

Git commit steps are omitted because `C:\Users\roni9\Desktop\Curso Da Sarah` is not currently a Git repository.

### Task 1: Package and Test Foundation

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `tests/__init__.py`
- Create: `tests/fakes.py`

- [ ] **Step 1: Declare package and test configuration**

```toml
[project]
name = "sessionbridge"
version = "0.1.0"
description = "Human-in-the-loop browser sessions over MCP and CDP"
requires-python = ">=3.11"
dependencies = [
  "mcp>=1.0,<2",
  "playwright>=1.40,<2",
]

[project.optional-dependencies]
test = [
  "pytest>=8,<9",
  "pytest-asyncio>=0.24,<2",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Ignore generated local state**

```gitignore
.venv/
__pycache__/
.pytest_cache/
*.py[cod]
.chrome_profile/
screenshot*.png
```

- [ ] **Step 3: Add focused fake page primitives**

```python
class FakeElement:
    def __init__(self, visible: bool = True):
        self.visible = visible

    async def is_visible(self) -> bool:
        return self.visible


class FakePage:
    def __init__(self, *, url="https://example.com", title="Example", body="", selectors=None):
        self.url = url
        self._title = title
        self.body = body
        self.selectors = selectors or {}
        self.closed = False

    async def title(self):
        return self._title

    async def query_selector(self, selector):
        return self.selectors.get(selector)

    async def evaluate(self, script):
        return self.body

    async def goto(self, url, **kwargs):
        self.url = url

    def is_closed(self):
        return self.closed
```

- [ ] **Step 4: Verify test discovery**

```python
def test_runtime_dependencies_import():
    import mcp
    import playwright

    assert mcp is not None
    assert playwright is not None
```

Run: `rtk python -m pytest tests/test_imports.py -q`

Expected: one test PASS and no collection errors.

### Task 2: Page-State Contract

**Files:**
- Modify: `browser/state.py`
- Test: `tests/test_state.py`

- [ ] **Step 1: Write failing classification tests**

```python
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
```

- [ ] **Step 2: Run characterization tests**

Run: `rtk python -m pytest tests/test_state.py -q`

Expected: tests may already PASS because current state classifier implements these invariants. If so, retain implementation unchanged. If any test fails, continue to Step 3.

- [ ] **Step 3: Consolidate state construction and preserve explicit checks**

Only if Step 2 fails from inconsistent payloads, add one `_status` constructor returning exactly six contract fields. Keep existing title, selector, and page-text indicators, but catch page-access errors only at inspection boundaries and place exception text in `reason`.

```python
def _status(*, connected, url, title, manual, ready, reason):
    return {
        "connected": connected,
        "url": url,
        "title": title,
        "manual_interaction_required": manual,
        "ready": ready,
        "reason": reason,
    }
```

- [ ] **Step 4: Verify GREEN**

Run: `rtk python -m pytest tests/test_state.py -q`

Expected: all tests PASS.

### Task 3: Safe Chrome Launch and CDP Lifecycle

**Files:**
- Modify: `browser/launcher.py`
- Modify: `browser/cdp.py`
- Create: `tests/test_launcher.py`
- Create: `tests/test_cdp.py`

- [ ] **Step 1: Write failing launch-argument test**

```python
from pathlib import Path
from unittest.mock import patch

from browser.launcher import launch_chrome


def test_launch_binds_debugging_to_loopback(tmp_path: Path):
    with patch("browser.launcher.find_chrome_executable", return_value="chrome.exe"), patch(
        "browser.launcher.subprocess.Popen"
    ) as popen:
        launch_chrome(user_data_dir=tmp_path)
    args = popen.call_args.args[0]
    assert "--remote-debugging-address=127.0.0.1" in args
    assert f"--user-data-dir={tmp_path}" in args
```

- [ ] **Step 2: Run launcher test and verify RED**

Run: `rtk python -m pytest tests/test_launcher.py -q`

Expected: FAIL because loopback argument is absent.

- [ ] **Step 3: Add explicit loopback argument and startup failure**

Add `--remote-debugging-address=127.0.0.1` beside the port argument. Change `ensure_chrome` to raise `ConnectionError` after timeout rather than returning an ambiguous false value; update `CDPConnection.connect` accordingly.

- [ ] **Step 4: Write CDP disconnect test before changing disconnect code**

```python
import pytest

from browser.cdp import CDPConnection


class FakePlaywright:
    def __init__(self):
        self.stopped = False
    async def stop(self):
        self.stopped = True


class FakeBrowser:
    def __init__(self):
        self.closed = False
    def is_connected(self):
        return True
    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_disconnect_stops_playwright_without_closing_browser():
    connection = CDPConnection()
    connection.playwright = FakePlaywright()
    browser = FakeBrowser()
    connection.browser = browser
    await connection.disconnect()
    assert browser.closed is False
    assert connection.playwright is None
    assert connection.browser is None
```

- [ ] **Step 5: Run CDP test and verify RED**

Run: `rtk python -m pytest tests/test_cdp.py -q`

Expected: FAIL because current implementation calls `browser.close()`.

- [ ] **Step 6: Disconnect transport only**

Remove `browser.close()` from `disconnect`; stop Playwright and clear local references. This detaches automation while leaving externally launched Chrome alive.

- [ ] **Step 7: Verify component tests**

Run: `rtk python -m pytest tests/test_launcher.py tests/test_cdp.py -q`

Expected: all tests PASS.

### Task 4: Session Workflow and Input Invariants

**Files:**
- Modify: `browser/session.py`
- Test: `tests/test_session.py`

- [ ] **Step 1: Write failing URL and content-limit tests**

```python
import pytest

from browser.session import SessionBridge
from tests.fakes import FakePage


@pytest.mark.asyncio
@pytest.mark.parametrize("url", ["", "example.com", "file:///tmp/a", "javascript:alert(1)"])
async def test_open_url_rejects_non_http_urls(url):
    session = SessionBridge()
    with pytest.raises(ValueError, match="absolute HTTP or HTTPS"):
        await session.open_url(url)


@pytest.mark.asyncio
async def test_content_respects_requested_limit():
    session = SessionBridge()
    session.page = FakePage(body="abcdefghij")
    session.cdp.browser = type("Browser", (), {"is_connected": lambda self: True})()
    result = await session.get_content(max_length=4)
    assert result["text"] == "abcd"
    assert result["length"] == 4
```

- [ ] **Step 2: Run tests and verify RED**

Run: `rtk python -m pytest tests/test_session.py -q`

Expected: FAIL because URL validation is absent and returned length describes untrimmed content.

- [ ] **Step 3: Implement validation and bounded content contract**

Use `urllib.parse.urlparse`; require scheme in `{http, https}` and non-empty `netloc`. Require `max_length` from 1 through 100000. Extract body text once, truncate it, and return truncated length.

```python
def validate_http_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("url must be an absolute HTTP or HTTPS URL")
    return url
```

- [ ] **Step 4: Add failing wait transition and timeout tests**

```python
from unittest.mock import AsyncMock, patch


BLOCKED = {
    "connected": True, "url": "https://example.com", "title": "Check",
    "manual_interaction_required": True, "ready": False, "reason": "CAPTCHA",
}
READY = {
    "connected": True, "url": "https://example.com", "title": "Example",
    "manual_interaction_required": False, "ready": True, "reason": "Normal page state",
}


@pytest.mark.asyncio
async def test_wait_returns_when_page_becomes_ready():
    session = SessionBridge()
    session.ensure_active = AsyncMock(return_value=FakePage())
    with patch("browser.session.inspect_page_state", AsyncMock(side_effect=[BLOCKED, READY])), patch(
        "browser.session.asyncio.sleep", AsyncMock()
    ):
        result = await session.wait_for_human(timeout_seconds=5, poll_interval=0)
    assert result["success"] is True
    assert result["reason"] == "Normal page state"


@pytest.mark.asyncio
async def test_wait_rejects_non_positive_timeout():
    session = SessionBridge()
    with pytest.raises(ValueError, match="positive"):
        await session.wait_for_human(timeout_seconds=0)
```

- [ ] **Step 5: Run wait tests and verify RED**

Run: `rtk python -m pytest tests/test_session.py -q`

Expected: FAIL until timeout validation and normalized result fields exist.

- [ ] **Step 6: Implement deterministic wait behavior**

Use `time.monotonic()`, reject `timeout_seconds <= 0`, poll the current page state, return the ready status with `success=True`, and return final inspected state with `success=False` plus timeout reason.

- [ ] **Step 7: Surface navigation errors selectively**

Catch Playwright `TimeoutError` around `goto` and continue to state inspection. Convert other Playwright navigation errors into a normalized disconnected/error response instead of silently discarding them.

- [ ] **Step 8: Verify session tests**

Run: `rtk python -m pytest tests/test_session.py -q`

Expected: all tests PASS.

### Task 5: Six-Tool MCP Surface

**Files:**
- Modify: `tools/browser.py`
- Modify: `server.py`
- Delete: `tools/workflow.py`
- Create: `tests/test_tools.py`
- Create: `tests/test_server.py`

- [ ] **Step 1: Write failing adapter continuation tests**

```python
import pytest
from unittest.mock import AsyncMock, patch

from tools.browser import continue_session


@pytest.mark.asyncio
async def test_continue_session_remains_blocked():
    session = AsyncMock()
    session.get_status.return_value = {
        "connected": True, "url": "https://example.com", "title": "Check",
        "manual_interaction_required": True, "ready": False, "reason": "CAPTCHA",
    }
    with patch("tools.browser.get_session", return_value=session):
        result = await continue_session()
    assert result["status"] == "blocked"
    assert result["ready"] is False
```

- [ ] **Step 2: Run adapter test and verify RED**

Run: `rtk python -m pytest tests/test_tools.py -q`

Expected: FAIL until adapter returns full normalized state without dropping fields.

- [ ] **Step 3: Make adapter thin and contract-preserving**

Keep six functions only. `continue_session` copies complete status and adds `status` as `blocked`, `ready`, or `unavailable`. All other functions directly return session results.

- [ ] **Step 4: Write registered-tool surface test**

```python
import pytest
from server import mcp


@pytest.mark.asyncio
async def test_server_exposes_exact_mvp_tools():
    tools = await mcp.list_tools()
    assert {tool.name for tool in tools} == {
        "open_browser", "get_browser_status", "wait_for_human",
        "continue_session", "get_current_page", "close_browser",
    }
```

- [ ] **Step 5: Run server test and verify RED**

Run: `rtk python -m pytest tests/test_server.py -q`

Expected: FAIL because workflow tools and screenshot are still registered.

- [ ] **Step 6: Remove out-of-scope tools**

Delete workflow imports and four decorators from `server.py`; delete `tools/workflow.py`. Keep `mcp.run()` stdio entrypoint and six approved tools.

- [ ] **Step 7: Verify surface tests**

Run: `rtk python -m pytest tests/test_tools.py tests/test_server.py -q`

Expected: all tests PASS.

### Task 6: Setup Documentation and Real Smoke Proof

**Files:**
- Create: `README.md`
- Create: `scripts/smoke_test.py`

- [ ] **Step 1: Add real smoke script**

```python
import asyncio

from browser.session import SessionBridge


async def main():
    session = SessionBridge()
    try:
        opened = await session.open_url("https://example.com")
        assert opened["connected"] and opened["ready"], opened
        content = await session.get_content(max_length=500)
        assert content["url"].startswith("https://example.com"), content
        print({"opened": opened, "content_length": content["length"]})
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Document Windows setup**

README commands:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\smoke_test.py
```

Document that Playwright connects to installed Chrome over CDP, so browser downloads are not required.

- [ ] **Step 3: Document Codex MCP configuration**

Provide configuration using absolute Windows paths and stdio:

```toml
[mcp_servers.sessionbridge]
command = "C:\\Users\\roni9\\Desktop\\Curso Da Sarah\\.venv\\Scripts\\python.exe"
args = ["C:\\Users\\roni9\\Desktop\\Curso Da Sarah\\server.py"]
```

Explain restarting Codex after configuration and keeping the Chrome window open during manual interaction.

- [ ] **Step 4: Run full automated proof**

Run: `rtk python -m pytest -q`

Expected: all tests PASS with no warnings or collection errors.

- [ ] **Step 5: Run import and MCP startup proof**

Run: `rtk python -c "import server; print(server.mcp.name)"`

Expected: `SessionBridge`.

- [ ] **Step 6: Run deliberate browser smoke test**

Run: `rtk python scripts/smoke_test.py`

Expected: visible Chrome opens with `.chrome_profile`, output reports `connected: True`, and script disconnects without closing Chrome.

- [ ] **Step 7: Record material limitation**

README must state challenge detection is heuristic: an unknown login or site-specific prompt may require caller judgment from `get_current_page`; SessionBridge never solves or bypasses verification.
