from typing import Dict, Any
from browser.session import get_session


async def open_browser(url: str) -> Dict[str, Any]:
    """
    Opens the Chrome browser (or uses active CDP session) and navigates to the given URL.
    Returns the initial state, indicating if manual human interaction is required.
    """
    session = get_session()
    return await session.open_url(url)


async def get_browser_status() -> Dict[str, Any]:
    """
    Returns the current status of the browser session, whether connected,
    the active URL, and if manual human interaction is required.
    """
    session = get_session()
    return await session.get_status()


async def wait_for_human(timeout_seconds: float = 120) -> Dict[str, Any]:
    """
    Pauses and monitors the browser, waiting for the human user to resolve
    any verification challenges (Cloudflare, CAPTCHA, login).
    """
    session = get_session()
    return await session.wait_for_human(timeout_seconds=timeout_seconds)


async def continue_session() -> Dict[str, Any]:
    """
    Checks the current browser state to confirm that the human verification step
    has passed and the automation can safely proceed.
    """
    session = get_session()
    status = await session.get_status()
    if status.get("manual_interaction_required"):
        state = "blocked"
    elif status.get("connected") and status.get("ready"):
        state = "ready"
    else:
        state = "unavailable"
    return {**status, "status": state}


async def get_current_page(max_length: int = 4000) -> Dict[str, Any]:
    """
    Retrieves the current page title, URL, and readable textual content.
    """
    session = get_session()
    return await session.get_content(max_length=max_length)


async def close_browser() -> Dict[str, Any]:
    """
    Disconnects the automation bridge from the browser session.
    """
    session = get_session()
    await session.close()
    return {"status": "disconnected"}
