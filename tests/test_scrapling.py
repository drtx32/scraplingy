import asyncio
from types import SimpleNamespace

import scrapling.fetchers.requests as scrapling_requests
import scrapling.fetchers.stealth_chrome as scrapling_stealth
import scraplingy._scrapling as scrapling_mod


class _FakePage:
    def __init__(self, url: str = "https://example.com", closed: bool = False):
        self.url = url
        self._closed = closed
        self.goto_calls: list[tuple[str, dict]] = []

    def is_closed(self) -> bool:
        return self._closed

    async def goto(self, url: str, **kwargs) -> None:
        self.goto_calls.append((url, kwargs))
        self.url = url


class _FakeContext:
    def __init__(self, pages: list[_FakePage]):
        self.pages = pages


class _FakeBrowser:
    def __init__(self, contexts: list[_FakeContext]):
        self.contexts = contexts


class _FakeChromium:
    def __init__(self, browser: _FakeBrowser):
        self.browser = browser
        self.endpoint_url = None

    async def connect_over_cdp(self, endpoint_url: str):
        self.endpoint_url = endpoint_url
        return self.browser


class _FakePlaywright:
    def __init__(self, browser: _FakeBrowser):
        self.chromium = _FakeChromium(browser)


class _FakePlaywrightContext:
    def __init__(self, browser: _FakeBrowser):
        self.browser = browser

    async def __aenter__(self):
        return _FakePlaywright(self.browser)

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_reset_singleton_browser_tab_navigates_about_blank(monkeypatch) -> None:
    page = _FakePage(url="https://example.com")
    browser = _FakeBrowser([_FakeContext([page])])
    monkeypatch.setattr(
        scrapling_mod,
        "async_playwright",
        lambda: _FakePlaywrightContext(browser),
    )

    result = asyncio.run(
        scrapling_mod._reset_singleton_browser_tab(
            "ws://example/devtools/browser/1"
        )
    )

    assert result is True
    assert page.goto_calls == [
        (
            "about:blank",
            {"wait_until": "commit", "timeout": 5000},
        )
    ]


def test_reset_singleton_browser_tab_skips_multi_tab_browser(monkeypatch) -> None:
    first = _FakePage(url="https://example.com")
    second = _FakePage(url="https://example.org")
    browser = _FakeBrowser([_FakeContext([first, second])])
    monkeypatch.setattr(
        scrapling_mod,
        "async_playwright",
        lambda: _FakePlaywrightContext(browser),
    )

    result = asyncio.run(
        scrapling_mod._reset_singleton_browser_tab(
            "ws://example/devtools/browser/1"
        )
    )

    assert result is False
    assert first.goto_calls == []
    assert second.goto_calls == []


def test_browse_url_resets_resolved_cloakbrowser_tab(monkeypatch) -> None:
    cleanup = []
    seen_kwargs = {}

    async def fake_cleanup(cdp_url: str | None) -> bool:
        cleanup.append(cdp_url)
        return True

    async def fake_resolve(api_url: str) -> str | None:
        assert api_url == "https://cloakbrowser-api.example"
        return "ws://example/devtools/browser/1"

    async def fake_fetch(url: str, **kwargs):
        seen_kwargs.update(kwargs)
        return SimpleNamespace(html_content="<html><body>ok</body></html>")

    monkeypatch.setattr(scrapling_mod, "_resolve_cloakbrowser_cdp", fake_resolve)
    monkeypatch.setattr(scrapling_mod, "_reset_singleton_browser_tab", fake_cleanup)
    monkeypatch.setenv("CLOAKBROWSER_API", "https://cloakbrowser-api.example")
    monkeypatch.setattr(
        scrapling_stealth,
        "StealthyFetcher",
        SimpleNamespace(async_fetch=fake_fetch),
    )
    monkeypatch.setattr(
        scrapling_requests,
        "AsyncFetcher",
        SimpleNamespace(get=fake_fetch),
    )

    result = asyncio.run(
        scrapling_mod.browse_url(
            "https://example.com",
            "stealth",
            wait=1000,
        )
    )

    assert result.html_content == "<html><body>ok</body></html>"
    assert cleanup == ["ws://example/devtools/browser/1"]
    assert seen_kwargs["useragent"] == "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
    assert seen_kwargs["network_idle"] is True


def test_browse_url_does_not_cleanup_basic_mode(monkeypatch) -> None:
    cleanup = []
    seen_kwargs = {}

    async def fake_cleanup(cdp_url: str | None) -> bool:
        cleanup.append(cdp_url)
        return True

    async def fake_fetch(url: str, **kwargs):
        seen_kwargs.update(kwargs)
        return SimpleNamespace(html_content="<html><body>ok</body></html>")

    monkeypatch.setattr(scrapling_mod, "_reset_singleton_browser_tab", fake_cleanup)
    monkeypatch.setattr(
        scrapling_requests,
        "AsyncFetcher",
        SimpleNamespace(get=fake_fetch),
    )

    result = asyncio.run(
        scrapling_mod.browse_url(
            "https://example.com",
            "basic",
            wait=1000,
        )
    )

    assert result.html_content == "<html><body>ok</body></html>"
    assert cleanup == []
    assert seen_kwargs["stealthy_headers"] is False


def test_basic_mode_does_not_import_stealth_chrome(monkeypatch) -> None:
    """basic-mode fetches must not touch scrapling.fetchers.stealth_chrome.

    Importing the stealth module pulls in browserforge-driven header
    generation on some platforms and fails with
    "No headers based on this input can be generated" before our
    basic-mode code path even runs. Defer it strictly to the branches
    that need it.
    """
    import sys

    # Make sure the stealth submodule is not loaded yet so we can observe
    # the import side effect of a basic-mode call.
    monkeypatch.delitem(sys.modules, "scrapling.fetchers.stealth_chrome", raising=False)

    seen_kwargs = {}

    async def fake_fetch(url: str, **kwargs):
        seen_kwargs.update(kwargs)
        return SimpleNamespace(html_content="<html><body>ok</body></html>")

    monkeypatch.setattr(
        scrapling_requests,
        "AsyncFetcher",
        SimpleNamespace(get=fake_fetch),
    )

    asyncio.run(
        scrapling_mod.browse_url("https://example.com", "basic", wait=1000)
    )

    assert seen_kwargs["stealthy_headers"] is False
    assert "scrapling.fetchers.stealth_chrome" not in sys.modules

