"""Tests for the interactive `scraper.py add` flow.

The web form validates before saving, but the CLI prompt never did --
a duplicate name or a missing URL landed in sites.json and only broke
the next `check` run.
"""
import argparse
import json

import scraper


def _answers(name="widget", url="https://example.com/w",
             selector=".price", title="", alert=""):
    return iter([name, url, selector, title, alert])


def _run_add(monkeypatch, tmp_path, answers):
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    args = argparse.Namespace(config=str(tmp_path / "sites.json"))
    return scraper.cmd_add(args)


def test_add_valid_site_writes_config(monkeypatch, tmp_path):
    assert _run_add(monkeypatch, tmp_path, _answers()) == 0
    data = json.loads((tmp_path / "sites.json").read_text())
    assert data["sites"][0]["name"] == "widget"


def test_add_duplicate_name_rejected_and_config_untouched(monkeypatch, tmp_path):
    cfg = tmp_path / "sites.json"
    cfg.write_text(json.dumps({"sites": [{"name": "widget",
                                          "url": "https://example.com/w",
                                          "price_selector": ".price"}]}))
    before = cfg.read_text()
    assert _run_add(monkeypatch, tmp_path, _answers()) == 1
    assert cfg.read_text() == before


def test_add_missing_url_rejected(monkeypatch, tmp_path):
    assert _run_add(monkeypatch, tmp_path, _answers(url="")) == 1
    assert not (tmp_path / "sites.json").exists()
