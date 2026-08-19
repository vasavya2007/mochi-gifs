"""
tools/import_local.py
=====================
CLI tool to import local GIF files from your computer into tiny.gif.
Processes each GIF through the Discord-safe pipeline, copies it to the
collection directory, and registers metadata in data/collection.json.

Usage:
  python tools/import_local.py --file "my_sticker.gif" --tag "cat"
  python tools/import_local.py --dir "C:/Downloads/AnimeGifs" --tag "anime"
"""

import os
import sys
import argparse
import shutil
from datetime import datetime
from typing import List, Dict, Any

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tools.gif_processor import process_gif
from tools.add_gifs import (
    sanitize_tag,
    load_collection,
    save_collection,
    get_next_index_for_tag,
    COLLECTION_PATH,
    GIFS_DIR
)


def import_single_gif(
    file_path: str,
    tag: str,
    title: str = None,
    max_dim: int = 80
) -> Dict[str, Any]:
    """Import a single local GIF file."""
    if not os.path.isfile(file_path):
        print(f"❌ File not found: {file_path}")
        return None

    if not file_path.lower().endswith(".gif"):
        print(f"⚠️ Skipping non-GIF file: {file_path}")
        return None

    clean_tag = sanitize_tag(tag)
    tag_folder = os.path.join(GIFS_DIR, clean_tag)
    os.makedirs(tag_folder, exist_ok=True)

    collection = load_collection(COLLECTION_PATH)
    next_idx = get_next_index_for_tag(collection, clean_tag)

    gif_id = f"{clean_tag}_{next_idx:03d}"
    filename = f"{gif_id}.gif"
    rel_path = f"/gifs/{clean_tag}/{filename}"
    abs_path = os.path.join(tag_folder, filename)

    gif_title = title or os.path.splitext(os.path.basename(file_path))[0].replace("_", " ").replace("-", " ")

    print(f"  ✨ Processing local file: {os.path.basename(file_path)} -> {filename}...")

    try:
        with open(file_path, "rb") as f:
            raw_bytes = f.read()

        result = process_gif(
            raw_bytes,
            output_path=abs_path,
            max_dim=max_dim
        )

        entry = {
            "id": gif_id,
            "title": gif_title,
            "file": rel_path,
            "tags": [tag, "local", "cute"],
            "source": "local",
            "source_id": f"local_{clean_tag}_{next_idx}",
            "source_url": "",
            "width": result["width"],
            "height": result["height"],
            "file_size": result["file_size"],
            "created_at": datetime.now().isoformat()
        }

        collection = load_collection(COLLECTION_PATH)
        collection["gifs"].append(entry)
        save_collection(collection, COLLECTION_PATH)

        print(f"  💖 Successfully imported {filename} ({result['width']}x{result['height']} px, {result['file_size']} bytes)!")
        return entry
    except Exception as e:
        print(f"  ❌ Error processing {file_path}: {e}")
        return None


def import_directory(
    dir_path: str,
    tag: str,
    max_dim: int = 80
) -> List[Dict[str, Any]]:
    """Import all GIF files from a directory."""
    if not os.path.isdir(dir_path):
        print(f"❌ Directory not found: {dir_path}")
        return []

    gif_files = [
        os.path.join(dir_path, f)
        for f in os.listdir(dir_path)
        if f.lower().endswith(".gif")
    ]

    if not gif_files:
        print(f"ℹ️ No .gif files found in directory: {dir_path}")
        return []

    print(f"\n📂 Found {len(gif_files)} GIF(s) in {dir_path} for tag '{tag}':")
    imported = []
    for fp in gif_files:
        res = import_single_gif(fp, tag=tag, max_dim=max_dim)
        if res:
            imported.append(res)

    print(f"\n🎉 Successfully imported {len(imported)} GIF(s) into category '{tag}'!\n")
    return imported


def main():
    parser = argparse.ArgumentParser(
        description="Tiny.gif - Import local GIF files from your computer."
    )
    parser.add_argument("--file", type=str, default=None, help="Path to a single .gif file")
    parser.add_argument("--dir", type=str, default=None, help="Path to a directory containing .gif files")
    parser.add_argument("--tag", type=str, required=True, help="Category tag for imported GIFs")
    parser.add_argument("--title", type=str, default=None, help="Custom title (only for single file)")
    parser.add_argument("--max-dim", type=int, default=80, help="Target max dimension (default: 80)")

    args = parser.parse_args()

    if args.file:
        import_single_gif(args.file, tag=args.tag, title=args.title, max_dim=args.max_dim)
    elif args.dir:
        import_directory(args.dir, tag=args.tag, max_dim=args.max_dim)
    else:
        print("⚠️ Please specify either --file <path> or --dir <path>.")
        parser.print_help()


if __name__ == "__main__":
    main()
