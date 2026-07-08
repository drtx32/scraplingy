# Cookies Support — Design Spec

**Date:** 2026-07-08
**Status:** Approved (pending user review of written spec)
**Scope:** Add optional `cookies_file` parameter to scraplingy's CLI and MCP fetch tools, parsing a Netscape-format `cookies.txt` and forwarding to Scrapling.

## 1. Goal

Let users fetch bot-protected / login-gated pages by supplying their own cookies at the CLI or MCP call site, without scraplingy implementing its own login flow, cookie jar, or persistence.

The user is in control: they export cookies from their browser (via a standard extension like "Get cookies.txt LOCALLY"), point scraplingy at the file, and the fetch proceeds with those cookies attached. If the file is missing, malformed, or the cookies are expired, scraplingy falls back to an anonymous fetch — never crashes.

## 2. Background — Why Mimic capswriter

The user explicitly asked to imitate the cookies implementation in `D:\pythonRelated\workspace-codex\capswriter`. capswriter has **no cookies implementation of its own**: it accepts two mutually-exclusive CLI flags (`--cookies <path>` for a Netscape file, `--cookies-from-browser <name>`) and forwards them verbatim to the `yt-dlp` subprocess. Five lines of argv glue; no storage, no login, no encryption, no refresh.

We are copying capswriter's **interface philosophy** — "user brings the credentials, we just plumb them through" — not its code, because scraplingy's fetcher (Scrapling + Playwright) is structurally different from capswriter's (subprocess wrapper around `yt-dlp`). Notably, scraplingy can only support the Netscape file input — the `--cookies-from-browser` flag is not portable to scraplingy because Playwright does not read directly from a user-installed browser's cookie store without launching it as a channel.

## 3. Design Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Input format: **Netscape `cookies.txt` only** | Most portable; standard browser-extension output; matches capswriter |
| 2 | API surface: **CLI flag + MCP tool parameter** | scraplingy's existing dual entry-point; mirrors `mode`/`format`/`wait` |
| 3 | Failure behavior: **completely silent degradation** | User explicitly chose "完全静默降级 (capswriter 原版)" over the "stderr warning" alternative |
| 4 | Parser location: **new `_cookies.py` module** | Keeps `_scrapling.py` as the sole Scrapling integration point (per CLAUDE.md); easier to unit-test |
| 5 | Parser contract: **never raises; returns `None` on any failure** | All failure modes collapse to "no cookies" — the caller never needs try/except |
| 6 | Parameter name: **`cookies_file`** (not `cookies`) | Disambiguates from Scrapling's own `cookies` kwarg; signals "path to a file" |
| 7 | Storage: **none** | No disk caching, no session reuse across calls; matches capswriter |
| 8 | Three modes: **`basic` / `stealth` / `max-stealth` all supported** | Verified in Scrapling source: `AsyncFetcher.get` (curl_cffi) and `StealthyFetcher.async_fetch` (Playwright) both accept `cookies=` |

## 4. Architecture

```
MCP / CLI call
  s_fetch_page(url=..., cookies_file="/path/cookies.txt")
      │
      ▼
mcp.py / cli.py
      │  forwards cookies_file
      ▼
_fetcher.py:fetch_page_impl(..., cookies_file)
      │
      ├─ parsed = _cookies.parse_netscape_cookies(cookies_file)
      │       │ returns list[dict] | None
      │       └─ any failure → None
      │
      └─ page = await browse_url(url, mode, wait, cookies=parsed)
            │
            ▼
_scrapling.py:browse_url(..., cookies=None)
      │
      ├─ basic       → AsyncFetcher.get(url, cookies=cookies, stealthy_headers=True)
      ├─ stealth     → StealthyFetcher.async_fetch(url, cookies=cookies, headless=True, network_idle=True, ...)
      └─ max-stealth → StealthyFetcher.async_fetch(url, cookies=cookies, headless=True, block_webrtc=True, ...)
```

The same `list[dict]` is forwarded to all three modes. Scrapling handles the per-mode difference (curl_cffi accepts it as a header list, Playwright passes it to `context.add_cookies()`).

## 5. Components

### 5.1 New: `src/scraplingy/_cookies.py`

```python
"""Netscape cookies.txt parser. Returns None on any failure (silent degradation)."""
from pathlib import Path
from typing import Any

def parse_netscape_cookies(path: str | Path) -> list[dict[str, Any]] | None:
    """Parse a Netscape-format cookies file.

    Returns a list of cookie dicts compatible with both Playwright's
    context.add_cookies() and curl_cffi's cookies= kwarg, or None if the
    file is missing, unreadable, empty, or contains no parseable cookies.
    """
    p = Path(path).resolve()
    if not p.is_file():
        return None
    cookies: list[dict[str, Any]] = []
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Standard Netscape comment; #HttpOnly_ is a real cookie marker.
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
        cookies.append({
            "name": name,
            "value": value,
            "domain": domain,
            "path": path_,
            "expires": exp,
            "httpOnly": False,
            "secure": secure.upper() == "TRUE",
        })
    return cookies or None
```

### 5.2 Modified: `src/scraplingy/_scrapling.py`

- `browse_url()` signature gains `cookies: list[dict[str, Any]] | None = None`
- All three branches forward `cookies=cookies` to the underlying Scrapling call
- `_scrapling.py` does not import `_cookies` — it receives an already-parsed list

