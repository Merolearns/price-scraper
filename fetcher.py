"""HTTP fetching with manners: retries, rate limiting, robots.txt."""

import json
import time
import urllib.request
from urllib import robotparser
from urllib.parse import urlparse

import requests


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)

DEFAULT_DELAY = 5.0  # seconds between requests to the same domain
ROBOTS_CACHE_TTL = 24 * 3600  # re-fetch robots.txt at most once a day per domain


class RobotsDenied(Exception):
    """Raised when robots.txt disallows a fetch and --ignore-robots wasn't passed."""


class PoliteFetcher:
    """Wraps requests with a per-domain delay, retries, and robots.txt checks.

    One instance per run is enough; it remembers when each domain was last
    hit and spaces requests out accordingly.
    """

    def __init__(self, delay=DEFAULT_DELAY, retries=3, ignore_robots=False,
                 robots_cache="robots-cache.json"):
        self.delay = delay
        self.retries = retries
        self.ignore_robots = ignore_robots
        self.robots_cache = robots_cache
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self._last_hit = {}  # domain -> timestamp of last request
        self._robots = {}    # domain -> RobotFileParser

    def get(self, url):
        """Fetch a URL, returning the response text. Retries transient failures."""
        domain = urlparse(url).netloc
        if not self.ignore_robots and not self._allowed(url, domain):
            raise RobotsDenied(f"robots.txt disallows fetching {url}")

        self._wait_turn(domain)

        last_exc = None
        for attempt in range(self.retries + 1):
            try:
                resp = self.session.get(url, timeout=15)
                if resp.status_code in (429,) or 500 <= resp.status_code < 600:
                    raise requests.HTTPError(
                        f"transient status {resp.status_code} for {url}"
                    )
                resp.raise_for_status()  # 4xx other than 429: no point retrying
                self._last_hit[domain] = time.time()
                return resp.text
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < self.retries:
                    time.sleep(2 ** attempt)  # 1s, 2s, 4s...
        raise last_exc

    def _wait_turn(self, domain):
        """Sleep until enough time has passed since the last hit on this domain."""
        last = self._last_hit.get(domain, 0)
        wait = self.delay - (time.time() - last)
        if wait > 0:
            time.sleep(wait)

    def _allowed(self, url, domain):
        """True if robots.txt permits fetching the URL (or can't be read)."""
        parser = self._robots.get(domain)
        if parser is None:
            body = self._robots_body(domain)
            if body is None:
                return True  # no robots.txt served -> nothing to obey
            parser = robotparser.RobotFileParser()
            parser.set_url(f"https://{domain}/robots.txt")
            parser.parse(body.splitlines())
            self._robots[domain] = parser
        return parser.can_fetch(USER_AGENT, url)

    def _robots_body(self, domain):
        """robots.txt text for a domain, cached on disk for 24h across runs."""
        cache = _load_json(self.robots_cache)
        entry = cache.get(domain)
        if entry and time.time() - entry.get("fetched_at", 0) < ROBOTS_CACHE_TTL:
            return entry.get("body")

        try:
            req = urllib.request.Request(
                f"https://{domain}/robots.txt",
                headers={"User-Agent": USER_AGENT},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read().decode("utf-8", errors="replace")
        except Exception:
            return None  # can't read it -> nothing to obey

        cache[domain] = {"fetched_at": time.time(), "body": body}
        _save_json(self.robots_cache, cache)
        return body


def _load_json(path):
    """Read a JSON file, {} when missing or unreadable."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_json(path, data):
    """Write a JSON file; silently skip on failure (cache is optional)."""
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
    except OSError:
        pass  # cache is a nice-to-have; never break a scrape over it
