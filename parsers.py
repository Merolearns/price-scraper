"""Turn raw price text from a page into a float."""

import re

# first number-ish chunk in the string; ignores "Sale:", "-", "from", etc.
_PRICE_RE = re.compile(r"-?\d[\d.,]*\d|-?\d")


def parse_price(raw):
    """Parse strings like '$1,299.00', '€ 24,99', '£49.99' into floats.

    Takes the first price-looking number found, so ranges like
    '$19.99 - $29.99' yield 19.99. Handles US ('1,299.00') and EU
    ('1.299,99' / '24,99') decimal styles heuristically. Raises ValueError
    when nothing parseable is in the string.
    """
    if raw is None:
        raise ValueError("no price text to parse")
    text = raw.strip()
    if not text:
        raise ValueError("empty price string")

    match = _PRICE_RE.search(text)
    if match is None:
        raise ValueError(f"no numeric value found in {raw!r}")

    return float(_normalize_decimal(match.group(0)))


def _normalize_decimal(number):
    """Decide which of '.' / ',' is the decimal separator."""
    negative = number.startswith("-")
    body = number.lstrip("-")
    has_dot = "." in body
    has_comma = "," in body

    if has_dot and has_comma:
        # whichever comes last is the decimal separator
        if body.rfind(".") > body.rfind(","):
            body = body.replace(",", "")          # US: 1,299.00
        else:
            body = body.replace(".", "").replace(",", ".")  # EU: 1.299,99
    elif has_comma:
        parts = body.split(",")
        if len(parts) > 1 and len(parts[-1]) == 3:
            body = "".join(parts)                 # thousands: 1,299
        else:
            body = "".join(parts[:-1]) + "." + parts[-1]  # decimal: 24,99
    elif has_dot:
        parts = body.split(".")
        if len(parts) == 2 and len(parts[1]) == 3 and len(parts[0]) <= 3:
            body = "".join(parts)                 # thousands: 1.299

    return ("-" if negative else "") + body
