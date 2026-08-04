from contextlib import redirect_stdout, redirect_stderr
from os import devnull
from os import environ
from typing import Any

try:
    from aiohttp import ClientSession
except ImportError:
    ClientSession = None

try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None


_STEALTH_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/145.0.0.0 Safari/537.36"
)


def _load_stealth_fetcher():
    """Import Scrapling's browser fetcher without fatal header generation."""
    from browserforge.headers.generator import HeaderGenerator

    original_generate = HeaderGenerator.generate

    def generate_with_fallback(generator, *args, **kwargs):
        try:
            return original_generate(generator, *args, **kwargs)
        except ValueError as exc:
            if "No headers based on this input can be generated" not in str(exc):
                raise
            return {"User-Agent": _STEALTH_USER_AGENT}

    HeaderGenerator.generate = generate_with_fallback
    try:
        from scrapling.fetchers.stealth_chrome import StealthyFetcher
    finally:
        HeaderGenerator.generate = original_generate
    return StealthyFetcher


async def _resolve_cloakbrowser_cdp(api_url: str) -> str | None:
    """Resolve CDP URL from CloakBrowser HTTP API.

    CloakBrowser exposes a CDP WebSocket at /devtools/browser/<id> which is
    returned by the /json/version endpoint. This function fetches that URL
    and returns it directly so Scrapling can connect over CDP.
    """
    if ClientSession is None:
        return None
    try:
        base = api_url.rstrip("/")
        async with ClientSession() as session:
            async with session.get(f"{base}/json/version", timeout=5.0) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                return data.get("webSocketDebuggerUrl")
    except Exception:
        return None


async def _reset_singleton_browser_tab(cdp_url: str | None) -> bool:
    """Best-effort reset for a shared CDP browser session.

    If the browser looks singleton-sized (one context, one page), keep the
    tab alive and navigate it to about:blank so other agents do not inherit the
    last task's page state. Local, non-CDP Playwright launches are left alone.
    """
    if not cdp_url or async_playwright is None:
        return False

    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.connect_over_cdp(
                endpoint_url=cdp_url
            )
            contexts = list(browser.contexts)
            if len(contexts) != 1:
                return False

            pages = list(contexts[0].pages)
            if len(pages) != 1:
                return False

            page = pages[0]
            if page.is_closed() or page.url == "about:blank":
                return False

            await page.goto("about:blank", wait_until="commit", timeout=5000)
            return True
    except Exception:
        return False


async def browse_url(
    url: str,
    mode: str,
    wait: int = 2000,
    cookies: list[dict] | None = None,
) -> Any:
    cdp_url = environ.get("CDP_URL")

    if not cdp_url and environ.get("CLOAKBROWSER_API"):
        cdp_url = await _resolve_cloakbrowser_cdp(environ["CLOAKBROWSER_API"])

    with open(devnull, "w") as nullfd, redirect_stdout(nullfd), redirect_stderr(nullfd):
        # Import scrapling fetchers inside this block and inside each mode
        # branch so that browsers / headers subsystems are only initialised
        # for the branch that actually needs them. Importing either
        # ``AsyncFetcher`` or ``StealthyFetcher`` transitively pulls in
        # ``scrapling.engines.toolbelt.fingerprints``, which calls
        # ``browserforge`` at module load time. On some platforms that call
        # fails with ``No headers based on this input can be generated``
        # before the basic-mode code path runs; deferring the import keeps
        # callers that only ever use ``basic`` from paying that cost.
        if mode == "basic":
            from scrapling.fetchers.requests import AsyncFetcher

            # curl_cffi's ``cookies`` parameter accepts a mapping or an
            # iterable of ``(name, value)`` pairs.  The Netscape parser
            # returns Playwright-compatible cookie dictionaries because the
            # stealth path needs domain/path/expiry metadata.  Passing those
            # dictionaries through directly makes curl_cffi unpack each dict
            # as an iterable and fail with ``too many values to unpack``.
            curl_cookies = (
                [(cookie["name"], cookie["value"]) for cookie in cookies]
                if cookies
                else None
            )
            return await AsyncFetcher.get(
                url, stealthy_headers=False, cookies=curl_cookies
            )

        try:
            StealthyFetcher = None
            if mode == "stealth":
                StealthyFetcher = _load_stealth_fetcher()

                return await StealthyFetcher.async_fetch(
                    url,
                    headless=True,
                    network_idle=True,
                    cdp_url=cdp_url,
                    wait=wait,
                    cookies=cookies,
                    useragent=_STEALTH_USER_AGENT,
                )
            elif mode == "max-stealth":
                StealthyFetcher = _load_stealth_fetcher()

                return await StealthyFetcher.async_fetch(
                    url,
                    headless=True,
                    block_webrtc=True,
                    network_idle=True,
                    disable_resources=False,
                    block_images=False,
                    cdp_url=cdp_url,
                    wait=wait,
                    cookies=cookies,
                    useragent=_STEALTH_USER_AGENT,
                )
            else:
                raise ValueError(f"Unknown mode: {mode}")
        finally:
            if mode in {"stealth", "max-stealth"} and cdp_url:
                await _reset_singleton_browser_tab(cdp_url)
