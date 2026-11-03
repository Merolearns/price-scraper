import pytest

from scraper import validate_sites


def good_site(**overrides):
    site = {"name": "widget", "url": "https://example.com/w",
            "price_selector": ".price"}
    site.update(overrides)
    return site


def test_valid_config_passes():
    validate_sites([good_site(), good_site(name="other",
                                           url="https://example.com/o")])


def test_empty_config_rejected():
    with pytest.raises(ValueError, match="non-empty"):
        validate_sites([])


def test_missing_name():
    site = good_site()
    del site["name"]
    with pytest.raises(ValueError, match="missing required 'name'"):
        validate_sites([site])


def test_missing_price_selector_names_the_site():
    site = good_site()
    del site["price_selector"]
    with pytest.raises(ValueError, match="widget.*price_selector"):
        validate_sites([site])


def test_duplicate_names_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        validate_sites([good_site(), good_site()])


def test_bad_alert_below_rejected():
    with pytest.raises(ValueError, match="not a number"):
        validate_sites([good_site(alert_below="cheap")])


def test_string_alert_below_is_fine():
    validate_sites([good_site(alert_below="99.99")])


def test_non_dict_entry_rejected():
    with pytest.raises(ValueError, match="expected an object"):
        validate_sites(["https://example.com"])
