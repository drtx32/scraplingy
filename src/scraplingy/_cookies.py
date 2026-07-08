"""Netscape cookies.txt parser.

Returns None on any failure (missing file, unreadable, empty, malformed) —
callers treat None as "no cookies" and proceed with a default anonymous fetch.
"""
from pathlib import Path
from typing import Any


def parse_netscape_cookies(path: str | Path) -> list[dict[str, Any]] | None:
    """Parse a Netscape-format cookies file.

    The result is a list of cookie dicts compatible with both Playwright's
    context.add_cookies() and curl_cffi's cookies= kwarg. Returns None if the
    file is missing, unreadable, empty, or contains no parseable cookies.
    """
    try:
        p = Path(path).resolve()
    except (OSError, ValueError):
        return None
    if not p.is_file():
        return None
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    cookies: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Standard Netscape comments are skipped; #HttpOnly_ marks a real cookie.
        if line.startswith("#") and not line.startswith("#HttpOnly_"):
            continue
        if line.startswith("#HttpOnly_"):
            line = line[len("#HttpOnly_"):]
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain, _, path_, secure, expires, name, value = parts[:7]
        try:
            exp = int(expires) if expires.isdigit() else -1
        except ValueError:
            exp = -1
        cookies.append(
            {
                "name": name,
                "value": value,
                "domain": domain,
                "path": path_,
                "expires": exp,
                "httpOnly": False,
                "secure": secure.upper() == "TRUE",
            }
        )
    return cookies or None
