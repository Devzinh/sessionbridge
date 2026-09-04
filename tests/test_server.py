import pytest

from server import mcp


@pytest.mark.asyncio
async def test_server_registers_only_browser_session_tools():
    tools = await mcp.list_tools()

    assert {tool.name for tool in tools} == {
        "open_browser",
        "get_browser_status",
        "wait_for_human",
        "continue_session",
        "get_current_page",
        "close_browser",
    }
