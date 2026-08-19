"""
tests/test_cli.py
=================
Tests for add_gifs.py and update_collection.py CLI logic,
tag sanitization, duplicate prevention, and JSON metadata updates.
"""

import os
import json
import pytest
import sys

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tools.add_gifs import (
    sanitize_tag,
    load_collection,
    save_collection,
    get_next_index_for_tag,
    generate_demo_stickers
)
from tools.update_collection import (
    count_gifs_by_tag,
    load_tags_config
)


def test_sanitize_tag():
    assert sanitize_tag("Hello Kitty!") == "hello_kitty"
    assert sanitize_tag("  cute--cats  ") == "cute_cats"
    assert sanitize_tag("miffy") == "miffy"
    assert sanitize_tag("!!!") == "misc"


def test_get_next_index_for_tag():
    collection = {
        "gifs": [
            {"id": "cute_001"},
            {"id": "cute_002"},
            {"id": "miffy_001"},
            {"id": "cute_005"}
        ]
    }
    assert get_next_index_for_tag(collection, "cute") == 6
    assert get_next_index_for_tag(collection, "miffy") == 2
    assert get_next_index_for_tag(collection, "anime") == 1


def test_count_gifs_by_tag():
    collection = {
        "gifs": [
            {"id": "1", "tags": ["cute", "miffy"]},
            {"id": "2", "tags": ["cute", "anime"]},
            {"id": "3", "tags": ["sleepy"]}
        ]
    }
    counts = count_gifs_by_tag(collection)
    assert counts["cute"] == 2
    assert counts["miffy"] == 1
    assert counts["anime"] == 1
    assert counts["sleepy"] == 1
    assert "happy" not in counts


def test_save_and_load_collection(tmp_path):
    test_json = tmp_path / "test_collection.json"
    dummy_data = {
        "gifs": [
            {"id": "test_001", "file": "/gifs/test/test_001.gif", "tags": ["test"]}
        ]
    }
    save_collection(dummy_data, path=str(test_json))
    loaded = load_collection(path=str(test_json))
    assert loaded["gifs"][0]["id"] == "test_001"


def test_import_local_gif(tmp_path, monkeypatch):
    from tools.import_local import import_single_gif
    from tests.test_processor import create_sample_animated_gif

    # Create dummy local gif
    sample_gif = tmp_path / "my_cat.gif"
    sample_gif.write_bytes(create_sample_animated_gif(100, 100, 2))

    # Mock COLLECTION_PATH and GIFS_DIR to tmp_path
    mock_coll_path = str(tmp_path / "collection.json")
    mock_gifs_dir = str(tmp_path / "gifs")
    monkeypatch.setattr("tools.import_local.COLLECTION_PATH", mock_coll_path)
    monkeypatch.setattr("tools.import_local.GIFS_DIR", mock_gifs_dir)

    entry = import_single_gif(str(sample_gif), tag="cat", title="My Kitty")
    assert entry is not None
    assert entry["id"] == "cat_001"
    assert entry["title"] == "My Kitty"
    assert "cat" in entry["tags"]
    assert entry["source"] == "local"
    assert os.path.exists(os.path.join(mock_gifs_dir, "cat", "cat_001.gif"))

