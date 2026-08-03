"""Regression tests for the fetch_pattern_impl pipeline.

Focus: parity with fetch_page_impl on the documented ``max_length=0`` default
("no limit"). Without the fix the default silently truncates the matched
content to an empty string and reports ``is_truncated=true``.
"""
from types import SimpleNamespace

import pytest

from scraplingy import _fetcher as fetcher_mod
from scraplingy._fetcher import fetch_pattern_impl


SAMPLE_HTML = (
    "<html><body>"
    "<p>Agent tooling matters for Agent workflows.</p>"
    "<p>Some other prose about markets and weather.</p>"
    "<p>Closing line referencing Agent again.</p>"
    "</body></html>"
)


@pytest.fixture
def fake_browse_url(monkeypatch):
    captured: dict = {}

    async def _fake(url: str, mode: str, wait: int = 2000, cookies=None):  # noqa: ARG001
        captured["url"] = url
        captured["mode"] = mode
        return SimpleNamespace(html_content=SAMPLE_HTML)

    monkeypatch.setattr(fetcher_mod, "browse_url", _fake)
    return captured


def test_fetch_pattern_max_length_zero_returns_full_matches(fake_browse_url) -> None:
    """max_length=0 must mean "no limit", mirroring fetch_page_impl."""
    import asyncio

    out = asyncio.run(
        fetch_pattern_impl(
            url="https://example.com",
            search_pattern="Agent",
            mode="basic",
            format="markdown",
            max_length=0,  # the default callers hit
            context_chars=50,
            wait=1000,
        )
    )

    # caller's url and mode were honored
    assert fake_browse_url["url"] == "https://example.com"
    assert fake_browse_url["mode"] == "basic"

    # body must not be silently empty when matches exist
    head, _, body = out.partition("\n\n")
    assert body, f"expected matched content under max_length=0, got: {head!r}"
    assert "Agent" in body

    # metadata must report the matches and NOT mark them truncated
    import json as _json

    meta = _json.loads(head.removeprefix("METADATA: "))
    assert meta["match_count"] == 3
    assert meta["is_truncated"] is False
    assert meta["retrieved_length"] > 0
