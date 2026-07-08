"""Unit tests for the Netscape cookies.txt parser.

These tests cover the parser's full failure surface: any error must collapse
to None (silent degradation), never raise.
"""
from pathlib import Path

from scraplingy._cookies import parse_netscape_cookies


NETSCAPE_HEADER = (
    "# Netscape HTTP Cookie File\n"
    "# https://curl.haxx.se/rfc/cookie_spec.html\n"
    "# This is a generated file! Do not edit.\n\n"
)


def test_parse_normal(tmp_path: Path) -> None:
    p = tmp_path / "cookies.txt"
    p.write_text(
        NETSCAPE_HEADER
        + ".example.com\tTRUE\t/\tFALSE\t1700000000\tsid\tabc123\n"
        + ".example.com\tTRUE\t/api\tFALSE\t0\tcsrf\ttok-en\n"
    )
    result = parse_netscape_cookies(p)
    assert result is not None
    assert len(result) == 2
    sid, csrf = result
    assert sid["name"] == "sid" and sid["value"] == "abc123"
    assert sid["domain"] == ".example.com" and sid["path"] == "/"
    assert sid["secure"] is False and sid["expires"] == 1700000000
    assert csrf["name"] == "csrf" and csrf["value"] == "tok-en"
    assert csrf["path"] == "/api" and csrf["expires"] == 0


def test_parse_http_only_prefix(tmp_path: Path) -> None:
    p = tmp_path / "cookies.txt"
    p.write_text(
        NETSCAPE_HEADER
        + "#HttpOnly_.example.com\tTRUE\t/\tFALSE\t1700000000\tsession\txyz\n"
    )
    result = parse_netscape_cookies(p)
    assert result is not None and len(result) == 1
    assert result[0]["name"] == "session" and result[0]["value"] == "xyz"


def test_parse_skips_comments(tmp_path: Path) -> None:
    p = tmp_path / "cookies.txt"
    p.write_text(
        "# This is a comment\n"
        "# Another comment\n"
        ".example.com\tTRUE\t/\tFALSE\t0\tsid\tv\n"
    )
    result = parse_netscape_cookies(p)
    assert result is not None and len(result) == 1


def test_parse_skips_blank_and_short_lines(tmp_path: Path) -> None:
    p = tmp_path / "cookies.txt"
    p.write_text("\n\nshort line\n\tshort\n.bad\n")
    p.write_text("\n\nshort line\n\tshort\n")
    result = parse_netscape_cookies(p)
    # No 7-field tab-separated line in the file
    assert result is None


def test_parse_expires_non_digit(tmp_path: Path) -> None:
    p = tmp_path / "cookies.txt"
    p.write_text(".example.com\tTRUE\t/\tFALSE\tnotanumber\tsid\tv\n")
    result = parse_netscape_cookies(p)
    assert result is not None and result[0]["expires"] == -1


def test_parse_secure_flag(tmp_path: Path) -> None:
    p = tmp_path / "cookies.txt"
    p.write_text(
        ".example.com\tTRUE\t/\tTRUE\t0\ts1\tv1\n"
        + ".example.com\tTRUE\t/\tFALSE\t0\ts2\tv2\n"
    )
    result = parse_netscape_cookies(p)
    assert result is not None
    assert result[0]["secure"] is True
    assert result[1]["secure"] is False


def test_returns_none_for_missing_file(tmp_path: Path) -> None:
    assert parse_netscape_cookies(tmp_path / "nope.txt") is None


def test_returns_none_for_directory(tmp_path: Path) -> None:
    assert parse_netscape_cookies(tmp_path) is None


def test_returns_none_for_empty_file(tmp_path: Path) -> None:
    p = tmp_path / "cookies.txt"
    p.write_text("")
    assert parse_netscape_cookies(p) is None


def test_returns_none_for_all_comments(tmp_path: Path) -> None:
    p = tmp_path / "cookies.txt"
    p.write_text(NETSCAPE_HEADER)
    assert parse_netscape_cookies(p) is None


def test_no_exception_on_garbage(tmp_path: Path) -> None:
    p = tmp_path / "cookies.txt"
    p.write_bytes(b"\x00\x01\x02\x03random binary\xff\xfe")
    # Should not raise; returns None (no parseable lines)
    assert parse_netscape_cookies(p) is None


def test_resolves_relative_path(tmp_path: Path, monkeypatch) -> None:
    p = tmp_path / "cookies.txt"
    p.write_text(".example.com\tTRUE\t/\tFALSE\t0\tsid\tv\n")
    monkeypatch.chdir(tmp_path)
    # Relative path; resolve() should find it
    result = parse_netscape_cookies("cookies.txt")
    assert result is not None and len(result) == 1
