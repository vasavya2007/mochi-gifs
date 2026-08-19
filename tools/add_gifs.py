"""
tools/add_gifs.py
=================
Fetch cute-character GIFs from GIPHY and store useful semantic tags.

The important idea is:

    USER TAG / REACTION
        angry
        annoyed
        wow
        bruh
        crying
        ...

    CUTE SEARCH SOURCES
        cute Anya Forger
        cute Bubu Dudu
        cute anime
        cute cat
        cute chibi

    GIPHY QUERY
        cute Anya Forger angry
        cute Bubu Dudu angry
        cute anime angry
        cute cat angry
        cute chibi angry

A downloaded GIF is stored under the reaction folder and gets tags such as:

    ["angry", "cute", "anya", "anime", "character"]

The reaction tag is always present, so searching the site for "angry" finds
cute-character angry GIFs.
"""

import argparse
import json
import math
import os
import re
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

from tools.gif_processor import process_gif

load_dotenv()

COLLECTION_PATH = os.path.join(BASE_DIR, "data", "collection.json")
TAGS_PATH = os.path.join(BASE_DIR, "data", "tags.json")
GIFS_DIR = os.path.join(BASE_DIR, "gifs")

DEFAULT_SEARCH_SOURCES = [
    {"query": "cute anime", "tags": ["cute", "anime", "character"]},
    {"query": "cute cat", "tags": ["cute", "cat", "animal", "character"]},
    {"query": "cute chibi", "tags": ["cute", "chibi", "anime", "character"]},
]


def sanitize_tag(tag: str) -> str:
    """Sanitize a tag for a GIF folder/file prefix."""
    clean = re.sub(r"[^a-zA-Z0-9]+", "_", tag.strip().lower())
    return clean.strip("_") or "misc"


def normalize_text(value: str) -> str:
    """Collapse whitespace and normalize a search phrase."""
    return re.sub(r"\s+", " ", value.strip().lower())


