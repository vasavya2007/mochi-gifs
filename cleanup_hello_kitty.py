"""
cleanup_hello_kitty.py
=======================
One-time cleanup script to remove all hello_kitty_* entries from
data/collection.json (used after manually deleting the GIF files
from the gifs/hello_kitty/ folder).

Usage:
    python cleanup_hello_kitty.py

Run this from your TinyGif project root (same folder as app.py).
"""

import os
import json
import shutil
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
COLLECTION_PATH = os.path.join(BASE_DIR, "data", "collection.json")

TAG_PREFIX = "hello_kitty_"  # matches ids like hello_kitty_001


def main():
    if not os.path.exists(COLLECTION_PATH):
        print(f"❌ Could not find {COLLECTION_PATH}")
        return

    # Backup collection.json first, just in case
    backup_path = COLLECTION_PATH + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(COLLECTION_PATH, backup_path)
    print(f"🗂️ Backup saved to: {backup_path}")

    with open(COLLECTION_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    gifs = data.get("gifs", [])
    before_count = len(gifs)

    remaining = [g for g in gifs if not g.get("id", "").startswith(TAG_PREFIX)]
    removed_count = before_count - len(remaining)

    data["gifs"] = remaining

    with open(COLLECTION_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✅ Removed {removed_count} '{TAG_PREFIX}*' entries from collection.json")
    print(f"📦 Remaining GIFs in collection: {len(remaining)}")
    print("\n✨ Done! Restart your Flask server if it's running, then reload the site.")


if __name__ == "__main__":
    main()
