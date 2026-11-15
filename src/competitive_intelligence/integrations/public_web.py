"""Optional live adapter: fetch *publicly accessible* product pages you configured.

Status: implemented and unit-tested against simulated HTTP responses
(tests/test_tools.py). It has not been validated against real retail sites,
and it will not work on every site — many pages render prices with JavaScript,
block automated clients, or forbid scraping in their terms.

Safeguards built in:
* Only URLs listed explicitly in `live-sources.json` are fetched (no crawling).
* robots.txt is checked for every URL; disallowed or unreadable robots → no fetch.
* One request per host per `CI_LIVE_MIN_INTERVAL_SECONDS`, with a timeout.
* No cookies, logins, CAPTCHA solving, or anti-bot evasion. A 401/403/429 or a
  page that looks like a login/CAPTCHA wall is reported as unavailable.
* Parsing reuses `page_parser.parse_product_page` (schema.org JSON-LD first).

You are responsible for confirming that monitoring a site is permitted by its
terms of service. See docs/live-integrations.md.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from ..models import ProductSnapshot
from .mock_sources import MalformedSourceError, SourceUnavailableError, read_json
from .page_parser import parse_product_page

_WALL_MARKERS = ("captcha", "are you a robot", "verify you are human", "please log in", "sign in to continue")


class LiveSourceConfig:
    def __init__(self, path: Path):
        self.path = path
        data = read_json(path)
        self.entries: dict[str, dict[str, Any]] = {}
        for entry in data.get("sources", []):
            url = entry.get("url", "")
            if urlparse(url).scheme not in {"http", "https"}:
                raise MalformedSourceError(f"Live source for {entry.get('product_id')} must be an http(s) URL")
            if entry.get("permission_confirmed") is not True:
                continue  # the user must confirm they are allowed to monitor this page
            self.entries[entry["product_id"]] = entry


class PublicPageSource:
    name = "live_public_page"

    def __init__(
        self,
        config: LiveSourceConfig,
        *,
        user_agent: str,
        timeout: float = 15.0,
        min_interval: float = 10.0,
        client: Any | None = None,
        sleep: Any = time.sleep,
        clock: Any = time.monotonic,
    ):
        self.config = config
        self.user_agent = user_agent
        self.timeout = timeout
        self.min_interval = min_interval
        self._client = client
        self._sleep = sleep
        self._clock = clock
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser | None] = {}

    @property
    def client(self) -> Any:
        if self._client is None:
            import httpx

            self._client = httpx.Client(
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": self.user_agent, "Accept": "text/html"},
            )
        return self._client

    def _throttle(self, host: str) -> None:
        last = self._last_request.get(host)
        if last is not None:
            wait = self.min_interval - (self._clock() - last)
            if wait > 0:
                self._sleep(wait)
        self._last_request[host] = self._clock()

    def _get(self, url: str) -> Any:
        host = urlparse(url).netloc
        self._throttle(host)
        try:
            return self.client.get(url)
        except Exception as exc:  # noqa: BLE001 - network errors vary by library
            raise SourceUnavailableError(f"Request to {host} failed: {type(exc).__name__}") from exc

    def robots_allows(self, url: str) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._robots:
            response = self._get(origin + "/robots.txt")
            if response.status_code == 404:
                self._robots[origin] = None  # no robots.txt: allowed by convention
            elif response.status_code >= 400:
                raise SourceUnavailableError(f"robots.txt for {parsed.netloc} returned {response.status_code}; not fetching")
            else:
                rp = RobotFileParser()
                rp.parse(response.text.splitlines())
                self._robots[origin] = rp
        rp = self._robots[origin]
        return True if rp is None else rp.can_fetch(self.user_agent, url)

    def fetch(self, competitor_id: str, product_id: str, variant_id: str | None) -> dict[str, Any]:
        entry = self.config.entries.get(product_id)
        if not entry or entry.get("competitor_id") != competitor_id:
            raise LookupError(
                f"No permitted live URL configured for {competitor_id}/{product_id} "
                f"(add it to {self.config.path.name} with permission_confirmed: true)"
            )
        url = entry["url"]
        if not self.robots_allows(url):
            raise SourceUnavailableError(f"robots.txt disallows fetching {url}")
        response = self._get(url)
        if response.status_code in {401, 403, 429}:
            raise SourceUnavailableError(f"{urlparse(url).netloc} returned {response.status_code}; not retrying or bypassing")
        if response.status_code >= 400:
            raise SourceUnavailableError(f"{urlparse(url).netloc} returned {response.status_code}")
        html = response.text
        if any(marker in html[:20000].lower() for marker in _WALL_MARKERS):
            raise SourceUnavailableError("Page looks like a login or CAPTCHA wall; not attempting to bypass it")
        parsed = parse_product_page(html, variant_id or entry.get("variant_id"))
        observed = datetime.now(timezone.utc).replace(microsecond=0)
        stamp = observed.strftime("%Y%m%dt%H%M%S")
        parsed.update(
            {
                "competitor_id": competitor_id,
                "product_id": product_id,
                "observed_at": observed.isoformat().replace("+00:00", "Z"),
                "source_id": f"src-live-{product_id.lower()}-{stamp}",
                "source_url": url,
                "fixture": None,
                "page_snapshot_id": None,
                "capture_method": self.name,
                "storefront": entry.get("storefront", "US"),
            }
        )
        return parsed


def observation_to_snapshot(obs: dict[str, Any], product_name_fallback: str = "") -> ProductSnapshot:
    """Convert a fetched page observation into a storable snapshot."""
    stamp = obs["observed_at"].replace(":", "").replace("-", "").lower()
    return ProductSnapshot(
        snapshot_id=f"{obs['product_id'].lower()}-live-{stamp}"[:80],
        source_id=obs["source_id"],
        competitor_id=obs["competitor_id"],
        product_id=obs["product_id"],
        product_name=obs.get("product_name") or product_name_fallback,
        variant_id=obs.get("variant_id"),
        variant_label=obs.get("variant_label"),
        size_oz=obs.get("size_oz"),
        storefront=obs.get("storefront", "US"),
        observed_at=obs["observed_at"],
        current_price=obs.get("current_price"),
        list_price=obs.get("list_price"),
        currency=obs.get("currency"),
        promotion=obs.get("promotion"),
        availability=obs.get("availability"),
        features=obs.get("features") or [],
        headline=obs.get("headline"),
        marketing_copy=obs.get("marketing_copy"),
        hidden_text=obs.get("hidden_text"),
        source_url=obs["source_url"],
        capture_method=obs.get("capture_method", "live_public_page"),
        fictional=False,
        notes="; ".join(obs.get("parse_warnings") or []) or None,
    )
