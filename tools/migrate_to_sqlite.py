"""
tools/migrate_to_sqlite.py
===========================
One-time migration: reads data/collection.json and populates
data/collection.db (SQLite). Safe to re-run any time — it's an
upsert, so running it again just re-syncs everything.

Usage:
    python tools/migrate_to_sqlite.py
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data import db


def main():
    print("\n" + "=" * 60)
    print("✨ tiny.gif — Migrating collection.json -> SQLite ✨")
    print("=" * 60)

    if not os.path.exists(db.COLLECTION_JSON_PATH):
        print(f"❌ {db.COLLECTION_JSON_PATH} not found. Nothing to migrate.")
        return

    db.init_db()
    count = db.sync_from_json()

    total_in_db = db.get_total_count()
    tags = db.get_tag_counts()

    print(f"✅ Synced {count} GIF record(s) from collection.json")
    print(f"📦 Total GIFs now in database : {total_in_db}")
    print(f"🏷️ Total unique tags          : {len(tags)}")
    print(f"💾 Database file              : {db.DB_PATH}")
    print("=" * 60)
    print("✨ Done! Your Flask app can now read from SQLite.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
