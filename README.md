# ˚₊‧꒰ა ♡ ໒꒱ ‧₊˚ tiny.gif
### *little things that move — a cute personal collection of tiny animated GIFs*

`tiny.gif` is a beginner-friendly full-stack web app and automated Python pipeline for curating, processing, and displaying a personal sticker collection of small, cute animated GIFs.

---

## 🌸 Features

- **Kawaii Anime Scrapbook Aesthetic**: Soft pastel tones, floating windows, gentle star/heart particle animations, washi tape cards, and retro anime touches.
- **Discord-Safe GIF Processor**: Solves the classic broken frame slicing bug by coalescing all frames onto a master RGBA canvas before resizing and re-encoding with palette transparency.
- **Proportional Resizing (50×50 to 90×90 px)**: Naturally scales wide, square, or tall GIFs while strictly preserving original aspect ratios.
- **Instant Live Search & Tag Drawer**: Filter effortlessly across tags, titles, and keywords with zero page reloads.
- **One-Click Link Copy & Direct Download**: Copies stable, direct self-hosted URLs with animated `copied ♡` feedback.
- **Zero Heavy Databases**: Clean, lightweight JSON metadata architecture (`data/collection.json` & `data/tags.json`).
- **Offline / Procedural Demo Fallback**: Works immediately out-of-the-box even before setting up a GIPHY API key!

---

## 🎀 Quick Start Guide

### 1. Requirements & Installation

Make sure you have **Python 3.10+** installed.

Open your terminal in the project folder and run:

```bash
# 1. Create a virtual environment (optional but recommended)
python -m venv .venv

# 2. Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (Command Prompt):
.venv\Scripts\activate.bat
# macOS / Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

### 2. Setting Up Your GIPHY API Key (Foolproof & Easy)

To fetch live GIFs directly from GIPHY:

1. Create a free account at the [GIPHY Developer Dashboard](https://developers.giphy.com/).
2. Click **Create an App** (choose "API", give it a cute name like `tiny-gif`).
3. Copy your generated **API Key**.
4. In your project folder, create a file named `.env` (or copy `.env.example` to `.env`):

```bash
# Windows PowerShell
Copy-Item .env.example .env

# macOS / Linux
cp .env.example .env
```

5. Open `.env` and paste your key:

```ini
GIPHY_API_KEY=AbCdEf1234567890YourKeyHere
```

> **Note**: Even if you don't have an API key yet, you can run the scripts with `--demo` to generate cute procedural animated stickers instantly!

---

### 3. Running the Website

Start the Flask server:

```bash
python app.py
```

Then open your browser to:

👉 **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 🛠️ Maintaining Your Collection (CLI Tools)

### Adding GIFs by Tag

To search, download, coalesce, resize, and add GIFs for any tag:

```bash
# Add 10 cute miffy GIFs:
python tools/add_gifs.py --tag "miffy" --count 10

# Add 20 cute anime GIFs:
python tools/add_gifs.py --tag "anime" --count 20

# Add 15 sleepy GIFs with custom target dimension:
python tools/add_gifs.py --tag "sleepy" --count 15 --max-dim 75

# Add Gojo GIFs:
python tools/add_gifs.py --tag "gojo" --count 10
```

#### Optional CLI Arguments:
- `--tag <name>`: The search tag (e.g. `cute`, `cat`, `crying`, `hello kitty`).
- `--count <n>`: Number of GIFs to fetch (default: `10`).
- `--max-dim <n>`: Target bounding size in px within the 50px–90px range (default: `80`).
- `--rating <g|pg|pg-13>`: Content rating filter (default: `g`).
- `--api-key <key>`: Pass GIPHY key directly if not in `.env`.
- `--demo`: Generate cute animated kawaii stickers procedurally.
- `--setup`: Interactive console prompt to paste your API key.

---

### Importing Local GIFs from Your Computer

If you already have downloaded `.gif` files on your computer:

```bash
# Import a single GIF file:
python tools/import_local.py --file "path/to/my_sticker.gif" --tag "cat"

# Import an entire folder of GIFs:
python tools/import_local.py --dir "C:/Downloads/CuteGifs" --tag "anime"
```

---

### Batch Updating from `data/tags.json`

You can define all your favorite tags and desired counts in `data/tags.json`:

```json
{
  "collections": {
    "cute": 15,
    "miffy": 10,
    "crying": 10,
    "sleepy": 10,
    "anime": 15,
    "cat": 12,
    "happy": 10,
    "angry": 8,
    "silly": 10,
    "blush": 8,
    "gojo": 10,
    "hello kitty": 10
  }
}
```

Then run the batch updater:

```bash
python tools/update_collection.py
```

It automatically checks how many GIFs already exist for each tag and only fetches the missing ones!

---

## 📁 Project Structure

```
tiny-gif/
├── app.py                      # Flask backend (serves web app & collection API)
├── requirements.txt            # Python dependencies (Flask, Pillow, requests, dotenv)
├── .env.example                # GIPHY API key template
├── .env                        # Private environment variables (never committed)
├── .gitignore                  # Git ignore rules
├── README.md                   # Beginner guide & documentation
│
├── data/
│   ├── collection.json         # Master collection metadata
│   └── tags.json               # Batch update target configuration
│
├── gifs/                       # Processed GIF storage organized by category
│   ├── cute/
│   ├── anime/
│   ├── miffy/
│   ├── crying/
│   └── ...
│
├── tools/
│   ├── gif_processor.py        # Discord-safe frame coalescer, resizer & re-encoder
│   ├── add_gifs.py             # CLI tool to search GIPHY & add GIFs
│   └── update_collection.py    # Batch collection updater
│
├── templates/
│   └── index.html              # Kawaii scrapbook single-page layout
│
├── static/
│   ├── css/
│   │   └── style.css           # Soft pastel theme, floating cards, animations
│   └── js/
│       └── app.js              # Live search, tag filters, modal & copy actions
│
└── tests/
    ├── test_processor.py       # Unit tests for GIF processor
    ├── test_app.py             # Unit tests for Flask API & routes
    └── test_cli.py             # Unit tests for CLI tools & deduplication
```

---

## 🧪 Running Automated Tests

Run the test suite with `pytest`:

```bash
python -m pytest tests/ -v
```

---

## 🚀 Deployment Guide

### Deploying to Render, Railway, or Fly.io
1. Create a `Procfile` containing:
   ```text
   web: python app.py
   ```
2. In your hosting dashboard (e.g. Render / Railway):
   - Add environment variable `GIPHY_API_KEY` with your key.
   - Set Build Command: `pip install -r requirements.txt`
   - Set Start Command: `python app.py`

---

## 💖 License & Credits

Built with `♡` for cute tiny animations on the internet.
- Icons: Unicode pastel symbols & stickers
- Fonts: Quicksand, M PLUS Rounded 1c, Gaegu (Google Fonts)
