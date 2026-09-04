"""
SessionBridge MCP Server
Provides human-in-the-loop browser automation with persistent CDP sessions.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.fastmcp import FastMCP
from tools.browser import (
    open_browser as tool_open_browser,
    get_browser_status as tool_get_browser_status,
    wait_for_human as tool_wait_for_human,
    continue_session as tool_continue_session,
    get_current_page as tool_get_current_page,
    close_browser as tool_close_browser,
)
mcp = FastMCP(
    "SessionBridge",
    instructions=(
        "MCP server for human-in-the-loop browser automation with persistent browser sessions and CDP handoff. "
        "Use open_browser to navigate. If manual_interaction_required is true (e.g. Cloudflare, CAPTCHA, login), "
        "instruct the user to solve it or call wait_for_human/continue_session to resume automation."
    ),
)


@mcp.tool()
async def open_browser(url: str) -> dict:
    """
    Opens the Chrome browser via CDP and navigates to the given URL.
    Returns the initial state and indicates if manual interaction (Cloudflare, CAPTCHA, login) is needed.
    """
    return await tool_open_browser(url)


@mcp.tool()
async def get_browser_status() -> dict:
    """
    Checks the current browser status.
    Returns connection state, active URL, page title, and whether manual interaction is required.
    """
    return await tool_get_browser_status()


@mcp.tool()
async def wait_for_human(timeout_seconds: float = 120) -> dict:
    """
    Waits actively for the human user to resolve a verification challenge (Cloudflare, CAPTCHA, login).
    Polls the page state until the challenge clears or timeout occurs.
    """
    return await tool_wait_for_human(timeout_seconds=timeout_seconds)


@mcp.tool()
async def continue_session() -> dict:
    """
    Re-checks the page state to confirm that the manual verification has passed
    and automation can safely proceed.
    """
    return await tool_continue_session()


@mcp.tool()
async def get_current_page(max_length: int = 4000) -> dict:
    """
    Extracts the current page URL, title, and readable text content for the AI agent to analyze.
    """
    return await tool_get_current_page(max_length=max_length)


@mcp.tool()
async def close_browser() -> dict:
    """
    Disconnects the automation session from Chrome.
    """
    return await tool_close_browser()


if __name__ == "__main__":
    # Runs standard stdio transport for MCP clients (Claude Desktop, Cline, etc.)
    mcp.run()
