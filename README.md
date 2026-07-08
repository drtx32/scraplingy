# scraplingy

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![PyPI version](https://img.shields.io/pypi/v/scraplingy.svg)](https://pypi.org/project/scraplingy/)

Scrapling + CloakBrowser integration. A CLI and MCP server for fetching bot-protected websites.

Uses Scrapling (patchright + curl-cffi) to bypass anti-automation measures, returning clean HTML or Markdown. Supports direct browser connection via CloakBrowser for enhanced stealth.

> Optimized for low-volume retrieval of documentation and reference materials. Not designed for high-volume scraping or data harvesting.

**Requirements**: Python 3.10+, [uv](https://github.com/astral-sh/uv)

## Installation

```bash
# Install via uv
uv tool install scraplingy

# Install browser binaries (required once)
uvx --from scraplingy scrapling install
```

Or install from source:

```bash
git clone https://github.com/drtx32/scraplingy.git
cd scraplingy
uv sync
uvx --from . scrapling install
```

## CLI Usage

```bash
# Fetch a URL as markdown (default)
scraplingy fetch "https://example.com"

# Fetch as HTML with stealth mode
scraplingy fetch "https://example.com" --mode stealth --format html

# Fetch with custom wait time for JS rendering
scraplingy fetch "https://example.com" --wait 3000

# Max content length (0 = no limit)
scraplingy fetch "https://example.com" --max-length 50000
```

### Fetch Modes

- **basic** — fast (1-2s), works for most sites
- **stealth** — moderate (3-8s), headless Chromium with network idle detection
- **max-stealth** — thorough (10s+), full browser fingerprint spoofing

## MCP Server

Run as an MCP server for integration with Claude Desktop or other MCP clients:

```bash
scraplingy mcp
```

### Claude Desktop Configuration

Add to your Claude Desktop config:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "scraplingy": {
      "command": "uvx",
      "args": ["scraplingy"]
    }
  }
}
```

### MCP Tools

Two tools are available via the MCP server:

#### `s_fetch_page`

Fetches a complete web page with pagination support.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | string | required | Web URL to fetch (http/https only) |
| `mode` | string | "basic" | Fetching mode (basic, stealth, or max-stealth) |
| `format` | string | "markdown" | Output format (html or markdown) |
| `max_length` | int | 0 | Max characters to return (0 = no limit) |
| `start_index` | int | 0 | Start output at this character index (for pagination) |
| `wait` | int | 2000 | Milliseconds to wait after page load for JS rendering |

Returns: `METADATA: {json}\n\n[content]`

#### `s_fetch_pattern`

Extracts content matching regex patterns from web pages.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | string | required | Web URL to fetch (http/https only) |
| `search_pattern` | string | required | Regular expression pattern to search for |
| `mode` | string | "basic" | Fetching mode (basic, stealth, or max-stealth) |
| `format` | string | "markdown" | Output format (html or markdown) |
| `max_length` | int | 0 | Max characters to return (0 = no limit) |
| `context_chars` | int | 200 | Characters to include before and after each match |
| `wait` | int | 2000 | Milliseconds to wait after page load for JS rendering |

Returns: `METADATA: {json}\n\n[matched content delimited with ॥๛॥]`

## CloakBrowser Integration

For enhanced stealth, connect to a CloakBrowser instance:

```bash
# Set API URL
export CLOAKBROWSER_API="http://localhost:8080"

# Or set CDP URL directly
export CDP_URL="ws://localhost:9222"

# Then run
scraplingy fetch "https://example.com"
```

## Claude Code Skill

A skill is available for Claude Code that provides a `/s-fetch` slash command. See [CLAUDE.md](./CLAUDE.md) for setup instructions.

## License

Apache 2.0
