def test_runtime_dependencies_are_importable() -> None:
    import mcp
    import playwright

    assert mcp is not None
    assert playwright is not None
