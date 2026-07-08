import asyncio
import json
import sys
from os import environ

import click

# Force UTF-8 output on Windows to avoid encoding errors
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def _configure_no_download():
    """If using CloakBrowser/external CDP, skip Playwright chromium download."""
    has_external = bool(environ.get("CDP_URL") or environ.get("CLOAKBROWSER_API"))
    if has_external:
        environ.setdefault("PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD", "1")
        environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")


@click.group()
def cli():
    """Scraplingy — Scrapling + CloakBrowser integration.

    Supports direct URL fetching and MCP server mode.
    Set CLOAKBROWSER_API or CDP_URL to connect to CloakBrowser.
    """
    _configure_no_download()


@cli.command()
@click.argument("url")
@click.option(
    "--mode",
    type=click.Choice(["basic", "stealth", "max-stealth"]),
    default="stealth",
    help="Fetch mode (default: stealth)",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["html", "markdown"]),
    default="markdown",
    help="Output format (default: markdown)",
)
@click.option(
    "--max-length",
    default=0,
    type=int,
    help="Max content length (0 = no limit, default: 0)",
)
@click.option(
    "--wait",
    default=2000,
    type=int,
    help="Wait milliseconds after page load for JS rendering (default: 2000)",
)
def fetch(url, mode, fmt, max_length, wait):
    """Fetch a URL and print content to stdout.

    Example: scraplingy fetch "https://example.com" --mode stealth
    """
    asyncio.run(_fetch_impl(url, mode, fmt, max_length, wait))


async def _fetch_impl(url, mode, fmt, max_length, wait):
    # Suppress INFO logs in CLI fetch mode only (MCP keeps them)
    try:
        from loguru import logger
        logger.disable("scrapling")
    except (ImportError, TypeError):
        pass

    import logging
    logging.getLogger("scrapling").setLevel(logging.WARNING)

    from scraplingy._fetcher import fetch_page_impl

    try:
        result = await fetch_page_impl(url, mode, fmt, max_length, 0, wait=wait)
        # Strip METADATA prefix, output only content
        if result.startswith("METADATA:"):
            _, _, content = result.partition("\n\n")
            click.echo(content)
        else:
            click.echo(result)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
def mcp():
    """Run as MCP server over stdio.

    Use with Claude Desktop or other MCP clients.
    Set CLOAKBROWSER_API or CDP_URL to connect to CloakBrowser.
    """
    _configure_no_download()
    from scraplingy.mcp import run_server

    run_server()


if __name__ == "__main__":
    cli()
