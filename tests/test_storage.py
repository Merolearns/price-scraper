import json

from storage import append_price, history_path, last_price, load_history


def test_append_and_last_price(tmp_path):
    append_price("Widget", 19.99, directory=tmp_path)
    append_price("Widget", 17.50, directory=tmp_path)
    assert last_price("Widget", directory=tmp_path) == 17.50
    entries = load_history("Widget", directory=tmp_path)
    assert [e["price"] for e in entries] == [19.99, 17.50]
    assert all("timestamp" in e for e in entries)


def test_no_history_yet(tmp_path):
    assert load_history("Widget", directory=tmp_path) == []
    assert last_price("Widget", directory=tmp_path) is None


def test_corrupt_json_starts_fresh(tmp_path):
    history_path("Widget", tmp_path).write_text("{not json")
    assert load_history("Widget", directory=tmp_path) == []


def test_valid_json_wrong_shape_starts_fresh(tmp_path):
    # A dict instead of a list used to crash append_price with AttributeError.
    path = history_path("Widget", tmp_path)
    path.write_text(json.dumps({"price": 9.99}))
    assert load_history("Widget", directory=tmp_path) == []
    assert append_price("Widget", 9.99, directory=tmp_path)[0]["price"] == 9.99


def test_malformed_entries_dropped(tmp_path):
    path = history_path("Widget", tmp_path)
    path.write_text(json.dumps([
        {"timestamp": "2026-11-08T00:00:00+00:00", "price": 19.99},
        {"timestamp": "2026-11-08T00:00:00+00:00"},  # no price
        {"timestamp": "2026-11-08T00:00:00+00:00", "price": "cheap"},
        "just a string",
        {"timestamp": "2026-11-08T00:00:00+00:00", "price": 17.50},
    ]))
    entries = load_history("Widget", directory=tmp_path)
    assert [e["price"] for e in entries] == [19.99, 17.50]
    assert last_price("Widget", directory=tmp_path) == 17.50


def test_history_path_sanitized(tmp_path):
    path = history_path("My Cool Widget!", tmp_path)
    assert path.name == "my_cool_widget_.json"
    assert path.parent == tmp_path
