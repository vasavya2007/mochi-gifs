"""
tests/test_app.py
=================
Tests for Flask application endpoints and static file serving.
"""

import os
import json
import pytest
import sys

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_index_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"tiny.gif" in response.data or b"html" in response.data.lower()


def test_api_status(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["status"] == "online"
    assert data["app"] == "tiny.gif"


def test_api_collection(client):
    response = client.get("/api/collection")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["success"] is True
    assert "gifs" in data
    assert isinstance(data["gifs"], list)


def test_api_collection_filter_tag(client):
    response = client.get("/api/collection?tag=cute")
    assert response.status_code == 200
    data = json.loads(response.data)
    for g in data["gifs"]:
        tag_match = any("cute" in t.lower() for t in g["tags"]) or "cute" in g["id"].lower()
        assert tag_match


def test_api_tags(client):
    response = client.get("/api/tags")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["success"] is True
    assert "tags" in data
    assert len(data["tags"]) > 0
    # First tag is 'all'
    assert data["tags"][0]["name"] == "all"


def test_serve_gif_existing(client):
    # Get an existing GIF from API
    response = client.get("/api/collection")
    data = json.loads(response.data)
    if data["gifs"]:
        sample_file = data["gifs"][0]["file"]  # e.g. /gifs/cute/cute_001.gif
        gif_resp = client.get(sample_file)
        assert gif_resp.status_code == 200
        assert gif_resp.content_type == "image/gif"


def test_serve_gif_traversal_prevention(client):
    # Test directory traversal attack prevention
    response = client.get("/gifs/../../app.py")
    assert response.status_code in [403, 404]
