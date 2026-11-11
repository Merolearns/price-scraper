"""price-scraper web UI: the same check path behind a dashboard.

Thin layer over scraper.py / fetcher.py / parsers.py / storage.py —
the CLI in scraper.py is untouched. The dashboard lists the tracked
products from sites.json with their latest price and history, "Check
now" runs the real fetch-and-record path, and the selector tester runs
the real extract_price on pasted HTML.
"""

import json
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request

from fetcher import PoliteFetcher, RobotsDenied
from scraper import extract_price, load_config, validate_sites
from storage import append_price, last_price, load_history

app = Flask(__name__)

BASE = Path(__file__).resolve().parent
CONFIG = BASE / "sites.json"
HISTORY_DIR = BASE / "history"


def _load_sites():
    """Configured sites, or [] when sites.json is missing or broken."""
    try:
        return load_config(str(CONFIG))
    except ValueError:
        return []


def _site_by_name(name):
    for site in _load_sites():
        if site["name"] == name:
            return site
    return None


def _sparkline_points(prices, width=120, height=36):
    """SVG polyline points for a small price history, or None if too short."""
    if len(prices) < 2:
        return None
    low, high = min(prices), max(prices)
    span = high - low or 1.0
    step = width / (len(prices) - 1)
    points = []
    for i, price in enumerate(prices):
        x = i * step
        y = height - 4 - (price - low) / span * (height - 8)
        points.append(f"{x:.1f},{y:.1f}")
    return " ".join(points)


def _dashboard_rows(sites):
    """One row per tracked product: latest price, change, sparkline."""
    rows = []
    for site in sites:
        name = site["name"]
        entries = load_history(name, directory=HISTORY_DIR)
        prices = [e["price"] for e in entries]
        current = prices[-1] if prices else None
        previous = prices[-2] if len(prices) > 1 else None
        change = current - previous if current is not None and previous is not None else None
        rows.append({
            "name": name,
            "url": site["url"],
            "current": current,
            "previous": previous,
            "change": change,
            "alert_below": site.get("alert_below"),
            "last_seen": entries[-1]["timestamp"] if entries else None,
            "sparkline": _sparkline_points(prices),
            "history_count": len(entries),
        })
    return rows


def _short_time(iso_timestamp):
    """ISO timestamp -> 'Nov 11, 10:00 UTC'; raw string back if unparsable."""
    if not iso_timestamp:
        return None
    try:
        return datetime.fromisoformat(iso_timestamp).strftime("%b %d, %H:%M UTC")
    except ValueError:
        return iso_timestamp


def _stats(sites, rows):
    """Dashboard stat row: counts computed from real history, nothing invented."""
    drops = 0
    last_seen = None
    for site in sites:
        prices = [e["price"] for e in load_history(site["name"], directory=HISTORY_DIR)]
        drops += sum(1 for a, b in zip(prices, prices[1:]) if b < a)
        entries = load_history(site["name"], directory=HISTORY_DIR)
        if entries and (last_seen is None or entries[-1]["timestamp"] > last_seen):
            last_seen = entries[-1]["timestamp"]
    below_target = sum(
        1 for row in rows
        if row["alert_below"] is not None and row["current"] is not None
        and row["current"] <= row["alert_below"]
    )
    return {
        "tracked": len(sites),
        "drops": drops,
        "below_target": below_target,
        "last_check": _short_time(last_seen),
    }


def _check_site(site, fetcher):
    """Fetch one site and record the price; returns a plain-English outcome."""
    name = site["name"]
    try:
        html = fetcher.get(site["url"])
        price, title = extract_price(
            html, site["price_selector"], site.get("title_selector")
        )
    except RobotsDenied as exc:
        return {"name": name, "status": "skipped", "message": str(exc)}
    except Exception as exc:  # same keep-going policy as the CLI
        return {"name": name, "status": "error",
                "message": f"{type(exc).__name__}: {exc}"}

    previous = last_price(name, directory=HISTORY_DIR)
    append_price(name, price, directory=HISTORY_DIR)
    threshold = site.get("alert_below")
    label = f"${price:.2f}" + (f"  [{title}]" if title else "")
    if previous is not None and price < previous:
        return {"name": name, "status": "drop",
                "message": f"Price drop: {label} (was ${previous:.2f})"}
    if threshold is not None and price <= threshold:
        return {"name": name, "status": "below-target",
                "message": f"Below target: {label} (target ${threshold:.2f})"}
    return {"name": name, "status": "ok", "message": label}


