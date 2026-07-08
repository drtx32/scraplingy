# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What it does

scraplingy is a Scrapling + CloakBrowser integration — a CLI and MCP server for fetching bot-protected websites. It exposes two tools (`s_fetch_page`, `s_fetch_pattern`) via FastMCP over stdio, using Scrapling (patchright + playwright + curl-cffi) to bypass anti-automation measures and returning HTML or Markdown.

It also ships as a Claude Code skill with a `/s-fetch` slash command that invokes scraplingy directly via Bash.

## Commands

```bash
# Install dependencies
uv sync

# Install browser binaries (required once; large download)
uvx --from scraplingy scrapling install

# Run MCP server
uv run scraplingy mcp

# Build
uv build
```

No test suite exists in this project.

## Skill structure

```
skills/s-fetch/SKILL.md              # /s-fetch — fetches URLs via scraplingy
skills/s-fetch/references/install.md # one-time install steps, loaded only on miss
```

Install: clone the repo and copy `skills/s-fetch` into `~/.claude/skills/` (see README for commands).

`/s-fetch` uses `$(uv tool dir)/scraplingy/bin/scraplingy -`. The first time it runs on a machine without the tool, SKILL.md's Setup section directs Claude to `references/install.md`, which is read on demand so it doesn't sit in context once the tool is present.

## Architecture

Request flow: `mcp.py` (FastMCP tool definitions) → `_fetcher.py` (content pipeline) → `_scrapling.py` (Scrapling dispatch) → returns `html_content`.

**`_scrapling.py`** — sole integration point with Scrapling. Maps the three fetch modes:
- `basic` — `AsyncFetcher.get` with stealthy headers (fastest, ~1-2s)
- `stealth` — `StealthyFetcher.async_fetch` headless+network_idle (~3-8s)
- `max-stealth` — same but with WebRTC blocked and resources/images not blocked (10s+)

Scrapling import is deferred inside `browse_url` with stdout redirected to `/dev/null` to suppress Scrapling's noisy startup output. `browse_url` accepts a `cookies=` list[dict] that is forwarded to all three modes (None means anonymous fetch).

**`_cookies.py`** — Netscape `cookies.txt` parser. Pure function `parse_netscape_cookies(path) -> list[dict] | None`. Never raises: any failure (missing file, OS error, no parseable lines) returns None, and the caller treats None as "no cookies".

**`_fetcher.py`** — content pipeline: calls `browse_url`, optionally converts HTML→Markdown via `_markdownify.py`, applies pagination (`start_index`/`max_length`) or regex pattern extraction, and wraps everything in `METADATA: {json}\n\n[content]`. The metadata JSON includes `total_length`, `retrieved_length`, `is_truncated`, `percent_retrieved`, and optionally `start_index` / `match_count`. Both `fetch_page_impl` and `fetch_pattern_impl` accept a `cookies_file: str | None` parameter; they parse it via `_cookies.parse_netscape_cookies` and forward the result to `browse_url`.

Pattern extraction (`_search_content`) compiles the regex, merges overlapping context windows around matches, and delimits sections with `॥๛॥` followed by `[Position: start-end]` so callers can issue targeted follow-up `s_fetch_page` requests with specific `start_index` values.

**`_markdownify.py`** — `_CustomMarkdownify` subclass adapted from Microsoft markitdown. Strips `<script>`/`<style>` via BeautifulSoup before conversion, fixes heading newlines, URL-encodes link hrefs, and truncates `data:` image sources.

Entry point: `scraplingy` CLI → `scraplingy.cli:cli` → `scraplingy.mcp:run_server` → `mcp.run(transport="stdio")`.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `CLOAKBROWSER_API` | CloakBrowser HTTP API URL (e.g. `http://localhost:8080`) |
| `CDP_URL` | Direct CDP WebSocket URL (overrides `CLOAKBROWSER_API`) |
| `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD` | Set to `1` when using external CDP |
| `PLAYWRIGHT_BROWSERS_PATH` | Set to `0` when using external CDP |