def load_collection(path: str = COLLECTION_PATH) -> Dict[str, Any]:
    """Load collection.json safely."""
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return {"gifs": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "gifs" not in data:
            data["gifs"] = []
        return data
    except Exception as exc:
        print(f"⚠️ Warning: Could not read collection.json ({exc}). Starting fresh.")
        return {"gifs": []}


def save_collection(data: Dict[str, Any], path: str = COLLECTION_PATH) -> None:
    """Atomically save collection.json."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    if os.path.exists(path):
        os.replace(temp_path, path)
    else:
        os.rename(temp_path, path)


def load_tags_config(path: str = TAGS_PATH) -> Dict[str, Any]:
    """Load the complete tags configuration."""
    if not os.path.exists(path):
        return {"active": {}, "aliases": {}, "cute_sources": [], "catalog": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"⚠️ Warning: Could not read tags.json ({exc}). Using defaults. {exc}")
        return {"active": {}, "aliases": {}, "cute_sources": [], "catalog": {}}


def load_aliases(path: str = TAGS_PATH) -> Dict[str, List[str]]:
    """Load optional manual search aliases for reaction tags."""
    data = load_tags_config(path)
    aliases = data.get("aliases", {})
    return aliases if isinstance(aliases, dict) else {}


def load_cute_sources(path: str = TAGS_PATH) -> List[Dict[str, Any]]:
    """Load cute search sources and their semantic tags."""
    data = load_tags_config(path)
    sources = data.get("cute_sources", [])
    if not isinstance(sources, list) or not sources:
        return DEFAULT_SEARCH_SOURCES.copy()

    cleaned: List[Dict[str, Any]] = []
    for source in sources:
        if isinstance(source, str):
            cleaned.append({"query": source, "tags": source.lower().split()})
            continue
        if not isinstance(source, dict):
            continue
        query = str(source.get("query", "")).strip()
        if not query:
            continue
        tags = source.get("tags", [])
        if not isinstance(tags, list):
            tags = []
        cleaned.append({
            "query": query,
            "tags": [str(t).strip().lower() for t in tags if str(t).strip()]
        })

    return cleaned or DEFAULT_SEARCH_SOURCES.copy()


def get_search_sources(reaction: str) -> List[Dict[str, Any]]:
    """
    Build GIPHY queries for a reaction.

    Primary behavior: combine every cute source with the reaction.
    Example: "cute anya forger" + "angry" -> "cute anya forger angry".

    Manual aliases in tags.json are also included. Their semantic tags are
    inferred conservatively from the query, with the reaction always added.
    """
    reaction_clean = normalize_text(reaction)
    config = load_tags_config()
    sources = load_cute_sources()
    aliases = config.get("aliases", {})
    alias_values = aliases.get(reaction_clean, []) if isinstance(aliases, dict) else []

    result: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    for source in sources:
        source_query = normalize_text(str(source.get("query", "")))
        if not source_query:
            continue
        query = normalize_text(f"{source_query} {reaction_clean}")
        if query in seen:
            continue
        seen.add(query)
        result.append({
            "query": query,
            "tags": list(dict.fromkeys(source.get("tags", []) + [reaction_clean]))
        })

    # Manual aliases are useful for targeted phrases such as
    # "cute Anya angry" or "cute Bubu Dudu annoyed".
    if isinstance(alias_values, list):
        for alias in alias_values:
            query = normalize_text(str(alias))
            if not query or query in seen:
                continue
            seen.add(query)
            result.append({
                "query": query,
                "tags": infer_tags_from_query(query, reaction_clean)
            })

    return result


def get_search_queries(tag: str) -> List[str]:
    """Backward-compatible helper returning only generated search strings."""
    return [item["query"] for item in get_search_sources(tag)]


def infer_tags_from_query(query: str, reaction: str = "") -> List[str]:
    """
    Infer safe searchable tags from a query.

    This intentionally does NOT dump every word from a GIPHY title into the
    database. Tags come from our controlled query vocabulary instead.
    """
    text = normalize_text(query)
    reaction_clean = normalize_text(reaction)
    tags: List[str] = []

    if "cute" in text.split():
        tags.append("cute")

    known_phrases = [
        "anya forger", "bubu dudu", "hello kitty", "miffy", "cinnamoroll",
        "kuromi", "my melody", "pusheen", "totoro", "pikachu", "kirby",
        "cute anime", "cute chibi", "cute cat", "cute bunny", "cute bear"
    ]
    for phrase in known_phrases:
        if phrase in text:
            tags.append(phrase)

    # Single-word style tags that are useful in the current collection.
    for word in ["anya", "anime", "chibi", "cat", "bunny", "bear", "animal", "character"]:
        if re.search(rf"\b{re.escape(word)}\b", text):
            tags.append(word)

    if reaction_clean:
        tags.append(reaction_clean)

    return list(dict.fromkeys(tags))


def get_next_index_for_tag(collection: Dict[str, Any], clean_tag: str) -> int:
    """Find the next sequential index for a reaction folder."""
    existing_nums: List[int] = []
    prefix = f"{clean_tag}_"
    for item in collection.get("gifs", []):
        gif_id = item.get("id", "")
        if gif_id.startswith(prefix):
            suffix = gif_id[len(prefix):]
            if suffix.isdigit():
                existing_nums.append(int(suffix))
    return max(existing_nums) + 1 if existing_nums else 1


def generate_demo_stickers(
    tag: str,
    count: int = 5,
    max_dim: int = 80,
    dry_run: bool = False
) -> List[Dict[str, Any]]:
    """Generate small procedural kawaii stickers for offline testing."""
    if dry_run:
        print(f"\n🔍 Procedural demo preview: '{tag}' ({count} sticker(s))")
        return []

    print(f"✨ Generating {count} procedural kawaii sticker(s) for '{tag}'...")
    clean_tag = sanitize_tag(tag)
    tag_folder = os.path.join(GIFS_DIR, clean_tag)
    os.makedirs(tag_folder, exist_ok=True)

    collection = load_collection()
    next_idx = get_next_index_for_tag(collection, clean_tag)
    stickers: List[Dict[str, Any]] = []

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
        width = height = max_dim

        for f_idx in range(num_frames):
            im = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(im)
            bounce = int(math.sin((f_idx / num_frames) * math.pi * 2) * 3)
            center_x = width // 2
            center_y = height // 2 + bounce
            r = 24
            draw.ellipse(
                [center_x - r, center_y - r, center_x + r, center_y + r],
                fill=theme["bg"], outline=theme["accent"], width=2
            )
            eye_y = center_y - 2
            draw.ellipse([center_x - 10, eye_y - 2, center_x - 6, eye_y + 2], fill=theme["face"])
            draw.ellipse([center_x + 6, eye_y - 2, center_x + 10, eye_y + 2], fill=theme["face"])
            draw.arc([center_x - 4, eye_y + 2, center_x + 4, eye_y + 8], 0, 180, fill=theme["face"], width=2)
            frames.append(im)

        gif_id = f"{clean_tag}_{next_idx:03d}"
        filename = f"{gif_id}.gif"
        rel_path = f"/gifs/{clean_tag}/{filename}"
        abs_path = os.path.join(tag_folder, filename)
        frames[0].save(
            abs_path, format="GIF", save_all=True, append_images=frames[1:],
            duration=120, loop=0, disposal=2
        )

        file_size = os.path.getsize(abs_path)
        gif_entry = {
            "id": gif_id,
            "title": f"cute {normalize_text(tag)}",
            "file": rel_path,
            "tags": list(dict.fromkeys([normalize_text(tag), "cute"])),
            "source": "procedural",
            "source_id": f"demo_{clean_tag}_{next_idx}",
            "source_url": "",
            "width": width,
            "height": height,
            "file_size": file_size,
            "created_at": datetime.now().isoformat(),
        }
        stickers.append(gif_entry)
        next_idx += 1

    collection["gifs"].extend(stickers)
    save_collection(collection)
    print(f"💖 Added {len(stickers)} demo GIF(s) to collection.json!")
    return stickers


def fetch_giphy_items(
    query: str,
    api_key: str,
    limit: int = 25,
    rating: str = "g",
    max_pages: int = 1
) -> List[Dict[str, Any]]:
    """Search GIPHY with conservative pagination to protect API quota."""
    endpoint = "https://api.giphy.com/v1/gifs/search"
    results: List[Dict[str, Any]] = []
    page_limit = min(max(limit, 1), 50)

    for page in range(max_pages):
        offset = page * page_limit
        params = {
            "api_key": api_key,
            "q": query,
            "limit": page_limit,
            "offset": offset,
            "rating": rating,
            "lang": "en",
        }
        try:
            resp = requests.get(endpoint, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data", [])
            if not items:
                break
            results.extend(items)
            if len(results) >= limit:
                break
        except Exception as exc:
            print(f"  ⚠️ GIPHY warning for '{query}' (offset {offset}): {exc}")
            break

    return results[:limit]


def build_tags_for_result(
    reaction: str,
    search_source: Dict[str, Any]
) -> List[str]:
    """Build controlled semantic tags; never use arbitrary GIPHY title words."""
    source_tags = search_source.get("tags", [])
    tags = [reaction]
    tags.extend(source_tags)
    return list(dict.fromkeys(normalize_text(t) for t in tags if normalize_text(t)))


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
    Fetch cute-character GIFs for a semantic reaction tag.

    Example:
        --tag angry

    searches multiple cute sources:
        cute anya forger angry
        cute bubu dudu angry
        cute anime angry
        cute cat angry
        cute chibi angry

    New GIF metadata gets controlled tags such as:
        ["angry", "cute", "anya", "anime", "character"]
    """
    reaction = normalize_text(tag)
    if not reaction:
        print("❌ Empty tag.")
        return []

    giphy_key = api_key or os.getenv("GIPHY_API_KEY")
    if not giphy_key or giphy_key == "your_api_key_here":
        if dry_run:
            print("⚠️ GIPHY_API_KEY is not configured; showing a dry-run preview only.")
            sources = get_search_sources(reaction)
            for source in sources:
                print(f"  🔎 {source['query']}")
            return []
        print("❌ GIPHY_API_KEY is missing. Set it in .env or pass --api-key.")
        return []

    clean_tag = sanitize_tag(reaction)
    tag_folder = os.path.join(GIFS_DIR, clean_tag)
    os.makedirs(tag_folder, exist_ok=True)

    collection = load_collection()
    existing_source_map: Dict[str, Dict[str, Any]] = {}
    for gif in collection.get("gifs", []):
        src = gif.get("source", "giphy")
        src_id = gif.get("source_id")
        if src_id:
            existing_source_map[f"{src}:{src_id}"] = gif

    sources = get_search_sources(reaction)
    if not sources:
        print(f"❌ No search sources configured for '{reaction}'.")
        return []

    # Spread the requested count across sources. For 10 GIFs and 5 sources,
    # each source contributes roughly 2 candidates. This is intentionally
    # different from the old "one query gets everything" behavior.
    per_source = max(2, math.ceil(count / len(sources)))
    candidate_limit = max(4, per_source * 2)

    print(f"\n🔍 Reaction: '{reaction}' | target: {count} | rating: {rating}")
    print(f"🎀 Cute sources: {len(sources)} | about {len(sources)} GIPHY searches")

    candidates: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    seen_ids: Set[str] = set()

    for index, source in enumerate(sources, start=1):
        query = source["query"]
        print(f"  [{index}/{len(sources)}] 🔎 {query}")
        items = fetch_giphy_items(
            query,
            giphy_key,
            limit=candidate_limit,
            rating=rating,
            max_pages=1,
        )
        for item in items:
            item_id = item.get("id")
            if item_id and item_id not in seen_ids:
                seen_ids.add(item_id)
                candidates.append((item, source))

    print(f"✨ Found {len(candidates)} unique candidate(s).")

    if dry_run:
        print("\nWould search/download:")
        for item, source in candidates[:count]:
            source_id = item.get("id", "?")
            print(f"  • {source['query']} -> {source_id}")
        print("\n✨ [DRY RUN] Nothing was downloaded or modified.\n")
        return []

    added_gifs: List[Dict[str, Any]] = []
    merged_count = 0
    collection_modified = False
    next_idx = get_next_index_for_tag(collection, clean_tag)

    for item, source in candidates:
        if len(added_gifs) >= count:
            break

        source_id = item.get("id")
        if not source_id:
            continue
        composite_key = f"giphy:{source_id}"
        desired_tags = build_tags_for_result(reaction, source)

        if composite_key in existing_source_map and not force:
            existing_gif = existing_source_map[composite_key]
            current_tags = existing_gif.setdefault("tags", [])
            current_lower = {normalize_text(t) for t in current_tags}
            changed = False
            for new_tag in desired_tags:
                if new_tag not in current_lower:
                    current_tags.append(new_tag)
                    current_lower.add(new_tag)
                    changed = True
            if changed:
                collection_modified = True
                merged_count += 1
                print(f"  🏷️ Merged tags into existing {existing_gif.get('id')}: {desired_tags}")
            continue

        images = item.get("images", {})
        candidate_url = None
        for key in ["fixed_height_small", "fixed_height", "downsized", "original"]:
            image = images.get(key, {})
            if image.get("url"):
                candidate_url = image["url"]
                break
        if not candidate_url:
            continue

        query_title = source["query"]
        print(f"  ⬇️ Downloading {len(added_gifs) + 1}/{count}: {query_title}")

        try:
            time.sleep(0.15)
            gif_resp = requests.get(candidate_url, timeout=20)
            if gif_resp.status_code != 200 or len(gif_resp.content) < 64:
                print(f"    ⚠️ Download failed for {source_id} (status {gif_resp.status_code})")
                continue
            if not (gif_resp.content.startswith(b"GIF87a") or gif_resp.content.startswith(b"GIF89a")):
                print(f"    ⚠️ Not a GIF stream for {source_id}")
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
                max_bound=max_bound,
            )

            gif_entry = {
                "id": gif_id,
                "title": query_title,
                "file": rel_file_path,
                "tags": desired_tags,
                "source": "giphy",
                "source_id": source_id,
                "source_url": item.get("url", ""),
                "search_query": query_title,
                "width": result["width"],
                "height": result["height"],
                "file_size": result["file_size"],
                "created_at": datetime.now().isoformat(),
            }

            added_gifs.append(gif_entry)
            existing_source_map[composite_key] = gif_entry
            next_idx += 1
            collection_modified = True
            print(
                f"    ✅ Saved {filename} | tags: {', '.join(desired_tags)} "
                f"| {result['width']}x{result['height']}"
            )
        except Exception as exc:
            print(f"    ❌ Error processing GIF {source_id}: {exc}")

    if collection_modified:
        collection["gifs"].extend(added_gifs)
        save_collection(collection)

    print("\n" + "-" * 60)
    print(f"🎉 Added {len(added_gifs)} new GIF(s) for '{reaction}'.")
    if merged_count:
        print(f"🏷️ Updated tags on {merged_count} existing GIF(s).")
    if not added_gifs and not merged_count:
        print("ℹ️ No new GIFs were added.")
    print("-" * 60 + "\n")

    return added_gifs


