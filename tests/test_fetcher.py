"""Unit tests for the HTML→markdown conversion pipeline.

Focus: defensive stripping at the input boundary, since upstream HTML from
real-world servers (x.com in particular) sometimes contains NUL-byte padding
that would otherwise leak into the markdown output as leading garbage.
"""
from scraplingy._fetcher import _html_to_markdown


def test_html_to_markdown_strips_leading_nul_padding() -> None:
    """The exact symptom: ~2KB of NUL bytes prepended to a real page."""
    # Simulate what x.com's no-JS shell returns: a giant NUL block then a
    # minimal HTML doc.
    nul_pad = "\x00" * 2377
    html = nul_pad + "<html><body><h1>Hi</h1><p>content</p></body></html>"
    out = _html_to_markdown(html)
    assert "\x00" not in out
    assert "Hi" in out
    assert "content" in out


def test_html_to_markdown_strips_scattered_nuls() -> None:
    """NUL bytes scattered through the HTML (not just leading)."""
    html = "<p>before\x00\x00\x00after</p>"
    out = _html_to_markdown(html)
    assert "\x00" not in out
    assert "beforeafter" in out


def test_html_to_markdown_normal_html_unchanged() -> None:
    """No-NUL input: output should contain the expected text."""
    html = "<html><body><h1>Title</h1><p>Paragraph.</p></body></html>"
    out = _html_to_markdown(html)
    assert "\x00" not in out
    assert "Title" in out
    assert "Paragraph." in out
