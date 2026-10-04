"""Per-product price history stored as one JSON file each."""

import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_DIR = Path("history")


def history_path(name, directory=DEFAULT_DIR):
    safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name).strip()
    safe = safe.replace(" ", "_").lower()
    return Path(directory) / f"{safe}.json"


def load_history(name, directory=DEFAULT_DIR):
    """Return the list of {'timestamp', 'price'} entries, [] if none/corrupt."""
    path = history_path(name, directory)
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return []  # corrupt file: start fresh rather than crash the run


def append_price(name, price, directory=DEFAULT_DIR):
    """Append a timestamped price; returns the full history."""
    entries = load_history(name, directory)
    entries.append({
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "price": price,
    })
    path = history_path(name, directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(entries, fh, indent=2)
    return entries


def last_price(name, directory=DEFAULT_DIR):
    """Most recently recorded price, or None if never seen."""
    entries = load_history(name, directory)
    return entries[-1]["price"] if entries else None
