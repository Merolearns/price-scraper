import pytest

from scraper import load_config, validate_sites


def test_load_config_missing_file(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        load_config(str(tmp_path / "sites.json"))


def test_load_config_bad_json(tmp_path):
    bad = tmp_path / "sites.json"
    bad.write_text("{not json")
    with pytest.raises(ValueError, match="not valid JSON"):
        load_config(str(bad))


def test_load_config_dict_without_sites_key(tmp_path):
    cfg = tmp_path / "sites.json"
    cfg.write_text('{"_note": "no sites here"}')
    with pytest.raises(ValueError, match="no 'sites' key"):
        load_config(str(cfg))


def test_load_config_dict_and_list_forms(tmp_path):
    cfg = tmp_path / "sites.json"
    cfg.write_text('{"sites": [{"name": "a", "url": "https://example.com", '
                   '"price_selector": ".p"}]}')
    assert load_config(str(cfg))[0]["name"] == "a"
    cfg.write_text('[{"name": "b", "url": "https://example.com", '
                   '"price_selector": ".p"}]')
    assert load_config(str(cfg))[0]["name"] == "b"


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
