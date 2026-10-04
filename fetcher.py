"""HTTP fetching with manners: retries, rate limiting, robots.txt."""

import time
from urllib import robotparser
from urllib.parse import urlparse

import requests


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)

DEFAULT_DELAY = 5.0  # seconds between requests to the same domain


class RobotsDenied(Exception):
    """Raised when robots.txt disallows a fetch and --ignore-robots wasn't passed."""


class PoliteFetcher:
    """Wraps requests with a per-domain delay, retries, and robots.txt checks.

    One instance per run is enough; it remembers when each domain was last
    hit and spaces requests out accordingly.
    """

    def __init__(self, delay=DEFAULT_DELAY, retries=3, ignore_robots=False):
        self.delay = delay
        self.retries = retries
        self.ignore_robots = ignore_robots
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
            # TODO: cache robots.txt across runs for 24h instead of re-fetching
            parser = robotparser.RobotFileParser()
            try:
                parser.set_url(f"https://{domain}/robots.txt")
                parser.read()
            except Exception:
                return True  # no robots.txt served -> nothing to obey
            self._robots[domain] = parser
        return parser.can_fetch(USER_AGENT, url)
