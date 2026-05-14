import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that hit real YouTube",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-integration"):
        return
    skip_integration = pytest.mark.skip(reason="need --run-integration to run")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


@pytest.fixture(autouse=True)
def _isolate_cache():
    """Clear the global ytdlp_client cache between tests so mocks don't leak."""
    try:
        from ytdlp_client import _cache_clear
    except ImportError:
        yield
        return
    _cache_clear()
    yield
    _cache_clear()
