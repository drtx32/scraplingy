from scraplingy import _scrapling


def test_basic_converts_playwright_cookies_for_curl_cffi(monkeypatch):
    captured = {}

    class FakeFetcher:
        @staticmethod
        async def get(url, **kwargs):
            captured["url"] = url
            captured.update(kwargs)
            return object()

    monkeypatch.setattr(
        "scrapling.fetchers.requests.AsyncFetcher", FakeFetcher
    )

    cookies = [
        {
            "name": "sid",
            "value": "abc",
            "domain": ".example.com",
            "path": "/",
        }
    ]

    async def run():
        return await _scrapling.browse_url(
            "https://example.com", "basic", cookies=cookies
        )

    import asyncio

    asyncio.run(run())
    assert captured["cookies"] == [("sid", "abc")]
    assert captured["stealthy_headers"] is False