def _render_index(error=None, results=None, status=200):
    sites = _load_sites()
    rows = _dashboard_rows(sites)
    return render_template(
        "index.html",
        sites=sites,
        rows=rows,
        stats=_stats(sites, rows),
        config_missing=not CONFIG.exists(),
        error=error,
        results=results,
    ), status


@app.route("/", methods=["GET"])
def index():
    return _render_index()


@app.route("/product/<name>", methods=["GET"])
def product_detail(name):
    site = _site_by_name(name)
    if site is None:
        return render_template("404.html", name=name), 404
    entries = load_history(name, directory=HISTORY_DIR)
    prices = [e["price"] for e in entries]
    # Newest first, each row carrying its change from the previous check.
    history_rows = []
    for i in range(len(entries) - 1, -1, -1):
        change = None
        if i > 0:
            change = entries[i]["price"] - entries[i - 1]["price"]
        history_rows.append({
            "timestamp": entries[i]["timestamp"],
            "price": entries[i]["price"],
            "change": change,
        })
    return render_template(
        "product.html",
        site=site,
        entries=entries,
        history_rows=history_rows,
        current=prices[-1] if prices else None,
        previous=prices[-2] if len(prices) > 1 else None,
        chart_points=_sparkline_points(prices, width=600, height=200),
        chart_low=min(prices) if prices else None,
        chart_high=max(prices) if prices else None,
    )


@app.route("/check/<name>", methods=["POST"])
def check_one(name):
    site = _site_by_name(name)
    if site is None:
        return render_template("404.html", name=name), 404
    fetcher = PoliteFetcher(delay=0)
    return _render_index(results=[_check_site(site, fetcher)])


@app.route("/check-all", methods=["POST"])
def check_all():
    fetcher = PoliteFetcher(delay=0)
    results = [_check_site(site, fetcher) for site in _load_sites()]
    return _render_index(results=results)


@app.route("/add", methods=["POST"])
def add_product():
    name = (request.form.get("name") or "").strip()
    url = (request.form.get("url") or "").strip()
    price_selector = (request.form.get("price_selector") or "").strip()
    title_selector = (request.form.get("title_selector") or "").strip() or None
    alert_raw = (request.form.get("alert_below") or "").strip()

    site = {"name": name, "url": url, "price_selector": price_selector}
    if title_selector:
        site["title_selector"] = title_selector
    if alert_raw:
        try:
            site["alert_below"] = float(alert_raw.replace("$", "").replace(",", ""))
        except ValueError:
            return _render_index(
                error=f"Alert threshold {alert_raw!r} is not a number.",
                status=400,
            )

    sites = _load_sites()
    try:
        validate_sites(sites + [site])
    except ValueError as exc:
        return _render_index(error=str(exc), status=400)

    sites.append(site)
    with open(CONFIG, "w", encoding="utf-8") as fh:
        json.dump({"sites": sites}, fh, indent=2)
    return _render_index(results=[{
        "name": name, "status": "ok",
        "message": f"Added {name!r} — it will be checked on the next run.",
    }])


@app.route("/test-selector", methods=["GET", "POST"])
def test_selector():
    html = (request.form.get("html") or "").strip()
    selector = (request.form.get("selector") or "").strip()
    title_selector = (request.form.get("title_selector") or "").strip() or None
    result = error = None
    if request.method == "POST":
        if not html or not selector:
            error = "Paste some HTML and a CSS selector first."
        else:
            try:
                price, title = extract_price(html, selector, title_selector)
                result = {"price": price, "title": title}
            except Exception as exc:  # show the real error, not a traceback
                error = f"{type(exc).__name__}: {exc}"
    return render_template(
        "test_selector.html",
        html=html, selector=selector, title_selector=title_selector,
        result=result, error=error,
    )


if __name__ == "__main__":
    app.run(debug=True)
