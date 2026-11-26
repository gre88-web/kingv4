from __future__ import annotations

import logging
import time
from typing import Any

import requests

log = logging.getLogger(__name__)

USER_AGENT = "radar/0.1 (public-data monitor)"


class HttpError(RuntimeError):
    pass


def session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


def request(
    sess: requests.Session,
    method: str,
    url: str,
    *,
    retries: int = 3,
    backoff: float = 2.0,
    timeout: float = 30.0,
    **kw: Any,
) -> requests.Response:
    """HTTP with retry on network errors, 429 and 5xx. Raises HttpError on final failure."""
    last: str = ""
    for attempt in range(retries + 1):
        try:
            r = sess.request(method, url, timeout=timeout, **kw)
            if r.status_code == 429 or r.status_code >= 500:
                last = f"HTTP {r.status_code}"
            else:
                if r.status_code >= 400:
                    raise HttpError(f"{method} {url}: HTTP {r.status_code}: {r.text[:200]}")
                return r
        except requests.RequestException as e:
            last = str(e)
        if attempt < retries:
            wait = backoff ** (attempt + 1)
            log.debug("retrying %s %s in %.1fs (%s)", method, url, wait, last)
            time.sleep(wait)
    raise HttpError(f"{method} {url}: {last}")
