import os
import sys
import json
import random
from typing import Dict, Any, List
from flask import Flask, render_template, jsonify, send_from_directory, request, abort

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

app = Flask(__name__, static_folder="static", template_folder="templates")

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
COLLECTION_FILE = os.path.join(BASE_DIR, "data", "collection.json")
GIFS_DIR = os.path.join(BASE_DIR, "gifs")


def get_collection_data() -> Dict[str, Any]:
    """Load collection metadata safely from JSON."""
    if not os.path.exists(COLLECTION_FILE):
        return {"gifs": []}
    try:
        with open(COLLECTION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "gifs" not in data:
                data["gifs"] = []
            return data
    except Exception as e:
        app.logger.error(f"Error loading collection.json: {e}")
        return {"gifs": []}


@app.route("/")
def index():
    """Render main cute scrapbook single page app."""
    return render_template("index.html")


@app.route("/api/collection", methods=["GET"])
def api_collection():
    """
    Return collection metadata with optional filtering and search.
    Query Params:
      - tag: filter by exact tag
      - q / search: keyword search in title, tags, or id
      - page: 1-indexed page number
      - limit: items per page (default all / unlimited if 0)
      - sort: 'newest' (default), 'oldest', 'random', 'title'
    """
    data = get_collection_data()
    gifs: List[Dict[str, Any]] = data.get("gifs", [])

    # Filter by tag
    tag_filter = request.args.get("tag", "").strip().lower()
    if tag_filter and tag_filter != "all":
        gifs = [
            g for g in gifs
            if any(t.lower() == tag_filter for t in g.get("tags", []))
            or tag_filter in g.get("id", "").lower()
        ]

    # Search keyword
    query = request.args.get("q", request.args.get("search", "")).strip().lower()
    if query:
        search_terms = query.split()
        filtered = []
        for g in gifs:
            searchable_text = " ".join([
                g.get("title", ""),
                g.get("id", ""),
                " ".join(g.get("tags", []))
            ]).lower()
            if all(term in searchable_text for term in search_terms):
                filtered.append(g)
        gifs = filtered

    # Sorting
    sort_mode = request.args.get("sort", "newest").lower()
    if sort_mode == "random":
        random.shuffle(gifs)
    elif sort_mode == "oldest":
        gifs = list(reversed(gifs))
    elif sort_mode == "title":
        gifs = sorted(gifs, key=lambda x: x.get("title", "").lower())
    # default 'newest': preserves insertion / newest order (or sort by created_at if available)

    total_count = len(gifs)

    # Pagination
    try:
        page = max(1, int(request.args.get("page", 1)))
        limit = int(request.args.get("limit", 0))
    except ValueError:
        page = 1
        limit = 0

    if limit > 0:
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_gifs = gifs[start_idx:end_idx]
        has_more = end_idx < total_count
    else:
        paginated_gifs = gifs
        has_more = False

    return jsonify({
        "success": True,
        "total": total_count,
        "page": page,
        "limit": limit,
        "has_more": has_more,
        "gifs": paginated_gifs
    })


@app.route("/api/tags", methods=["GET"])
def api_tags():
    """
    Return unique tags and counts derived dynamically from collection metadata.
    """
    data = get_collection_data()
    gifs = data.get("gifs", [])

    tag_counts: Dict[str, int] = {}
    for g in gifs:
        for tag in g.get("tags", []):
            clean = tag.strip().lower()
            if clean:
                tag_counts[clean] = tag_counts.get(clean, 0) + 1

    # Sorted list of tag objects: total first, then by frequency
    sorted_tags = sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))
    tag_list = [{"name": "all", "count": len(gifs)}]
    tag_list.extend([{"name": k, "count": v} for k, v in sorted_tags])

    return jsonify({
        "success": True,
        "total_gifs": len(gifs),
        "total_tags": len(tag_counts),
        "tags": tag_list
    })


@app.route("/gifs/<path:filename>")
def serve_gif(filename):
    """
    Serve processed GIF files directly from the gifs/ directory with caching.
    """
    # Normalize forward slashes for cross-platform compatibility
    normalized_path = filename.replace("\\", "/").lstrip("/")
    target_file = os.path.join(GIFS_DIR, *normalized_path.split("/"))

    # Security check to prevent directory traversal
    if not os.path.abspath(target_file).startswith(GIFS_DIR):
        abort(403)

    if not os.path.isfile(target_file):
        abort(404)

    directory, name = os.path.split(target_file)
    response = send_from_directory(directory, name, mimetype="image/gif")
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@app.route("/api/status")
def status():
    """System health check endpoint."""
    data = get_collection_data()
    return jsonify({
        "status": "online",
        "app": "tiny.gif",
        "version": "1.0.0",
        "total_gifs": len(data.get("gifs", [])),
        "aesthetic": "kawaii anime scrapbook"
    })


if __name__ == "__main__":
    print("✨ Starting tiny.gif server on http://127.0.0.1:5000 ...")
    app.run(host="0.0.0.0", port=5000, debug=True)