### 5.3 Modified: `src/scraplingy/_fetcher.py`

- `fetch_page_impl()` and `fetch_pattern_impl()` gain `cookies_file: str | None = None`
- Internally: `cookies = _cookies.parse_netscape_cookies(cookies_file) if cookies_file else None`
- Forward `cookies=cookies` to `browse_url(...)`

### 5.4 Modified: `src/scraplingy/mcp.py`

- `s_fetch_page` and `s_fetch_pattern` each gain an optional `cookies_file: str | None = None` parameter
- Docstring: `"Path to a Netscape-format cookies.txt file. If missing or malformed, silently proceeds without cookies."`

### 5.5 Modified: `src/scraplingy/cli.py`

- `fetch` command gains a Click option: `--cookies` (type=`click.Path(exists=False, dir_okay=False)`; default `None`)
- Forwarded to `_fetch_impl(..., cookies_file=cookies_path)`

### 5.6 Modified: `README.md` and `CLAUDE.md`

- `s_fetch_page` / `s_fetch_pattern` parameter tables gain a `cookies_file` row
- New section: "Using cookies to access login-gated content" with one example invocation
- `CLAUDE.md` env-vars / architecture notes updated to mention `cookies_file` parameter

## 6. Error Handling

| Failure mode | `_cookies.py` returns | Caller behavior |
|--------------|----------------------|-----------------|
| Path does not exist | `None` | `cookies=None` → Scrapling default (no cookies) |
| Path is a directory | `None` | Same |
| Permission denied (`read_text` raises) | `None` | Same |
| Empty file | `None` (from `cookies or None`) | Same |
| All-comment file | `None` | Same |
| Individual line < 7 fields | skip line, continue | Partial cookies (the valid ones) |
| Individual line's `expires` not parseable | `expires = -1` (session cookie) | Continue |
| File is huge / encoding errors | `errors="replace"` → continues | Best-effort |

**No exceptions escape `_cookies.py`.** No `stderr` writes. No log lines. The caller's experience of a failed cookies file is identical to not passing one at all.

## 7. Testing

Create `tests/test_cookies.py` (project's first test file) with the following cases:

- `test_parse_normal` — typical 3-cookie Netscape file → 3 dicts with correct fields
- `test_parse_http_only_prefix` — `#HttpOnly_` prefix is stripped, cookie included
- `test_parse_skips_comments` — `# Netscape HTTP Cookie File` header line ignored
- `test_parse_skips_blank_and_short_lines` — empty lines and lines with < 7 fields ignored
- `test_parse_expires_non_digit` — non-numeric `expires` → `-1` (session)
- `test_parse_secure_flag` — `TRUE` → `secure=True`, `FALSE` → `secure=False`
- `test_returns_none_for_missing_file` — nonexistent path → `None`
- `test_returns_none_for_directory` — path is a directory → `None`
- `test_returns_none_for_empty_file` — 0-byte file → `None`
- `test_returns_none_for_all_comments` — only `#` lines → `None`
- `test_no_exception_on_garbage` — random non-cookie text → `None` (not a crash)
- `test_resolves_relative_path` — `Path("cookies.txt").resolve()` works

Run with `uv run pytest tests/test_cookies.py`. ~50 lines, no fixtures beyond `tmp_path`.

## 8. Out of Scope (YAGNI)

- **`--cookies-from-browser <name>`** — capswriter has this; we don't. Playwright would require launching the user's installed browser as a channel, which adds cross-platform complexity and a security review surface. Users who want this can use Playwright directly.
- **`storage_state.json` support** — Playwright's native format. We only support Netscape. (User explicitly chose "仅 Netscape cookies.txt".)
- **Inline cookies string** — `--cookies "name1=value1; name2=value2"`. capswriter doesn't have this either. (User declined option C.)
- **Cookie persistence / session reuse across calls** — every call is stateless. (User declined options B and C; pure capswriter philosophy.)
- **Auto-detection of expired cookies** — we just forward whatever the user provides. Expired cookies produce an anonymous-looking response, same as not providing any.
- **Login flow** — we never log in on the user's behalf. The user obtains cookies in their own browser.
- **Stderr warning on file-missing** — explicit user choice for "完全静默降级".
- **CloakBrowser / CDP-specific cookie injection** — the env vars `CLOAKBROWSER_API` and `CDP_URL` already work transparently with whatever Scrapling does. No new integration needed.

## 9. File Manifest

| Status | Path | Change |
|--------|------|--------|
| NEW | `src/scraplingy/_cookies.py` | Netscape parser, ~40 lines |
| MOD  | `src/scraplingy/_scrapling.py` | `browse_url` gains `cookies` param; 3 branches forward it |
| MOD  | `src/scraplingy/_fetcher.py` | `fetch_*_impl` gain `cookies_file`; call parser; forward |
| MOD  | `src/scraplingy/mcp.py` | `s_fetch_page` / `s_fetch_pattern` gain `cookies_file` |
| MOD  | `src/scraplingy/cli.py` | `fetch` gains `--cookies` option |
| MOD  | `README.md` | API tables + new usage section |
| MOD  | `CLAUDE.md` | Architecture mention |
| NEW | `tests/test_cookies.py` | Unit tests for parser, ~50 lines |
| NEW | `docs/superpowers/specs/2026-07-08-cookies-support-design.md` | This spec |
