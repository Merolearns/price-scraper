import pytest

from parsers import parse_price


@pytest.mark.parametrize("raw,expected", [
    ("$1,299.00", 1299.00),
    ("1,299.00", 1299.00),
    ("$19.99", 19.99),
    ("€ 24,99", 24.99),
    ("1.299,99 €", 1299.99),
    ("£49.99", 49.99),
    ("$1,299", 1299.00),
    ("₹1,299.00", 1299.00),
    ("  $5.00  ", 5.00),
    ("Sale: $19.99", 19.99),
    ("$19.99 - $29.99", 19.99),  # ranges take the first price
    ("$0.99", 0.99),
    ("24,99", 24.99),            # bare EU decimal
    ("1.299", 1299.00),          # EU thousands
])
def test_parse_price(raw, expected):
    assert parse_price(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", [
    "",
    "   ",
    "Free",
    "out of stock",
    "price TBD",
    None,
])
def test_parse_price_rejects(raw):
    with pytest.raises(ValueError):
        parse_price(raw)
