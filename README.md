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

## Being polite about scraping

Scraping other people's sites comes with some responsibility, so this:

- waits a few seconds between requests to the same domain (default 5s,
  adjustable with `--delay`),
- honors `robots.txt` by default (there's an `--ignore-robots` flag, but I
  only use it on sites that clearly tolerate it),
- retries transient failures with exponential backoff instead of hammering,
- identifies itself with a normal browser user agent.

It's built for checking a handful of pages occasionally, not bulk crawling.

## Notes

Personal learning project — I built it to get comfortable with `requests`,
`BeautifulSoup`, and argparse. Nothing fancy, and sites changing their HTML
is just the maintenance cost of scraping.
