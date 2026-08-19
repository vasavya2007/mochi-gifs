"""
tools/update_collection.py
==========================
Batch update and collection management tool for tiny.gif.

Commands:
  # See available categories and catalog tags (does NOT download anything):
  python tools/update_collection.py --list-catalog

  # See currently active collections and counts:
  python tools/update_collection.py --list-active

  # Activate or update a tag target count:
  python tools/update_collection.py --activate "bubu dudu" 10

  # Deactivate a tag:
  python tools/update_collection.py --deactivate "bubu dudu"

  # Batch update all active collections:
  python tools/update_collection.py

  # Dry run update preview:
  python tools/update_collection.py --dry-run
"""

import os
import sys
import json
import argparse
from typing import Dict, Any, List

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tools.add_gifs import (
    load_collection,
    search_and_add_gifs,
    generate_demo_stickers,
    print_catalog_summary,
    COLLECTION_PATH,
    TAGS_PATH
)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def load_tags_file(path: str = TAGS_PATH) -> Dict[str, Any]:
    """Load complete tags.json file safely."""
    if not os.path.exists(path):
        return {"active": {}, "aliases": {}, "catalog": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error reading {path}: {e}")
        return {"active": {}, "aliases": {}, "catalog": {}}


def save_tags_file(data: Dict[str, Any], path: str = TAGS_PATH) -> None:
    """Save tags.json file safely."""
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    if os.path.exists(path):
        os.replace(temp_path, path)
    else:
        os.rename(temp_path, path)


def load_tags_config(path: str = TAGS_PATH) -> Dict[str, int]:
    """Load active tags configuration from tags.json."""
    data = load_tags_file(path)
    # Backward compatible with both "active" and "collections"
    return data.get("active", data.get("collections", {}))


def count_gifs_by_tag(collection: Dict[str, Any]) -> Dict[str, int]:
    """Count existing GIFs per tag in collection."""
    counts: Dict[str, int] = {}
    for gif in collection.get("gifs", []):
        for tag in gif.get("tags", []):
            tag_lower = tag.lower().strip()
            counts[tag_lower] = counts.get(tag_lower, 0) + 1
    return counts


def list_active_tags(tags_path: str = TAGS_PATH):
    """Print currently active tags and their progress in collection.json."""
    active_config = load_tags_config(tags_path)
    collection = load_collection(COLLECTION_PATH)
    counts = count_gifs_by_tag(collection)

    print("\n" + "=" * 65)
    print("🌸 Tiny.gif Currently Active Collections 🌸")
    print("=" * 65)
    if not active_config:
        print("ℹ️ No tags are currently active in tags.json.")
    else:
        for tag, target in sorted(active_config.items()):
            current = counts.get(tag.lower().strip(), 0)
            status = "✅ Complete" if current >= target else f"📥 Need {target - current}"
            print(f"🏷️ {tag:22} : {current:2d} / {target:2d} target ({status})")

    print("-" * 65)
    print(f"Total Active Collections: {len(active_config)}")
    print(f"Total GIFs in Library   : {len(collection.get('gifs', []))}")
    print("=" * 65 + "\n")


def activate_tag(tag: str, count: int = 10, tags_path: str = TAGS_PATH):
    """Add or update an active tag target count in tags.json."""
    data = load_tags_file(tags_path)
    if "active" not in data:
        data["active"] = data.get("collections", {})

    data["active"][tag.strip()] = max(1, count)
    save_tags_file(data, tags_path)
    print(f"💖 Successfully activated tag '{tag}' with target count: {count} in tags.json!")
    print(f"💡 Run 'python tools/update_collection.py' or 'python tools/add_gifs.py --tag \"{tag}\"' to fetch GIFs.\n")


def deactivate_tag(tag: str, tags_path: str = TAGS_PATH):
    """Remove a tag from active collections in tags.json without deleting existing GIFs."""
    data = load_tags_file(tags_path)
    removed = False
    for key in ["active", "collections"]:
        if key in data and tag in data[key]:
            del data[key][tag]
            removed = True

    if removed:
        save_tags_file(data, tags_path)
        print(f"✨ Deactivated tag '{tag}' from active collections.")
    else:
        print(f"ℹ️ Tag '{tag}' was not found in active collections.")


def update_all_collections(
    tags_path: str = TAGS_PATH,
    max_dim: int = 80,
    rating: str = "g",
    api_key: str = None,
    demo_mode: bool = False,
    dry_run: bool = False
):
    """Reconcile and fetch missing GIFs for all active tags in tags.json."""
    tags_config = load_tags_config(tags_path)
    if not tags_config:
        print("ℹ️ No active collections configured in tags.json.")
        print("💡 Use 'python tools/update_collection.py --activate \"<tag>\" 10' to add one!")
        return

    print("\n" + "=" * 65)
    print("✨ Tiny.gif Batch Collection Updater ✨")
    if dry_run:
        print("🔍 MODE: DRY RUN (Previewing without downloading)")
    print("=" * 65)

    total_added = 0

    for tag, target_count in tags_config.items():
        collection = load_collection(COLLECTION_PATH)
        tag_counts = count_gifs_by_tag(collection)
        current_count = tag_counts.get(tag.lower().strip(), 0)

        needed = target_count - current_count
        print(f"\n🏷️ Tag: '{tag}' — Current: {current_count} / Target: {target_count}")

        if needed <= 0:
            print(f"  ✨ Tag '{tag}' is already up-to-date! ({current_count} items)")
            continue

        print(f"  📥 Need {needed} more GIF(s)...")

        if dry_run:
            search_and_add_gifs(
                tag=tag,
                count=needed,
                max_dim=max_dim,
                rating=rating,
                api_key=api_key,
                dry_run=True
            )
        elif demo_mode:
            added = generate_demo_stickers(tag=tag, count=min(needed, 5), max_dim=max_dim)
            total_added += len(added)
        else:
            added = search_and_add_gifs(
                tag=tag,
                count=needed,
                max_dim=max_dim,
                rating=rating,
                api_key=api_key,
                dry_run=False
            )
            total_added += len(added)

    print("\n" + "=" * 65)
    if dry_run:
        print("✨ Dry run batch preview completed! No files were downloaded.")
    else:
        print(f"🎀 Batch update completed! Added {total_added} new GIF(s) in total.")
    print("=" * 65 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Update and manage active GIF collections from data/tags.json"
    )
    parser.add_argument("--config", type=str, default=TAGS_PATH, help="Path to tags.json")
    parser.add_argument("--max-dim", type=int, default=80, help="Target max dimension (50-90 px range)")
    parser.add_argument("--rating", type=str, default="g", choices=["g", "pg", "pg-13"], help="Content rating")
    parser.add_argument("--api-key", type=str, default=None, help="GIPHY API key override")
    parser.add_argument("--demo", action="store_true", help="Generate cute procedural demo stickers")
    parser.add_argument("--dry-run", action="store_true", help="Preview what would be fetched without downloading")
    parser.add_argument("--list-catalog", action="store_true", help="List all curated categories in the catalog (no downloads)")
    parser.add_argument("--list-active", action="store_true", help="List currently active tags and target counts")
    parser.add_argument("--activate", nargs="+", help="Activate a tag: --activate \"tag name\" [target_count]")
    parser.add_argument("--deactivate", type=str, help="Deactivate a tag from active collections")

    args = parser.parse_args()

    if args.list_catalog:
        print_catalog_summary()
        return

    if args.list_active:
        list_active_tags(args.config)
        return

    if args.activate:
        tag_name = args.activate[0]
        count = int(args.activate[1]) if len(args.activate) > 1 and args.activate[1].isdigit() else 10
        activate_tag(tag_name, count=count, tags_path=args.config)
        return

    if args.deactivate:
        deactivate_tag(args.deactivate, tags_path=args.config)
        return

    update_all_collections(
        tags_path=args.config,
        max_dim=args.max_dim,
        rating=args.rating,
        api_key=args.api_key,
        demo_mode=args.demo,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()
