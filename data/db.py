"""
data/db.py
==========
SQLite database layer for tiny.gif.

Stores GIF metadata (title, tags, file path, dimensions, source info).
Actual .gif binary files remain on disk under gifs/ — the database
only stores the path to each file, not the file content itself.

Schema:
  gifs      : one row per GIF (id, title, file, source, dims, etc.)
  tags      : one row per unique tag name
  gif_tags  : many-to-many join table between gifs and tags
"""

import os
import sqlite3
import json
from contextlib import contextmanager
from typing import Dict, Any, List, Optional

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "collection.db")
COLLECTION_JSON_PATH = os.path.join(BASE_DIR, "collection.json")

SCHEMA = """
CREATE TABLE IF NOT EXISTS gifs (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL DEFAULT '',
    file        TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT 'giphy',
    source_id   TEXT,
    source_url  TEXT,
    width       INTEGER,
    height      INTEGER,
    file_size   INTEGER,
    created_at  TEXT
);

CREATE TABLE IF NOT EXISTS tags (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS gif_tags (
    gif_id TEXT NOT NULL REFERENCES gifs(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (gif_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_gif_tags_tag_id ON gif_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_gif_tags_gif_id ON gif_tags(gif_id);
CREATE INDEX IF NOT EXISTS idx_gifs_source ON gifs(source, source_id);
"""


@contextmanager
def get_conn(db_path: str = DB_PATH):
    """Context-managed SQLite connection with foreign keys enabled."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str = DB_PATH) -> None:
    """Create tables/indexes if they don't already exist. Safe to call repeatedly."""
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA)


def _get_or_create_tag_id(conn: sqlite3.Connection, tag_name: str) -> int:
    tag_name = tag_name.strip().lower()
    row = conn.execute("SELECT id FROM tags WHERE name = ?", (tag_name,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute("INSERT INTO tags (name) VALUES (?)", (tag_name,))
    return cur.lastrowid


def upsert_gif(gif: Dict[str, Any], db_path: str = DB_PATH) -> None:
    """Insert or update a single GIF entry (and its tag associations)."""
    with get_conn(db_path) as conn:
        conn.execute("""
            INSERT INTO gifs (id, title, file, source, source_id, source_url, width, height, file_size, created_at)
            VALUES (:id, :title, :file, :source, :source_id, :source_url, :width, :height, :file_size, :created_at)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title, file=excluded.file, source=excluded.source,
                source_id=excluded.source_id, source_url=excluded.source_url,
                width=excluded.width, height=excluded.height,
                file_size=excluded.file_size, created_at=excluded.created_at
        """, {
            "id": gif.get("id"),
            "title": gif.get("title", ""),
            "file": gif.get("file", ""),
            "source": gif.get("source", "giphy"),
            "source_id": gif.get("source_id"),
            "source_url": gif.get("source_url", ""),
            "width": gif.get("width"),
            "height": gif.get("height"),
            "file_size": gif.get("file_size"),
            "created_at": gif.get("created_at"),
        })

        # Reset and rewrite tag associations for this gif
        conn.execute("DELETE FROM gif_tags WHERE gif_id = ?", (gif.get("id"),))
        for tag_name in gif.get("tags", []):
            if not tag_name or not tag_name.strip():
                continue
            tag_id = _get_or_create_tag_id(conn, tag_name)
            conn.execute(
                "INSERT OR IGNORE INTO gif_tags (gif_id, tag_id) VALUES (?, ?)",
                (gif.get("id"), tag_id)
            )


def upsert_many(gifs: List[Dict[str, Any]], db_path: str = DB_PATH) -> int:
    """Upsert multiple gif entries. Returns count processed."""
    for gif in gifs:
        upsert_gif(gif, db_path=db_path)
    return len(gifs)


def _row_to_gif_dict(conn: sqlite3.Connection, row: sqlite3.Row) -> Dict[str, Any]:
    tag_rows = conn.execute("""
        SELECT t.name FROM tags t
        JOIN gif_tags gt ON gt.tag_id = t.id
        WHERE gt.gif_id = ?
        ORDER BY t.name
    """, (row["id"],)).fetchall()
    tags = [r["name"] for r in tag_rows]

    return {
        "id": row["id"],
        "title": row["title"],
        "file": row["file"],
        "tags": tags,
        "source": row["source"],
        "source_id": row["source_id"],
        "source_url": row["source_url"],
        "width": row["width"],
        "height": row["height"],
        "file_size": row["file_size"],
        "created_at": row["created_at"],
    }


def get_all_gifs(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Return all gifs (with tags) as a list of dicts, newest first."""
    with get_conn(db_path) as conn:
        rows = conn.execute("SELECT * FROM gifs ORDER BY created_at DESC").fetchall()
        return [_row_to_gif_dict(conn, row) for row in rows]


def get_gifs_by_tag(tag: str, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Return gifs matching an exact tag name, newest first."""
    tag_clean = tag.strip().lower()
    with get_conn(db_path) as conn:
        rows = conn.execute("""
            SELECT g.* FROM gifs g
            JOIN gif_tags gt ON gt.gif_id = g.id
            JOIN tags t ON t.id = gt.tag_id
            WHERE t.name = ?
            ORDER BY g.created_at DESC
        """, (tag_clean,)).fetchall()
        return [_row_to_gif_dict(conn, row) for row in rows]


def get_tag_counts(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Return [{name, count}, ...] sorted by frequency then name."""
    with get_conn(db_path) as conn:
        rows = conn.execute("""
            SELECT t.name AS name, COUNT(gt.gif_id) AS count
            FROM tags t
            JOIN gif_tags gt ON gt.tag_id = t.id
            GROUP BY t.name
            ORDER BY count DESC, name ASC
        """).fetchall()
        return [{"name": r["name"], "count": r["count"]} for r in rows]


def get_total_count(db_path: str = DB_PATH) -> int:
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM gifs").fetchone()
        return row["c"] if row else 0


def sync_from_json(json_path: str = COLLECTION_JSON_PATH, db_path: str = DB_PATH) -> int:
    """
    One-way sync: read collection.json and upsert every entry into SQLite.
    Safe to call repeatedly (idempotent). Used for initial migration and
    can be re-run any time collection.json changes outside of this module.
    """
    init_db(db_path)
    if not os.path.exists(json_path):
        return 0
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    gifs = data.get("gifs", [])
    return upsert_many(gifs, db_path=db_path)