def print_catalog_summary() -> None:
    """Print the small active catalog and cute search sources."""
    data = load_tags_config()
    active = data.get("active", {})
    sources = data.get("cute_sources", [])
    catalog = data.get("catalog", {})

    print("\n" + "=" * 65)
    print("🌸 Tiny.gif Cute Reaction Catalog 🌸")
    print("=" * 65)
    print(f"🏷️ Active reaction tags : {len(active)}")
    for tag, target in active.items():
        print(f"   • {tag:16} -> {target} GIFs")
    print(f"\n🎀 Cute search sources  : {len(sources)}")
    for source in sources:
        query = source.get("query") if isinstance(source, dict) else str(source)
        print(f"   • {query}")
    if catalog:
        print("\n📚 Catalog categories:")
        for name, values in catalog.items():
            print(f"   • {name}: {len(values)}")
    print("=" * 65 + "\n")


def interactive_setup() -> None:
    """Prompt for a GIPHY API key and save it to .env."""
    print("\n🌸 Tiny.gif — GIPHY API Key Setup 🌸")
    key = input("Enter GIPHY API Key: ").strip()
    if not key:
        print("⚠️ No key entered. Setup cancelled.")
        return
    env_path = os.path.join(BASE_DIR, ".env")
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(f"GIPHY_API_KEY={key}\n")
    print(f"💖 Saved GIPHY_API_KEY to {env_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tiny.gif — fetch cute-character GIFs with semantic reaction tags."
    )
    parser.add_argument("--tag", type=str, default=None, help="Reaction tag, e.g. angry, annoyed, wow")
    parser.add_argument("--count", type=int, default=10, help="Number of GIFs to fetch")
    parser.add_argument("--width", type=int, default=80, help="Target max dimension")
    parser.add_argument("--height", type=int, default=80, help="Target max height")
    parser.add_argument("--max-dim", type=int, default=80, help="Target max dimension")
    parser.add_argument("--rating", type=str, default="g", choices=["g", "pg", "pg-13", "r"], help="Content rating")
    parser.add_argument("--output", type=str, default="gifs", help="Output directory (kept for CLI compatibility)")
    parser.add_argument("--api-key", type=str, default=None, help="GIPHY API key override")
    parser.add_argument("--demo", action="store_true", help="Generate procedural demo stickers")
    parser.add_argument("--dry-run", action="store_true", help="Preview searches without downloading")
    parser.add_argument("--force", action="store_true", help="Re-download even if source GIF already exists")
    parser.add_argument("--setup", action="store_true", help="Save GIPHY API key to .env")
    parser.add_argument("--list-catalog", action="store_true", help="Show active reactions and cute sources")
    args = parser.parse_args()

    if args.list_catalog:
        print_catalog_summary()
        return
    if args.setup:
        interactive_setup()
        return
    if not args.tag:
        parser.print_help()
        return

    max_d = args.max_dim or args.width or 80
    if args.demo:
        generate_demo_stickers(args.tag, count=args.count, max_dim=max_d, dry_run=args.dry_run)
    else:
        search_and_add_gifs(
            tag=args.tag,
            count=args.count,
            max_dim=max_d,
            rating=args.rating,
            api_key=args.api_key,
            dry_run=args.dry_run,
            force=args.force,
        )


if __name__ == "__main__":
    main()
