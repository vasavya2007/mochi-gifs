"""
tests/test_processor.py
=======================
Tests for GIF processor: coalescing, proportional resizing, transparency,
and metadata output.
"""

import os
import io
import pytest
from PIL import Image, ImageDraw
import sys

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tools.gif_processor import (
    calculate_dimensions,
    coalesce_frames,
    rgba_to_gif_frame,
    process_gif,
)


def create_sample_animated_gif(width=200, height=150, num_frames=3) -> bytes:
    """Create an in-memory test animated GIF with moving shapes and transparency."""
    frames = []
    for i in range(num_frames):
        im = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(im)
        # Draw pastel circle moving across
        x = 20 + i * 40
        y = 20 + i * 20
        draw.ellipse([x, y, x + 60, y + 60], fill=(255, 182, 193, 255), outline=(255, 105, 180, 255))
        # Draw cute little heart or square
        draw.rectangle([x + 20, y + 20, x + 40, y + 40], fill=(230, 230, 250, 255))
        frames.append(im)

    out = io.BytesIO()
    frames[0].save(
        out,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=120,
        loop=0,
        disposal=2
    )
    return out.getvalue()


def test_calculate_dimensions_wide():
    # 200x100 (2:1 aspect ratio) -> target range 50 to 90
    w, h = calculate_dimensions(200, 100, max_dim=80, min_dim=50, max_bound=90)
    assert w <= 90
    assert h >= 40 and h <= 90
    assert w >= h  # Preserves wide orientation


def test_calculate_dimensions_tall():
    # 100x200 (1:2 aspect ratio) -> target range 50 to 90
    w, h = calculate_dimensions(100, 200, max_dim=80, min_dim=50, max_bound=90)
    assert h <= 90
    assert w >= 40 and w <= 90
    assert h >= w  # Preserves tall orientation


def test_calculate_dimensions_square():
    # 300x300 (1:1) -> exactly 80x80
    w, h = calculate_dimensions(300, 300, max_dim=80, min_dim=50, max_bound=90)
    assert w == 80
    assert h == 80


def test_process_gif_in_memory():
    gif_bytes = create_sample_animated_gif(width=240, height=180, num_frames=4)
    result = process_gif(gif_bytes, max_dim=80)

    assert result["frame_count"] == 4
    assert result["width"] <= 90
    assert result["height"] <= 90
    assert result["file_size"] > 0
    assert len(result["durations"]) == 4

    # Verify the output can be reopened by PIL as an animated GIF
    reopened = Image.open(io.BytesIO(result["bytes"]))
    assert reopened.is_animated
    assert reopened.n_frames == 4
    assert reopened.size == (result["width"], result["height"])


def test_process_gif_to_file(tmp_path):
    gif_bytes = create_sample_animated_gif(width=160, height=160, num_frames=2)
    out_file = tmp_path / "test_out.gif"
    
    result = process_gif(gif_bytes, output_path=str(out_file), max_dim=70)
    
    assert os.path.exists(out_file)
    assert os.path.getsize(out_file) == result["file_size"]
    assert result["width"] == 70
    assert result["height"] == 70
