#!/usr/bin/env python3
"""Bake Postcard-collection plates with the label bar inside the frame.

The finished files stay the exact postcard sizes. A solid black 190px bar
sits inside the bottom of that frame, under the photograph. It is not an
extra strip, and no type is drawn on the picture.

  16:9  1920×1080
  4:5  1080×1350
  9:16 1080×1920

The scenario line on the bar is exactly "Postcard collection". No date,
weather, or timestamp is drawn. Art. 50 text chunks are metadata only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from composite_masters import (
    BAR_H,
    BRAND,
    DISCLOSURE,
    INK,
    INK_DISCLOSURE,
    INK_SCENARIO,
    SIGNATURE_NAME,
    _bbox,
    _measure,
    comment_text,
    fit,
    inject_art50,
    layout_fonts,
)

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = "Postcard collection"
CANVAS = {"16x9": (1920, 1080), "4x5": (1080, 1350), "9x16": (1080, 1920)}
# Solid black, matching the postcard plates. Not the night-master charcoal.
BAR_BLACK = (0, 0, 0)
SERIF = Path("/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf")
# Clear gap between the roman brand line and the script, both on the black.
RIGHT_GAP_PX = 16
INK_PAD = 8


def _ink_columns(layer: Image.Image, bar_top: int) -> list[int]:
    alpha = layer.split()[-1].crop((0, bar_top, layer.width, layer.height))
    raw = alpha.tobytes()
    width = alpha.width
    height = alpha.height
    columns: list[int] = []
    for x in range(width):
        if any(raw[y * width + x] for y in range(height)):
            columns.append(x)
    return columns


def draw_bar_inside(photo: Image.Image, caption: str) -> Image.Image:
    """Place a solid black bar under the photograph, inside the frame.

    The photograph occupies only the area above the bar. Type is drawn on a
    separate layer and must sit entirely inside the black, including the
    script. Nothing is painted over the picture.
    """
    photo = photo.convert("RGB")
    pw, ph = photo.size
    if ph <= BAR_H + 40:
        raise SystemExit(f"plate {pw}x{ph} is too short for a {BAR_H}px inside bar")
    bar_top = ph - BAR_H
    band = photo.crop((0, bar_top, pw, ph))
    if band.getcolors(maxcolors=1) != [(pw * BAR_H, BAR_BLACK)]:
        raise SystemExit("postcard bar must already be solid black under the photo")

    if not SERIF.exists():
        raise SystemExit(f"roman face missing: {SERIF}")

    fonts, gap = layout_fonts(pw, caption, SCENARIO)
    brand_px = max(15, int(round(fonts["brand"].size * 1.05)))
    fonts["brand"] = ImageFont.truetype(str(SERIF), brand_px)
    margin = max(20, int(round(pw * 0.028)))
    col_gap = max(16, int(round(pw * 0.018)))
    right_gap = max(RIGHT_GAP_PX, gap + 8)
    left_rows = [
        (caption, fonts["cap"], INK),
        (SCENARIO, fonts["sc"], INK_SCENARIO),
        (DISCLOSURE, fonts["disc"], INK_DISCLOSURE),
    ]
    roman = (BRAND, fonts["brand"], INK)
    script = (SIGNATURE_NAME, fonts["name"], INK)

    def row_size(text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
        return _measure(font, text)

    def stack_height(rows: list[tuple[str, ImageFont.FreeTypeFont, tuple[int, int, int]]], row_gap: int) -> int:
        total = 0
        for index, (text, font, _ink) in enumerate(rows):
            total += row_size(text, font)[1]
            if index:
                total += row_gap
        return total

    def stack_width(rows: list[tuple[str, ImageFont.FreeTypeFont, tuple[int, int, int]]]) -> int:
        return max(row_size(text, font)[0] for text, font, _ink in rows)

    left_w = stack_width(left_rows)
    right_rows = [roman, script]
    right_w = stack_width(right_rows)
    if margin + left_w + col_gap + right_w + margin > pw:
        raise SystemExit(f"label overflow on {pw}px: caption {caption!r}")
    if stack_height(left_rows, gap) > BAR_H - 2 * INK_PAD:
        raise SystemExit(f"left label taller than the black bar: {caption!r}")
    if stack_height(right_rows, right_gap) > BAR_H - 2 * INK_PAD:
        raise SystemExit(f"signature taller than the black bar: {caption!r}")

    def paint(
        rows: list[tuple[str, ImageFont.FreeTypeFont, tuple[int, int, int]]],
        align: str,
        row_gap: int,
    ) -> Image.Image:
        layer = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        block_h = stack_height(rows, row_gap)
        y = bar_top + max(0, (BAR_H - block_h) // 2)
        block_w = stack_width(rows)
        for text, font, ink in rows:
            text_w, text_h = row_size(text, font)
            left_edge, top_edge, _right, _bottom = _bbox(font, text)
            x = margin if align == "left" else pw - margin - block_w
            if align == "right":
                x = x + (block_w - text_w)
            draw.text((x - left_edge, y - top_edge), text, font=font, fill=ink + (255,), anchor="lt")
            y += text_h + row_gap
        return layer

    left_layer = paint(left_rows, "left", gap)
    right_layer = paint(right_rows, "right", right_gap)
    # Split the right-hand stack so the roman line and the script each have
    # their own ink box. A single centered line would hide a missing gap.
    right_block_h = stack_height(right_rows, right_gap)
    y = bar_top + max(0, (BAR_H - right_block_h) // 2)
    block_w = stack_width(right_rows)
    line_layers: list[Image.Image] = []
    for text, font, ink in right_rows:
        layer = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        text_w, text_h = row_size(text, font)
        left_edge, top_edge, _right, _bottom = _bbox(font, text)
        x = pw - margin - block_w + (block_w - text_w)
        draw.text((x - left_edge, y - top_edge), text, font=font, fill=ink + (255,), anchor="lt")
        line_layers.append(layer)
        y += text_h + right_gap
    roman_layer, script_layer = line_layers
    roman_box = roman_layer.getbbox()
    script_box = script_layer.getbbox()
    if roman_box is None or script_box is None:
        raise SystemExit("roman line and script must both be present")
    if script_box[1] - roman_box[3] < 8:
        raise SystemExit("gap between Jason D's Vision and the script is too small")

    overlay = Image.alpha_composite(left_layer, roman_layer)
    overlay = Image.alpha_composite(overlay, script_layer)
    ink_box = overlay.getbbox()
    if ink_box is None:
        raise SystemExit("postcard label drew no type")
    if ink_box[1] < bar_top + INK_PAD or ink_box[3] > ph - INK_PAD:
        raise SystemExit(
            f"signature leaves the black bar: ink y {ink_box[1]}:{ink_box[3]}, bar {bar_top}:{ph}"
        )
    if ink_box[0] < INK_PAD or ink_box[2] > pw - INK_PAD:
        raise SystemExit(f"signature leaves the side margins: ink x {ink_box[0]}:{ink_box[2]}")

    left_cols = _ink_columns(left_layer, bar_top)
    right_cols = _ink_columns(right_layer, bar_top)
    if not left_cols or not right_cols:
        raise SystemExit(f"label missing a column: {caption!r}")
    if min(right_cols) - max(left_cols) < col_gap:
        raise SystemExit(f"caption and signature collide: {caption!r}")
    photo.paste(overlay, (0, 0), overlay)
    return photo


def bake_one(src: Path, dest: Path, fmt: str, caption: str, comment: str) -> None:
    tw, th = CANVAS[fmt]
    photo_h = th - BAR_H
    photo = fit(Image.open(src), tw, photo_h)
    if photo.size != (tw, photo_h):
        raise SystemExit(f"{src} fit to {photo.size}, expected {(tw, photo_h)}")
    plate = Image.new("RGB", (tw, th), BAR_BLACK)
    plate.paste(photo, (0, 0))
    finished = draw_bar_inside(plate, caption)
    if finished.size != (tw, th):
        raise SystemExit(f"{dest} size changed to {finished.size}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    finished.save(dest, format="PNG", compress_level=9)
    inject_art50(dest, comment)
    with Image.open(dest) as saved:
        saved.load()
        if saved.size != (tw, th):
            raise SystemExit(f"bad size {dest} {saved.size}")
        bar_top = th - BAR_H
        if saved.getpixel((2, th - 1))[:3] != BAR_BLACK:
            raise SystemExit(f"label bar is not black {dest}")
        if saved.getpixel((2, bar_top))[:3] != BAR_BLACK:
            raise SystemExit(f"black bar does not start under the photo {dest}")
        # The photograph keeps its last row. A black photo pixel is allowed;
        # a repainted bar would have moved that row down by the bar height.


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Bake inside-frame postcard plates.")
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--comment-date", default="2026-10-03")
    parser.add_argument("entry_ids", nargs="+")
    args = parser.parse_args(argv)
    catalogue = json.loads((ROOT / "tools" / "catalogue.json").read_text())
    by_id = {row["entry_id"]: row for row in catalogue}
    comment = comment_text(args.comment_date)
    for entry_id in args.entry_ids:
        row = by_id.get(entry_id)
        if row is None:
            raise SystemExit(f"unknown entry {entry_id}")
        stem = entry_id.lower()
        folder = ROOT / "library" / "world" / "Netherlands" / row["folder"]
        for fmt in ("16x9", "4x5", "9x16"):
            src = args.raw_dir / f"{stem}-{fmt}-raw.jpg"
            if not src.exists():
                src = args.raw_dir / f"{stem}-{fmt}-raw.png"
            if not src.exists():
                raise SystemExit(f"missing raw plate {src}")
            dest = folder / f"{stem}-postcard-{fmt}.png"
            bake_one(src, dest, fmt, row["caption"], comment)
            with Image.open(dest) as im:
                print(f"baked {entry_id} {dest.relative_to(ROOT)} {im.size[0]}x{im.size[1]}")


if __name__ == "__main__":
    main()
