# SessionBridge MVP Design

## Objective

Build a local MCP server for Codex/ChatGPT that controls a visible Chrome window through Playwright and CDP while preserving a dedicated browser profile between executions. Automation must pause when detectable manual interaction is required and continue in the same session after the user resolves it.

## Scope

The MVP exposes exactly six MCP tools:

- `open_browser(url)`
- `get_browser_status()`
- `wait_for_human(timeout_seconds)`
- `continue_session()`
- `get_current_page(max_length)`
- `close_browser()`

Clicking elements, filling inputs, arbitrary JavaScript execution, screenshots, HTTP adapters, and support for multiple simultaneous sessions are outside this MVP.

## Architecture

`server.py` owns the MCP stdio interface. Tool functions delegate to one process-wide `SessionBridge` instance. The session coordinates three browser components:

- `browser/launcher.py` locates and starts a visible Chromium-based browser with remote debugging bound to `127.0.0.1:9222` and a dedicated persistent profile.
- `browser/cdp.py` manages the Playwright lifecycle and CDP connection without owning or terminating the browser process.
- `browser/state.py` inspects the active page and classifies it as ready or requiring manual interaction.

Browser code remains independent from any specific AI client. Codex/ChatGPT interacts only through MCP tools.

## State Contract

Status-producing operations return a consistent payload containing:

- `connected`: whether the browser session is available.
- `url`: current page URL, or an empty string when unavailable.
- `title`: current page title, or an empty string when unavailable.
- `manual_interaction_required`: whether a known challenge blocks automation.
- `ready`: whether automation may continue.
- `reason`: concise state or error explanation.

`connected` and `ready` are false on connection or page-inspection failure. A detected CAPTCHA, Cloudflare challenge, or recognizable human-verification prompt sets `manual_interaction_required` to true and `ready` to false. A normal reachable page sets `manual_interaction_required` to false and `ready` to true.

## Workflow

1. `open_browser` accepts only absolute `http` or `https` URLs.
2. SessionBridge starts Chrome when no CDP endpoint is available, otherwise reuses the existing dedicated session.
3. Playwright connects over CDP, selects an active page, and navigates to the URL.
4. Page state is inspected and returned to the MCP client.
5. If manual interaction is required, the user resolves it in the visible browser.
6. `wait_for_human` polls until the state becomes ready or the timeout expires. `continue_session` performs the same state check once.
7. `get_current_page` returns URL, title, and readable page text truncated to the requested limit.
8. `close_browser` disconnects Playwright but leaves Chrome running, preserving cookies, login state, and open tabs.

## Error Handling and Security

- Invalid URLs fail before Chrome launches.
- Browser discovery, startup, CDP connection, navigation, inspection, and timeout failures return explicit errors or normalized unavailable states.
- Expected navigation timeouts may still return inspected page state, but other navigation failures remain visible to the caller.
- CDP listens only on the loopback interface.
- A dedicated profile prevents interference with the user's primary Chrome profile.
- The server detects challenges and supports human handoff; it does not solve, bypass, or evade CAPTCHA or anti-bot controls.
- Arbitrary script execution is not exposed.

## Testing

Automated tests cover URL validation, challenge detection, normal and disconnected states, continuation behavior, timeout behavior, content truncation, and disconnect semantics. Browser dependencies are replaced at component boundaries so unit tests do not launch Chrome.

A local smoke test verifies that the installed server can start, launch or reuse the dedicated Chrome instance, navigate to a safe page, report status, return bounded content, and disconnect without terminating Chrome.

## Deliverables

- Minimal Python package structure using current project layout.
- Declared runtime and test dependencies.
- Six-tool MCP stdio server.
- Automated test suite.
- Setup and Codex/ChatGPT MCP configuration instructions for Windows.
- Local automated tests and documented smoke-test result.

## Success Criteria

The MVP is complete when all automated tests pass and a local smoke test demonstrates the full open, inspect, optional human-wait, continue, read, and disconnect lifecycle using the same visible Chrome profile.
