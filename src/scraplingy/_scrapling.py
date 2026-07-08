from contextlib import redirect_stdout, redirect_stderr
from os import devnull
from os import environ
from typing import Any

try:
    from aiohttp import ClientSession
except ImportError:
    ClientSession = None


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


async def browse_url(url: str, mode: str, wait: int = 2000) -> Any:
    cdp_url = environ.get("CDP_URL")

    if not cdp_url and environ.get("CLOAKBROWSER_API"):
        cdp_url = await _resolve_cloakbrowser_cdp(environ["CLOAKBROWSER_API"])

    with open(devnull, "w") as nullfd, redirect_stdout(nullfd), redirect_stderr(nullfd):
        from scrapling.fetchers import AsyncFetcher, StealthyFetcher

        if mode == "basic":
            return await AsyncFetcher.get(url, stealthy_headers=True)
        elif mode == "stealth":
            return await StealthyFetcher.async_fetch(
                url, headless=True, network_idle=True, cdp_url=cdp_url, wait=wait
            )
        elif mode == "max-stealth":
            return await StealthyFetcher.async_fetch(
                url,
                headless=True,
                block_webrtc=True,
                network_idle=True,
                disable_resources=False,
                block_images=False,
                cdp_url=cdp_url,
                wait=wait,
            )
        else:
            raise ValueError(f"Unknown mode: {mode}")
