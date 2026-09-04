import asyncio
import sys
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from browser.session import SessionBridge


async def main(session_factory: Callable[[], SessionBridge] = SessionBridge) -> None:
    session = session_factory()
    try:
        opened = await session.open_url("https://example.com")
        if not opened.get("connected") or not opened.get("ready"):
            raise AssertionError(
                "Browser did not reach the required connected and ready state"
            )

        content = await session.get_content(max_length=500)
        url = content.get("url", "")
        parsed_url = urlsplit(url)
        if (
            parsed_url.scheme != "https"
            or parsed_url.hostname != "example.com"
            or parsed_url.username is not None
            or parsed_url.password is not None
        ):
            raise AssertionError("Browser did not return the expected example.com URL")

        print(
            {
                "connected": opened["connected"],
                "ready": opened["ready"],
                "url": url,
                "content_length": content.get("length", 0),
            }
        )
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())
