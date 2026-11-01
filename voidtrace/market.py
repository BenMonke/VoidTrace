"""Shared Warframe.Market API access.

Public data needs no account. Signed-in calls (your own orders) go through `request()` with a
token from voidtrace.account. Requests are spaced to stay under the site's API limits (terms, section 11):
3 a second for listings, 10 a minute for contracts (riven auctions).
"""

from __future__ import annotations

import threading
import time
from typing import Any, Optional

import requests

API_BASE = "https://api.warframe.market/v2"
API_BASE_V1 = "https://api.warframe.market/v1"
HEADERS = {
    "Accept": "application/json",
    "Language": "en",
    "Platform": "pc",
    "User-Agent": "VoidTrace/0.2 (Warframe companion)",
}
MIN_INTERVAL = 0.35  # seconds between listing requests
CONTRACT_INTERVAL = 6.0  # seconds between riven auction requests


class MarketClient:
    # shared by every client: the limits are for the whole app, and prices, sellers and rivens each have one
    _locks = {"listings": threading.Lock(), "contracts": threading.Lock()}
    _last = {"listings": 0.0, "contracts": 0.0}

    def __init__(self, session: Optional[requests.Session] = None, timeout: float = 10.0) -> None:
        self.session = session or requests.Session()
        self.timeout = timeout

    def get(self, path: str) -> Any:
        """GET {API_BASE}{path} (v2) and return the `data` field of the JSON envelope."""
        return self._get(API_BASE + path)["data"]

    def get_v1(self, path: str) -> Any:
        """GET a legacy v1 endpoint and return its `payload`. Used for closed-trade statistics,
        which v2 does not expose."""
        return self._get(API_BASE_V1 + path)["payload"]

    def _get(self, url: str) -> Any:
        resp = self.request("GET", url)
        resp.raise_for_status()
        return resp.json()

    def request(self, method: str, url: str, headers: Optional[dict] = None, json: Any = None) -> requests.Response:
        """Rate-limited request; the caller checks the status. `url` may be a v1/v2 path or a full URL."""
        if url.startswith("/"):
            url = API_BASE + url
        kind, interval = ("contracts", CONTRACT_INTERVAL) if "/auctions" in url else ("listings", MIN_INTERVAL)
        with self._locks[kind]:
            wait = interval - (time.monotonic() - self._last[kind])
            if wait > 0:
                time.sleep(wait)
            self._last[kind] = time.monotonic()
        return self.session.request(method, url, headers={**HEADERS, **(headers or {})}, json=json,
                                    timeout=self.timeout)
