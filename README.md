# price-scraper

A small script that watches product pages and tells me when the price drops.
I kept bookmarking things and checking them by hand like an animal, so I wrote
this instead.

## How it works

- `python scraper.py check` fetches every site in `sites.json`, pulls the
  price out with a CSS selector, and appends it to a history file under
  `history/`.
- If the new price is lower than the last one seen, or below an `alert_below`
  threshold you set per site, it prints an alert line and writes to the log.
- `python scraper.py history "Product Name"` prints the recorded history.
- `python scraper.py add` walks you through adding a new site to the config.

## Setup

```bash
pip install -r requirements.txt
cp sites.example.json sites.json
# edit sites.json: real product URLs and the CSS selectors for price/title
python scraper.py check
```

Finding the right selector is the fiddly part — open the product page in your
browser's dev tools, inspect the price element, and copy its selector.
Retailers change their markup sometimes, so if a site starts failing, the
selector probably needs updating.

## Web UI

The same scraper behind a dashboard, for when you'd rather look at prices
than read terminal output:

```bash
pip install -r requirements.txt
python app.py
# open http://127.0.0.1:5000
```

The dashboard lists every product in `sites.json` with its latest price,
the previous price, the change (green when the price went down, red when
it went up), and a small sparkline of its history. Each product has a
"Check now" button, there's a "Check all" button, and each product links
to a detail page with a full price chart and a timestamped history table.
Checking from the web runs the exact same path as `python scraper.py
check` — the real fetch, the same selectors, results recorded in
`history/` — it just doesn't wait 5 seconds between requests.

There's also an add-product form on the dashboard (name, URL, price
selector, optional title selector and alert threshold) and a
`/test-selector` page: paste a chunk of a product page's HTML and a CSS
selector, and it runs the real `extract_price` on it and shows what comes
out. That's the quick way to check a selector before adding the product —
for example, pasting `<span class="product-price">$24.99</span>` with
selector `.product-price` returns $24.99.

When `sites.json` doesn't exist yet, the dashboard says so plainly and
points you at the add form (or copy `sites.example.json` to `sites.json`
as in the setup above). The command line in `scraper.py` is untouched and
still works the same way.

## Being polite about scraping

Scraping other people's sites comes with some responsibility, so this:

- waits a few seconds between requests to the same domain (default 5s,
  adjustable with `--delay`),
- honors `robots.txt` by default (there's an `--ignore-robots` flag, but I
  only use it on sites that clearly tolerate it), and caches each domain's
  robots.txt for 24 hours so repeat runs don't re-fetch it,
- retries transient failures with exponential backoff instead of hammering,
- identifies itself with a normal browser user agent.

It's built for checking a handful of pages occasionally, not bulk crawling.

## Notes

Personal learning project — I built it to get comfortable with `requests`,
`BeautifulSoup`, and argparse. Nothing fancy, and sites changing their HTML
is just the maintenance cost of scraping.
