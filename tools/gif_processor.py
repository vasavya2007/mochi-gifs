"""
tools/gif_processor.py
=======================
Discord-safe GIF Processing Pipeline for tiny.gif.

Solves the classic GIF resizing bug (horizontal slicing / offset corruption)
by properly coalescing all frames onto a full-sized RGBA canvas, respecting
disposal methods, calculating aspect-ratio preserving dimensions in the
50x50 - 90x90 range, preserving frame durations and loop counts, and
cleanly quantizing and re-encoding.
"""

from __future__ import annotations
import os
import io
import logging
from typing import Tuple, List, Optional, Dict, Any
from PIL import Image, ImageSequence, ImageOps

logger = logging.getLogger("gif_processor")


def calculate_dimensions(
    orig_w: int,
    orig_h: int,
    max_dim: int = 80,
    min_dim: int = 50,
    max_bound: int = 90
) -> Tuple[int, int]:
    """
    Calculate target dimensions preserving the original aspect ratio
    within the configured range (50x50 to 90x90 px).
    """
    if orig_w <= 0 or orig_h <= 0:
        return max_dim, max_dim

    aspect = orig_w / orig_h

    # Scale based on the largest dimension to fit within max_bound
    target_max = min(max_bound, max_dim)

    if orig_w >= orig_h:
        # Wider than tall
        new_w = target_max
        new_h = int(round(target_max / aspect))
        if new_h < min_dim and orig_h >= min_dim:
            # If height dropped below min_dim but original was larger, adjust proportionally
            new_h = min_dim
            new_w = int(round(min_dim * aspect))
            if new_w > max_bound:
                new_w = max_bound
    else:
        # Taller than wide
        new_h = target_max
        new_w = int(round(target_max * aspect))
        if new_w < min_dim and orig_w >= min_dim:
            new_w = min_dim
            new_h = int(round(min_dim / aspect))
            if new_h > max_bound:
                new_h = max_bound

    new_w = max(1, min(max_bound, new_w))
    new_h = max(1, min(max_bound, new_h))

    return new_w, new_h


def coalesce_frames(im: Image.Image) -> Tuple[List[Image.Image], List[int], int]:
    """
    Extract and fully coalesce every frame in an animated GIF.
    
    GIF animation relies on partial delta updates and disposal methods:
      0: Unspecified
      1: Do not dispose (leave current frame on canvas)
      2: Restore to background (clear frame rect to transparent)
      3: Restore to previous (revert canvas to state prior to frame)

    By compositing each frame onto a complete RGBA canvas, we eliminate
    all frame offset, ghosting, and slicing bugs during subsequent resizing.
    """
    canvas_w, canvas_h = im.size
    coalesced_frames: List[Image.Image] = []
    durations: List[int] = []

    # Get loop count (0 = infinite loop)
    loop = im.info.get("loop", 0)

    current_canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    prev_canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    prev_disposal = 0
    prev_bbox = (0, 0, canvas_w, canvas_h)

    for frame in ImageSequence.Iterator(im):
        # Frame duration in milliseconds (default 100ms if 0 or missing)
        duration = frame.info.get("duration", 100)
        if duration <= 0:
            duration = 100
        durations.append(duration)

        # Disposal method for this frame
        disposal = frame.info.get("disposal", 2)

        # Revert/clear based on PREVIOUS frame's disposal method
        if prev_disposal == 2:
            # Restore to background (clear previous frame's bounding box)
            clear_box = Image.new("RGBA", (prev_bbox[2] - prev_bbox[0], prev_bbox[3] - prev_bbox[1]), (0, 0, 0, 0))
            current_canvas.paste(clear_box, (prev_bbox[0], prev_bbox[1]))
        elif prev_disposal == 3:
            # Restore to previous canvas
            current_canvas = prev_canvas.copy()

        # Save snapshot of canvas before applying current frame (for disposal 3)
        prev_canvas = current_canvas.copy()

        # Get frame bounding box offset if present
        box = (0, 0, canvas_w, canvas_h)
        if hasattr(frame, "tile") and frame.tile:
            # frame.tile format: [('gif', (x0, y0, x1, y1), offset, flags)]
            try:
                box = frame.tile[0][1]
            except Exception:
                box = (0, 0, frame.width, frame.height)

        prev_bbox = box
        prev_disposal = disposal

        # Convert frame to RGBA
        frame_rgba = frame.convert("RGBA")

        # Paste onto current canvas with alpha mask
        if box == (0, 0, canvas_w, canvas_h):
            current_canvas.paste(frame_rgba, (0, 0), frame_rgba)
        else:
            current_canvas.paste(frame_rgba, (box[0], box[1]), frame_rgba)

        # Store complete reconstructed frame snapshot
        coalesced_frames.append(current_canvas.copy())

    if not coalesced_frames:
        coalesced_frames = [im.convert("RGBA")]
        durations = [100]

    return coalesced_frames, durations, loop


