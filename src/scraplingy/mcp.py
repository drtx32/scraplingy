from os import environ
from logging import getLogger
from traceback import format_exc

from mcp.server.fastmcp import FastMCP

from scraplingy._fetcher import (
    fetch_page_impl,
    fetch_pattern_impl,
)

mcp = FastMCP("scraplingy")

# Configure Playwright to skip browser download when using external CDP
_has_external = bool(environ.get("CDP_URL") or environ.get("CLOAKBROWSER_API"))
if _has_external:
    environ.setdefault("PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD", "1")
    environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")


@mcp.tool()
async def s_fetch_page(
    url: str,
    mode: str = "basic",
    format: str = "markdown",
    max_length: int = 0,
    start_index: int = 0,
    wait: int = 2000,
) -> str:
    """Fetches a complete web page with pagination support. Retrieves content from websites with bot-detection avoidance. For best performance, start with 'basic' mode (fastest), then only escalate to 'stealth' or 'max-stealth' modes if basic mode fails. Content is returned as 'METADATA: {json}\\n\\n[content]' where metadata includes length information and truncation status.

    Args:
        url: Web URL to fetch (http/https only)
        mode: Fetching mode (basic, stealth, or max-stealth)
        format: Output format (html or markdown)
        max_length: Maximum number of characters to return (0 = no limit)
        start_index: On return output starting at this character index, useful if a previous fetch was truncated and more content is required.
        wait: Milliseconds to wait after page load for JS rendering (default: 2000)
    """
    try:
        result = await fetch_page_impl(url, mode, format, max_length, start_index, wait=wait)
        return result
    except Exception as e:
        logger = getLogger("scraplingy")
        logger.error("DETAILED ERROR IN s_fetch_page: %s", str(e))
        logger.error("TRACEBACK: %s", format_exc())
        raise


@mcp.tool()
async def s_fetch_pattern(
    url: str,
    search_pattern: str,
    mode: str = "basic",
    format: str = "markdown",
    max_length: int = 0,
    context_chars: int = 200,
    wait: int = 2000,
) -> str:
    """Extracts content matching regex patterns from web pages. Retrieves specific content from websites with bot-detection avoidance. For best performance, start with 'basic' mode (fastest), then only escalate to 'stealth' or 'max-stealth' modes if basic mode fails. Returns matched content as 'METADATA: {json}\\n\\n[content]' where metadata includes match statistics and truncation information. Each matched content chunk is delimited with '॥๛॥' and prefixed with '[Position: start-end]' indicating its byte position in the original document, allowing targeted follow-up requests with s-fetch-page using specific start_index values.

    Args:
        url: Web URL to fetch (http/https only)
        search_pattern: Regular expression pattern to search for in the content
        mode: Fetching mode (basic, stealth, or max-stealth)
        format: Output format (html or markdown)
        max_length: Maximum number of characters to return (0 = no limit)
        context_chars: Number of characters to include before and after each match
        wait: Milliseconds to wait after page load for JS rendering (default: 2000)
    """
    try:
        result = await fetch_pattern_impl(
            url, search_pattern, mode, format, max_length, context_chars, wait=wait
        )
        return result
    except Exception as e:
        logger = getLogger("scraplingy")
        logger.error("DETAILED ERROR IN s_fetch_pattern: %s", str(e))
        logger.error("TRACEBACK: %s", format_exc())
        raise


def run_server():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_server()
