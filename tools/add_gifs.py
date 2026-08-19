"""
tools/add_gifs.py
=================
CLI tool to fetch GIFs from GIPHY API, filter duplicates, process frames
using the Discord-safe pipeline, and update data/collection.json.

Features:
  - --dry-run: Preview search results without downloading.
  - --force: Force re-fetching even if tag was previously processed.
  - Tag Merging: Appends new tags to existing source GIFs (source:source_id)
    without creating redundant file downloads.
  - Alias Fallbacks: Automatically tries alternate search phrases from data/tags.json.
  - API Safeguards: Limits pagination and throttles requests.

Usage:
  python tools/add_gifs.py --tag "bubu dudu" --count 10
  python tools/add_gifs.py --tag "gojo" --count 10 --dry-run
  python tools/add_gifs.py --tag "capybara" --count 15
"""

import os
import sys
import json
import time
import argparse
import re
import math
from datetime import datetime
from typing import List, Dict, Any, Optional, Set, Tuple
import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw

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

# Load .env file
load_dotenv()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
COLLECTION_PATH = os.path.join(BASE_DIR, "data", "collection.json")
TAGS_PATH = os.path.join(BASE_DIR, "data", "tags.json")
GIFS_DIR = os.path.join(BASE_DIR, "gifs")


def sanitize_tag(tag: str) -> str:
    """Sanitize tag string for folder and file names."""
    clean = re.sub(r"[^a-zA-Z0-9]+", "_", tag.strip().lower())
    return clean.strip("_") or "misc"


