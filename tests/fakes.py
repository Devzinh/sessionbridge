class FakeElement:
    def __init__(self, visible: bool = True) -> None:
        self.visible = visible

    async def is_visible(self) -> bool:
        return self.visible


class FakePage:
    def __init__(
        self,
        *,
        url: str = "https://example.com",
        title: str = "Example",
        body: str = "",
        selectors: dict[str, FakeElement] | None = None,
    ) -> None:
        self.url = url
        self._title = title
        self.body = body
        self.selectors = selectors or {}
        self.closed = False

    async def title(self) -> str:
        return self._title

    async def query_selector(self, selector: str) -> FakeElement | None:
        return self.selectors.get(selector)

    async def evaluate(self, script: str) -> str:
        return self.body

    async def goto(self, url: str, **kwargs: object) -> None:
        self.url = url

    def is_closed(self) -> bool:
        return self.closed
