import time

import pytest

import fetcher
from fetcher import PoliteFetcher

ROBOTS = "User-agent: *\nDisallow: /private\n"


class FakeResponse:
    def __init__(self, body):
        self._body = body.encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture
def fake_robots(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append(req.full_url)
        return FakeResponse(ROBOTS)

    monkeypatch.setattr(fetcher.urllib.request, "urlopen", fake_urlopen)
    return calls


def test_robots_disallow(fake_robots, tmp_path):
    f = PoliteFetcher(robots_cache=str(tmp_path / "robots.json"))
    assert f._allowed("https://shop.example/private/thing", "shop.example") is False
    assert f._allowed("https://shop.example/item", "shop.example") is True
    assert len(fake_robots) == 1  # in-memory reuse on repeat checks


def test_robots_cached_across_instances(fake_robots, tmp_path):
    cache = str(tmp_path / "robots.json")
    f1 = PoliteFetcher(robots_cache=cache)
    assert f1._allowed("https://shop.example/item", "shop.example") is True
    assert len(fake_robots) == 1

    f2 = PoliteFetcher(robots_cache=cache)  # new run, same cache file
    assert f2._allowed("https://shop.example/private/thing", "shop.example") is False
    assert len(fake_robots) == 1  # served from the on-disk cache


def test_stale_cache_refetches(fake_robots, tmp_path):
    cache = str(tmp_path / "robots.json")
    (tmp_path / "robots.json").write_text(
        '{"shop.example": {"fetched_at": %d, "body": %s}}'
        % (time.time() - 25 * 3600, repr("User-agent: *\nDisallow: /"))
    )
    f = PoliteFetcher(robots_cache=cache)
    assert f._allowed("https://shop.example/item", "shop.example") is True
    assert len(fake_robots) == 1  # expired entry was re-fetched


def test_unreadable_robots_allows_everything(monkeypatch, tmp_path):
    def boom(req, timeout=None):
        raise OSError("no robots.txt here")

    monkeypatch.setattr(fetcher.urllib.request, "urlopen", boom)
    f = PoliteFetcher(robots_cache=str(tmp_path / "robots.json"))
    assert f._allowed("https://shop.example/anything", "shop.example") is True