def load_collection(path: str = COLLECTION_PATH) -> Dict[str, Any]:
    """Load collection metadata JSON safely."""
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return {"gifs": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "gifs" not in data:
                data["gifs"] = []
            return data
    except Exception as e:
        print(f"⚠️ Warning: Could not read collection.json ({e}). Starting fresh.")
        return {"gifs": []}


def save_collection(data: Dict[str, Any], path: str = COLLECTION_PATH) -> None:
    """Save collection metadata JSON atomically."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    if os.path.exists(path):
        os.replace(temp_path, path)
    else:
        os.rename(temp_path, path)


def load_aliases(path: str = TAGS_PATH) -> Dict[str, List[str]]:
    """Load tag aliases mapping from tags.json."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("aliases", {})
    except Exception:
        return {}


def get_search_queries(tag: str) -> List[str]:
    """Get ordered list of search queries (primary tag + aliases)."""
    clean = tag.strip().lower()
    aliases_dict = load_aliases()
    queries = [tag]
    if clean in aliases_dict:
        for alias in aliases_dict[clean]:
            if alias.lower() not in [q.lower() for q in queries]:
                queries.append(alias)
    return queries


def get_next_index_for_tag(collection: Dict[str, Any], clean_tag: str) -> int:
    """Find the next sequential index number for a tag category."""
    existing_nums = []
    prefix = f"{clean_tag}_"
    for item in collection.get("gifs", []):
        gif_id = item.get("id", "")
        if gif_id.startswith(prefix):
            suffix = gif_id[len(prefix):]
            if suffix.isdigit():
                existing_nums.append(int(suffix))
    return (max(existing_nums) + 1) if existing_nums else 1


def generate_demo_stickers(
    tag: str,
    count: int = 5,
    max_dim: int = 80,
    dry_run: bool = False
) -> List[Dict[str, Any]]:
    """Generate cute animated kawaii sticker GIFs procedurally."""
    if dry_run:
        print(f"\n🔍 Searching (Procedural Demo): '{tag}'")
        print(f"✨ Found: {count} procedural kawaii template(s)")
        print("\nWould generate:")
        for i in range(count):
            print(f"  {i+1}. cute demo {tag} #{i+1}")
        print("\n✨ [DRY RUN] No files generated or modified.\n")
        return []

    print(f"✨ Generating {count} procedural kawaii sticker(s) for tag '{tag}'...")
    stickers = []
    clean_tag = sanitize_tag(tag)
    tag_folder = os.path.join(GIFS_DIR, clean_tag)
    os.makedirs(tag_folder, exist_ok=True)

    collection = load_collection()
    next_idx = get_next_index_for_tag(collection, clean_tag)

    themes = [
        {"bg": (255, 230, 240), "accent": (255, 105, 180), "face": (70, 50, 60), "name": "blushy"},
        {"bg": (230, 240, 255), "accent": (100, 160, 255), "face": (50, 60, 80), "name": "dreamy"},
        {"bg": (240, 255, 240), "accent": (120, 210, 150), "face": (40, 70, 50), "name": "minty"},
        {"bg": (255, 250, 220), "accent": (255, 200, 80), "face": (80, 60, 40), "name": "sunny"},
        {"bg": (245, 230, 255), "accent": (190, 130, 255), "face": (60, 40, 80), "name": "starry"},
    ]

    for i in range(count):
        theme = themes[i % len(themes)]
        frames = []
        num_frames = 6
        width, height = max_dim, max_dim

        for f_idx in range(num_frames):
            im = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(im)
            
            bounce = int(math.sin((f_idx / num_frames) * math.pi * 2) * 3)
            center_x = width // 2
            center_y = (height // 2) + bounce

            r = 24
            draw.ellipse(
                [center_x - r, center_y - r, center_x + r, center_y + r],
                fill=theme["bg"],
                outline=theme["accent"],
                width=2
            )

            if any(k in tag.lower() for k in ["cat", "miffy", "kitty", "bunny", "bubu", "bear"]):
                ear_h = 10 if "miffy" in tag.lower() else 6
                draw.polygon([(center_x - 16, center_y - r + 4), (center_x - 10, center_y - r - ear_h), (center_x - 4, center_y - r + 4)], fill=theme["accent"])
                draw.polygon([(center_x + 4, center_y - r + 4), (center_x + 10, center_y - r - ear_h), (center_x + 16, center_y - r + 4)], fill=theme["accent"])

            eye_y = center_y - 2
            if f_idx == 3:
                draw.arc([center_x - 12, eye_y - 3, center_x - 4, eye_y + 3], 180, 360, fill=theme["face"], width=2)
                draw.arc([center_x + 4, eye_y - 3, center_x + 12, eye_y + 3], 180, 360, fill=theme["face"], width=2)
            else:
                draw.ellipse([center_x - 10, eye_y - 2, center_x - 6, eye_y + 2], fill=theme["face"])
                draw.ellipse([center_x + 6, eye_y - 2, center_x + 10, eye_y + 2], fill=theme["face"])

            draw.ellipse([center_x - 16, eye_y + 4, center_x - 10, eye_y + 8], fill=(255, 160, 180, 180))
            draw.ellipse([center_x + 10, eye_y + 4, center_x + 16, eye_y + 8], fill=(255, 160, 180, 180))

            if "crying" in tag.lower():
                draw.arc([center_x - 4, eye_y + 4, center_x + 4, eye_y + 10], 0, 180, fill=theme["face"], width=2)
                draw.ellipse([center_x - 14, eye_y + 8 + (f_idx % 3) * 2, center_x - 10, eye_y + 12 + (f_idx % 3) * 2], fill=(130, 200, 255, 220))
                draw.ellipse([center_x + 10, eye_y + 8 + (f_idx % 3) * 2, center_x + 14, eye_y + 12 + (f_idx % 3) * 2], fill=(130, 200, 255, 220))
            elif "sleepy" in tag.lower():
                draw.line([(center_x - 3, eye_y + 6), (center_x + 3, eye_y + 6)], fill=theme["face"], width=2)
                z_offset = (f_idx * 3) % 15
                draw.text((center_x + 18, center_y - 15 - z_offset), "z", fill=theme["accent"])
            else:
                draw.arc([center_x - 4, eye_y + 2, center_x + 4, eye_y + 8], 0, 180, fill=theme["face"], width=2)

            sparkle_x = center_x + 18 + int(math.cos(f_idx) * 2)
            sparkle_y = center_y - 12 + int(math.sin(f_idx) * 2)
            draw.text((sparkle_x, sparkle_y), "✧", fill=theme["accent"])

            frames.append(im)

        gif_id = f"{clean_tag}_{next_idx:03d}"
        filename = f"{gif_id}.gif"
        rel_path = f"/gifs/{clean_tag}/{filename}"
        abs_path = os.path.join(tag_folder, filename)

        frames[0].save(
            abs_path,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=120,
            loop=0,
            disposal=2
        )

        file_size = os.path.getsize(abs_path)
        tags_list = list(dict.fromkeys([tag, "cute", theme["name"]]))

        gif_entry = {
            "id": gif_id,
            "title": f"cute {theme['name']} {tag}",
            "file": rel_path,
            "tags": tags_list,
            "source": "procedural",
            "source_id": f"demo_{clean_tag}_{next_idx}",
            "source_url": "",
            "width": width,
            "height": height,
            "file_size": file_size,
            "created_at": datetime.now().isoformat()
        }
        stickers.append(gif_entry)
        next_idx += 1

    collection = load_collection()
    collection["gifs"].extend(stickers)
    save_collection(collection)
    print(f"💖 Added {len(stickers)} demo GIF(s) to collection.json!")
    return stickers


def fetch_giphy_items(
    query: str,
    api_key: str,
    limit: int = 25,
    rating: str = "g",
    max_pages: int = 2
) -> List[Dict[str, Any]]:
    """
    Search GIPHY API with pagination safeguards to protect API quota.
    """
    endpoint = "https://api.giphy.com/v1/gifs/search"
    results = []
    page_limit = min(limit, 50)

    for page in range(max_pages):
        offset = page * page_limit
        params = {
            "api_key": api_key,
            "q": query,
            "limit": page_limit,
            "offset": offset,
            "rating": rating,
            "lang": "en"
        }
        try:
            resp = requests.get(endpoint, params=params, timeout=12)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data", [])
            if not items:
                break
            results.extend(items)
            if len(results) >= limit:
                break
        except Exception as e:
            print(f"  ⚠️ GIPHY API warning on query '{query}' (offset {offset}): {e}")
            break

    return results


def search_and_add_gifs(
    tag: str,
    count: int = 10,
    max_dim: int = 80,
    min_dim: int = 50,
    max_bound: int = 90,
    rating: str = "g",
    api_key: Optional[str] = None,
    dry_run: bool = False,
    force: bool = False
) -> List[Dict[str, Any]]:
    """
    Search GIPHY API for tag, filter duplicates using composite key (source:source_id),
    merge tags into existing entries, process with Discord-safe pipeline,
    and update collection metadata.
    """
    giphy_key = api_key or os.getenv("GIPHY_API_KEY")

    if not giphy_key or giphy_key == "your_api_key_here":
        if dry_run:
            return generate_demo_stickers(tag=tag, count=min(count, 5), max_dim=max_dim, dry_run=True)
        print("\n" + "=" * 65)
        print("🌸 GIPHY API Key Missing or Not Configured!")
        print("=" * 65)
        print("Run: python tools/add_gifs.py --setup to paste your API key.")
        print("Switching to Cute Procedural Demo generator for now!")
        print("=" * 65 + "\n")
        return generate_demo_stickers(tag=tag, count=min(count, 5), max_dim=max_dim)

    clean_tag = sanitize_tag(tag)
    tag_folder = os.path.join(GIFS_DIR, clean_tag)
    os.makedirs(tag_folder, exist_ok=True)

    collection = load_collection()
    
    # Composite source key mapping: "source:source_id" -> gif_entry
    existing_source_map: Dict[str, Dict[str, Any]] = {}
    for g in collection.get("gifs", []):
        src = g.get("source", "giphy")
        src_id = g.get("source_id")
        if src_id:
            existing_source_map[f"{src}:{src_id}"] = g

    queries = get_search_queries(tag)
    print(f"\n🔍 Searching GIPHY for '{tag}' (requested: {count}, rating: {rating})...")
    if len(queries) > 1:
        print(f"  ✨ Query aliases available: {', '.join(queries[1:])}")

    # Fetch candidate items across primary query and aliases if needed
    candidates = []
    seen_ids = set()

    for q in queries:
        needed_from_query = max(count * 2, 20) - len(candidates)
        if needed_from_query <= 0:
            break
        items = fetch_giphy_items(q, giphy_key, limit=needed_from_query, rating=rating, max_pages=2)
        for item in items:
            item_id = item.get("id")
            if item_id and item_id not in seen_ids:
                seen_ids.add(item_id)
                candidates.append(item)

    print(f"✨ Found: {len(candidates)} total result(s) from GIPHY")

    if dry_run:
        print("\nWould download:")
        preview_count = 0
        for item in candidates:
            if preview_count >= count:
                break
            source_id = item.get("id")
            composite_key = f"giphy:{source_id}"
            title = item.get("title", f"{tag} GIF").strip()
            url = item.get("url", "")
            if composite_key in existing_source_map and not force:
                print(f"  {preview_count+1}. [EXISTS - WILL MERGE TAG] {title or source_id} (Key: {composite_key})")
            else:
                print(f"  {preview_count+1}. [NEW DOWNLOAD] {title or source_id} ({url})")
            preview_count += 1
        print(f"\n✨ [DRY RUN] No files downloaded or modified ({preview_count} items previewed).\n")
        return []

    added_gifs = []
    merged_count = 0
    collection_modified = False
    next_idx = get_next_index_for_tag(collection, clean_tag)

    for item in candidates:
        if len(added_gifs) >= count:
            break

        source_id = item.get("id")
        if not source_id:
            continue

        composite_key = f"giphy:{source_id}"

        # DUPLICATE DETECTION & TAG MERGING
        if composite_key in existing_source_map and not force:
            existing_gif = existing_source_map[composite_key]
            current_tags = existing_gif.get("tags", [])
            tag_clean = tag.strip().lower()
            if not any(t.lower() == tag_clean for t in current_tags):
                existing_gif["tags"].append(tag.strip())
                collection_modified = True
                merged_count += 1
                print(f"  🏷️ Merged tag '{tag}' into existing GIF: {existing_gif.get('id')} ({composite_key})")
            continue

        title = item.get("title", f"{tag} GIF").strip()
        source_url = item.get("url", "")

        images = item.get("images", {})
        candidate_url = None
        for key in ["fixed_height_small", "fixed_height", "downsized", "original"]:
            if key in images and images[key].get("url"):
                candidate_url = images[key]["url"]
                break

        if not candidate_url:
            continue

        print(f"  ⬇️ Downloading ({len(added_gifs) + 1}/{count}): {title or source_id}...")

        try:
            time.sleep(0.2)  # Throttle to protect API quota
            gif_resp = requests.get(candidate_url, timeout=15)
            if gif_resp.status_code != 200 or len(gif_resp.content) < 64:
                print(f"    ⚠️ Download failed for {source_id} (status: {gif_resp.status_code})")
                continue

            if not (gif_resp.content.startswith(b"GIF87a") or gif_resp.content.startswith(b"GIF89a")):
                print(f"    ⚠️ Not a valid GIF stream for {source_id}")
                continue

            gif_id = f"{clean_tag}_{next_idx:03d}"
            filename = f"{gif_id}.gif"
            rel_file_path = f"/gifs/{clean_tag}/{filename}"
            abs_file_path = os.path.join(tag_folder, filename)

            result = process_gif(
                gif_resp.content,
                output_path=abs_file_path,
                max_dim=max_dim,
                min_dim=min_dim,
                max_bound=max_bound
            )

            # Extract clean keyword tags
            tags_list = [tag]
            if title:
                words = [re.sub(r"[^a-zA-Z0-9]", "", w.lower()) for w in title.split()]
                for w in words:
                    if len(w) > 2 and w not in ["gif", "the", "and", "by", "via", "with", tag.lower()] and w not in tags_list:
                        tags_list.append(w)
            tags_list = list(dict.fromkeys(tags_list))[:6]

            gif_entry = {
                "id": gif_id,
                "title": title or f"{tag} #{next_idx}",
                "file": rel_file_path,
                "tags": tags_list,
                "source": "giphy",
                "source_id": source_id,
                "source_url": source_url,
                "width": result["width"],
                "height": result["height"],
                "file_size": result["file_size"],
                "created_at": datetime.now().isoformat()
            }

            added_gifs.append(gif_entry)
            existing_source_map[composite_key] = gif_entry
            next_idx += 1
            collection_modified = True
            print(f"    ✅ Saved: {filename} ({result['width']}x{result['height']} px, {result['file_size']} bytes)")

        except Exception as err:
            print(f"    ❌ Error processing GIF {source_id}: {err}")
            continue

    if collection_modified:
        if added_gifs:
            collection["gifs"].extend(added_gifs)
        save_collection(collection)

    print("\n" + "-" * 60)
    if added_gifs:
        print(f"🎉 Successfully added {len(added_gifs)} new cute GIF(s) for '{tag}'!")
    if merged_count > 0:
        print(f"🏷️ Merged tag '{tag}' into {merged_count} existing GIF(s) without duplicating files.")
    if not added_gifs and merged_count == 0:
        print(f"ℹ️ No new GIFs added for '{tag}'.")
    print("-" * 60 + "\n")

    return added_gifs


def print_catalog_summary():
    """Print curated categories and tag counts without downloading anything."""
    if not os.path.exists(TAGS_PATH):
        print(f"❌ {TAGS_PATH} not found.")
        return

    with open(TAGS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    catalog = data.get("catalog", {})
    active = data.get("active", data.get("collections", {}))

    print("\n" + "=" * 65)
    print("🌸 Tiny.gif Curated Tag Catalog 🌸")
    print("=" * 65)
    total_tags = 0
    for cat, tags in catalog.items():
        cat_title = cat.replace("_", " ").title()
        print(f"🏷️ {cat_title:24} : {len(tags):3d} tags (e.g. {', '.join(tags[:3])}...)")
        total_tags += len(tags)

    print("-" * 65)
    print(f"✨ Total Curated Tags in Catalog : {total_tags}")
    print(f"✨ Total Active Collections      : {len(active)}")
    print("=" * 65)
    print("💡 To preview before downloading: python tools/add_gifs.py --tag \"<tag>\" --dry-run")
    print("💡 To activate a collection      : python tools/update_collection.py --activate \"<tag>\" 10\n")


def interactive_setup():
    """Prompt user interactively to configure GIPHY API key into .env file."""
    print("\n" + "=" * 65)
    print("🌸 Tiny.gif — GIPHY API Key Interactive Setup 🌸")
    print("=" * 65)
    print("1. Get a free API key at https://developers.giphy.com/")
    print("2. Paste your API key below and press Enter.")
    print("-" * 65)
    key = input("Enter GIPHY API Key: ").strip()
    if not key:
        print("⚠️ No key entered. Setup cancelled.")
        return

    env_path = os.path.join(BASE_DIR, ".env")
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(f"GIPHY_API_KEY={key}\n")
    print(f"\n💖 Successfully saved GIPHY_API_KEY to {env_path}!")
    print("✨ You can now run: python tools/add_gifs.py --tag \"cute\" --count 10\n")


def main():
    parser = argparse.ArgumentParser(
        description="Tiny.gif - Fetch, process, and register cute small GIFs."
    )
    parser.add_argument("--tag", type=str, default=None, help="Search tag (e.g. miffy, bubu dudu, gojo)")
    parser.add_argument("--count", type=int, default=10, help="Number of GIFs to fetch (default: 10)")
    parser.add_argument("--width", type=int, default=80, help="Target max dimension (default: 80)")
    parser.add_argument("--height", type=int, default=80, help="Target max height")
    parser.add_argument("--max-dim", type=int, default=80, help="Target max dimension (50-90 px range, default: 80)")
    parser.add_argument("--rating", type=str, default="g", choices=["g", "pg", "pg-13", "r"], help="Content rating")
    parser.add_argument("--output", type=str, default="gifs", help="Output directory for GIFs")
    parser.add_argument("--api-key", type=str, default=None, help="GIPHY API key override")
    parser.add_argument("--demo", action="store_true", help="Generate cute procedural demo stickers without API")
    parser.add_argument("--dry-run", action="store_true", help="Preview search results without downloading any files")
    parser.add_argument("--force", action="store_true", help="Force re-fetching even if tag was previously processed")
    parser.add_argument("--setup", action="store_true", help="Interactively set up your GIPHY API key into .env")
    parser.add_argument("--list-catalog", action="store_true", help="List all curated categories and tag counts")

    args = parser.parse_args()

    if args.list_catalog:
        print_catalog_summary()
        return

    if args.setup:
        interactive_setup()
        return

    if not args.tag:
        parser.print_help()
        print("\n🌸 Example usage: python tools/add_gifs.py --tag \"bubu dudu\" --count 10 --dry-run")
        print("🌸 List catalog : python tools/add_gifs.py --list-catalog\n")
        return

    max_d = args.max_dim or args.width or 80

    if args.demo:
        generate_demo_stickers(tag=args.tag, count=args.count, max_dim=max_d, dry_run=args.dry_run)
    else:
        search_and_add_gifs(
            tag=args.tag,
            count=args.count,
            max_dim=max_d,
            rating=args.rating,
            api_key=args.api_key,
            dry_run=args.dry_run,
            force=args.force
        )


if __name__ == "__main__":
    main()
