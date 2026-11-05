#!/usr/bin/env python3
"""price-scraper: watch product pages, get told when the price drops."""

import argparse
import json
import logging
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from fetcher import PoliteFetcher, RobotsDenied
from parsers import parse_price
from storage import append_price, last_price, load_history

log = logging.getLogger("price-scraper")


def load_config(path):
    """Read the config file; fail with a plain-English error, not a traceback.

    A missing sites.json used to die with a bare FileNotFoundError, bad JSON
    with a JSONDecodeError, and a dict without a "sites" key with a KeyError.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        raise ValueError(
            f"config file {path!r} not found -- copy sites.example.json "
            f"to {path} and fill in real product pages"
        ) from None
    except json.JSONDecodeError as e:
        raise ValueError(f"config file {path!r} is not valid JSON: {e}") from None
    if isinstance(data, dict):
        if "sites" not in data:
            raise ValueError(f"config file {path!r} has no 'sites' key")
        return data["sites"]
    return data


def validate_sites(sites):
    """Check config entries before the first request goes out.

    A typo in sites.json used to die mid-run with a bare KeyError.
    This fails fast with the site name and the missing key instead.
    Raises ValueError on the first broken entry.
    """
    if not isinstance(sites, list) or not sites:
        raise ValueError("config must hold a non-empty list of sites")
    seen = set()
    for i, site in enumerate(sites):
        if not isinstance(site, dict):
            raise ValueError(
                f"site #{i + 1}: expected an object, got {type(site).__name__}"
            )
        name = site.get("name")
        if not name:
            raise ValueError(f"site #{i + 1}: missing required 'name'")
        for key in ("url", "price_selector"):
            if not site.get(key):
                raise ValueError(f"site {name!r}: missing required '{key}'")
        if name in seen:
            raise ValueError(f"site {name!r}: duplicate site name")
        seen.add(name)
        threshold = site.get("alert_below")
        if threshold is not None:
            try:
                float(threshold)
            except (TypeError, ValueError):
                raise ValueError(
                    f"site {name!r}: alert_below {threshold!r} is not a number"
                )


def extract_price(html, price_selector, title_selector=None):
    """Pull price (and optional title) out of a page with CSS selectors."""
    soup = BeautifulSoup(html, "html.parser")

    el = soup.select_one(price_selector)
    if el is None:
        raise LookupError(f"price selector {price_selector!r} matched nothing")
    price = parse_price(el.get_text(" ", strip=True))

    title = None
    if title_selector:
        tel = soup.select_one(title_selector)
        if tel is not None:
            title = tel.get_text(" ", strip=True)

    return price, title


def cmd_check(args):
    try:
        sites = load_config(args.config)
        validate_sites(sites)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    fetcher = PoliteFetcher(delay=args.delay, ignore_robots=args.ignore_robots)

    failures = 0
    for site in sites:
        name = site["name"]
        try:
            html = fetcher.get(site["url"])
            price, title = extract_price(
                html, site["price_selector"], site.get("title_selector")
            )
        except RobotsDenied as exc:
            log.warning("%s: skipped -- %s", name, exc)
            continue
        except Exception as exc:  # keep going with the other sites
            log.error("%s: %s: %s", name, type(exc).__name__, exc)
            failures += 1
            continue

        previous = last_price(name)
        append_price(name, price)
        threshold = site.get("alert_below")

        label = f"{name}: ${price:.2f}" + (f"  [{title}]" if title else "")
        if previous is not None and price < previous:
            drop = previous - price
            print(f"PRICE DROP: {label} (was ${previous:.2f}, down ${drop:.2f})")
            log.info("ALERT price drop for %s: %.2f -> %.2f", name, previous, price)
        elif threshold is not None and price <= threshold:
            print(f"BELOW TARGET: {label} (target ${threshold:.2f})")
            log.info("ALERT %s at %.2f, below target %.2f", name, price, threshold)
        else:
            print(label)
            log.info("checked %s: %.2f", name, price)

    return 1 if failures else 0


def cmd_history(args):
    entries = load_history(args.name, args.dir)
    if not entries:
        print(f"no history for {args.name!r}")
        return 0
    for entry in entries:
        print(f"{entry['timestamp']}: ${entry['price']:.2f}")
    return 0


def cmd_add(args):
    """Walk the user through adding a site to the config file."""
    config_path = Path(args.config)
    if config_path.exists():
        with open(config_path, encoding="utf-8") as fh:
            data = json.load(fh)
    else:
        data = {"sites": []}
    if isinstance(data, list):
        data = {"sites": data}

    name = input("Product name: ").strip()
    url = input("Product URL: ").strip()
    price_selector = input("CSS selector for the price element: ").strip()
    title_selector = input("CSS selector for the title (optional): ").strip() or None
    alert_raw = input("Alert when price drops below (optional): ").strip()

    site = {"name": name, "url": url, "price_selector": price_selector}
    if title_selector:
        site["title_selector"] = title_selector
    if alert_raw:
        try:
            site["alert_below"] = float(alert_raw.replace("$", "").replace(",", ""))
        except ValueError:
            print(f"ignoring invalid alert threshold {alert_raw!r}")

    data["sites"].append(site)
    with open(config_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    print(f"added {name!r} to {config_path}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="price-scraper",
        description="Monitor product pages for price drops.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="fetch every configured site once")
    p_check.add_argument("--config", default="sites.json")
    p_check.add_argument(
        "--delay", type=float, default=5.0,
        help="seconds between requests to the same domain",
    )
    p_check.add_argument(
        "--ignore-robots", action="store_true",
        help="skip the robots.txt check (use sparingly)",
    )
    p_check.set_defaults(func=cmd_check)

    p_hist = sub.add_parser("history", help="print the recorded price history")
    p_hist.add_argument("name", help="product name as in the config file")
    p_hist.add_argument("--dir", default="history")
    p_hist.set_defaults(func=cmd_history)

    p_add = sub.add_parser("add", help="interactively add a site to the config")
    p_add.add_argument("--config", default="sites.json")
    p_add.set_defaults(func=cmd_add)

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler("price-scraper.log"),
            logging.StreamHandler(sys.stderr),
        ],
    )
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
