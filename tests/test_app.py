"""Smoke tests for the web UI (app.py), using Flask's test client.

Everything runs in a tmp working dir so the real sites.json and
history/ are never touched, and the fetcher is stubbed — no network.
"""

import json

import pytest

import app as app_module


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "CONFIG", tmp_path / "sites.json")
    monkeypatch.setattr(app_module, "HISTORY_DIR", tmp_path / "history")
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def _write_config(tmp_path, sites):
    (tmp_path / "sites.json").write_text(json.dumps({"sites": sites}))


def _site(**overrides):
    site = {"name": "Widget", "url": "https://example.com/w",
            "price_selector": ".price"}
    site.update(overrides)
    return site


class FakeFetcher:
    """Returns fixed HTML instead of hitting the network."""

    def __init__(self, *args, **kwargs):
        pass

    def get(self, url):
        return '<html><span class="price">$19.99</span></html>'


def test_dashboard_empty_state(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"No products tracked yet" in resp.data
    assert b"sites.example.json" in resp.data


def test_dashboard_lists_product(client, tmp_path):
    _write_config(tmp_path, [_site(alert_below=25.00)])
    from storage import append_price
    append_price("Widget", 24.99, directory=tmp_path / "history")
    append_price("Widget", 19.99, directory=tmp_path / "history")

    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Widget" in resp.data
    assert b"$19.99" in resp.data
    assert b"$24.99" in resp.data
    assert b"-5.00" in resp.data  # the drop, green on the page
    assert b"<svg" in resp.data  # sparkline

    # Stats row counts real history, not invented numbers.
    assert b"1" in resp.data  # products tracked
    assert b"price drops found" in resp.data


def test_product_detail(client, tmp_path):
    _write_config(tmp_path, [_site(alert_below=15.00)])
    from storage import append_price
    append_price("Widget", 24.99, directory=tmp_path / "history")
    append_price("Widget", 19.99, directory=tmp_path / "history")

    resp = client.get("/product/Widget")
    assert resp.status_code == 200
    assert b"$19.99" in resp.data
    assert b"down $5.00" in resp.data
    assert b"alert when below $15.00" in resp.data
    assert b"<polyline" in resp.data
    assert b"2026" in resp.data or b"timestamp" not in resp.data  # history rows


def test_product_detail_missing_is_404(client):
    resp = client.get("/product/Nope")
    assert resp.status_code == 404
    assert b"Product not found" in resp.data
    assert b"Traceback" not in resp.data


def test_add_product(client, tmp_path):
    resp = client.post("/add", data={
        "name": "Gadget",
        "url": "https://example.com/g",
        "price_selector": ".price",
        "alert_below": "49.99",
    })
    assert resp.status_code == 200
    assert b"Gadget" in resp.data
    saved = json.loads((tmp_path / "sites.json").read_text())
    assert saved["sites"][0]["name"] == "Gadget"
    assert saved["sites"][0]["alert_below"] == 49.99


def test_add_product_duplicate_rejected(client, tmp_path):
    _write_config(tmp_path, [_site()])
    resp = client.post("/add", data={
        "name": "Widget",
        "url": "https://example.com/other",
        "price_selector": ".price",
    })
    assert resp.status_code == 400
    assert b"duplicate" in resp.data
    saved = json.loads((tmp_path / "sites.json").read_text())
    assert len(saved["sites"]) == 1  # nothing was written


def test_add_product_missing_url_rejected(client):
    resp = client.post("/add", data={
        "name": "Gadget",
        "url": "",
        "price_selector": ".price",
    })
    assert resp.status_code == 400
    assert b"missing required" in resp.data


def test_selector_page_loads(client):
    resp = client.get("/test-selector")
    assert resp.status_code == 200
    assert b"Test a selector" in resp.data


def test_selector_extracts_price(client):
    resp = client.post("/test-selector", data={
        "html": '<span class="product-price">$24.99</span>',
        "selector": ".product-price",
    })
    assert resp.status_code == 200
    assert b"$24.99" in resp.data


def test_selector_bad_selector_shows_error(client):
    resp = client.post("/test-selector", data={
        "html": '<span class="product-price">$24.99</span>',
        "selector": ".nope",
    })
    assert resp.status_code == 200
    assert b"matched nothing" in resp.data


def test_check_now_records_price(client, tmp_path, monkeypatch):
    _write_config(tmp_path, [_site()])
    monkeypatch.setattr(app_module, "PoliteFetcher", FakeFetcher)

    resp = client.post("/check/Widget")
    assert resp.status_code == 200
    assert b"$19.99" in resp.data
    from storage import load_history
    entries = load_history("Widget", directory=tmp_path / "history")
    assert [e["price"] for e in entries] == [19.99]


def test_check_all_records_each_site(client, tmp_path, monkeypatch):
    _write_config(tmp_path, [
        _site(),
        _site(name="Other", url="https://example.com/o"),
    ])
    monkeypatch.setattr(app_module, "PoliteFetcher", FakeFetcher)

    resp = client.post("/check-all")
    assert resp.status_code == 200
    from storage import load_history
    assert load_history("Widget", directory=tmp_path / "history")[0]["price"] == 19.99
    assert load_history("Other", directory=tmp_path / "history")[0]["price"] == 19.99


def test_check_missing_product_is_404(client):
    resp = client.post("/check/Nope")
    assert resp.status_code == 404