def rgba_to_gif_frame(frame: Image.Image, transparent_color: Tuple[int, int, int] = (255, 0, 255)) -> Image.Image:
    """
    Quantize an RGBA frame to an 8-bit palette GIF frame preserving alpha transparency.
    """
    # Separate alpha channel
    alpha = frame.split()[3]
    
    # Check if frame actually contains transparent pixels
    has_transparency = False
    extrema = alpha.getextrema()
    if extrema[0] < 128:
        has_transparency = True

    if not has_transparency:
        # Completely opaque frame: convert directly to palette
        rgb_frame = frame.convert("RGB")
        p_frame = rgb_frame.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
        return p_frame

    # Create binary transparency mask (pixels with alpha < 128 are transparent)
    mask = Image.eval(alpha, lambda a: 255 if a < 128 else 0)

    # Convert RGB frame with dummy background color for transparent pixels
    rgb_frame = Image.new("RGB", frame.size, transparent_color)
    rgb_frame.paste(frame, (0, 0), alpha)

    # Quantize to 255 colors leaving slot for transparency
    p_frame = rgb_frame.quantize(colors=255, method=Image.Quantize.MEDIANCUT)

    # Find the palette index closest to the transparent key color or reserve 255
    palette = p_frame.getpalette()
    transparent_idx = 255
    # Assign the transparent key color at index 255 in palette
    if palette:
        while len(palette) < 768:
            palette.append(0)
        palette[255 * 3] = transparent_color[0]
        palette[255 * 3 + 1] = transparent_color[1]
        palette[255 * 3 + 2] = transparent_color[2]
        p_frame.putpalette(palette)

    # Apply mask to set transparent pixels to transparent_idx
    p_frame.paste(transparent_idx, mask)
    p_frame.info["transparency"] = transparent_idx

    return p_frame


def process_gif(
    input_source: str | bytes | io.BytesIO,
    output_path: Optional[str] = None,
    max_dim: int = 80,
    min_dim: int = 50,
    max_bound: int = 90
) -> Dict[str, Any]:
    """
    Process a GIF (from file path, raw bytes, or BytesIO):
    1. Read and validate
    2. Discord-safe frame coalescing
    3. Aspect-ratio preserving resize (50x50 to 90x90 range)
    4. Re-quantize and re-encode to output file or memory buffer.
    
    Returns metadata dictionary:
    {
      "width": int,
      "height": int,
      "frame_count": int,
      "file_size": int,
      "loop": int,
      "durations": List[int]
    }
    """
    # Open image
    if isinstance(input_source, (bytes, bytearray)):
        input_stream = io.BytesIO(input_source)
    elif isinstance(input_source, io.BytesIO):
        input_stream = input_source
    else:
        with open(input_source, "rb") as f:
            input_stream = io.BytesIO(f.read())

    im = Image.open(input_stream)
    orig_w, orig_h = im.size

    # Calculate target dimensions
    target_w, target_h = calculate_dimensions(
        orig_w, orig_h,
        max_dim=max_dim,
        min_dim=min_dim,
        max_bound=max_bound
    )

    # Coalesce all frames
    rgba_frames, durations, loop = coalesce_frames(im)

    # Resize all coalesced frames using high-quality Lanczos resampling
    resized_frames = []
    for f in rgba_frames:
        resized_frame = f.resize((target_w, target_h), Image.Resampling.LANCZOS)
        resized_frames.append(resized_frame)

    # Convert resized RGBA frames to palette GIF frames
    gif_frames = [rgba_to_gif_frame(f) for f in resized_frames]

    # Save animated GIF
    out_buffer = io.BytesIO()
    if len(gif_frames) == 1:
        gif_frames[0].save(
            out_buffer,
            format="GIF",
            save_all=False,
            optimize=False
        )
    else:
        gif_frames[0].save(
            out_buffer,
            format="GIF",
            save_all=True,
            append_images=gif_frames[1:],
            duration=durations,
            loop=loop,
            disposal=2,  # Restore to background per frame for clean discord/web playback
            optimize=False
        )

    processed_bytes = out_buffer.getvalue()
    file_size = len(processed_bytes)

    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "wb") as f_out:
            f_out.write(processed_bytes)

    return {
        "width": target_w,
        "height": target_h,
        "original_width": orig_w,
        "original_height": orig_h,
        "frame_count": len(gif_frames),
        "file_size": file_size,
        "loop": loop,
        "durations": durations,
        "bytes": processed_bytes
    }
