#!/usr/bin/env python3
"""Bake Postcard-collection plates with the label bar inside the frame.

The finished files stay the exact postcard sizes. The 190px signature bar
is drawn inside the bottom of that frame. It is not an extra strip.

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

from PIL import Image, ImageDraw

from composite_masters import (
    BAR_BG,
    BAR_H,
    BRAND,
    DISCLOSURE,
    HAIR,
    HAIRLINE,
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


def draw_bar_inside(photo: Image.Image, caption: str) -> Image.Image:
    """Paint the signature bar over the bottom of an exact-size plate."""
    photo = photo.convert("RGB")
    pw, ph = photo.size
    if ph <= BAR_H + 40:
        raise SystemExit(f"plate {pw}x{ph} is too short for a {BAR_H}px inside bar")
    canvas = photo.copy()
    draw = ImageDraw.Draw(canvas)
    bar_top = ph - BAR_H
    draw.rectangle((0, bar_top, pw - 1, bar_top + HAIRLINE - 1), fill=HAIR)
    draw.rectangle((0, bar_top + HAIRLINE, pw - 1, ph - 1), fill=BAR_BG)

    fonts, gap = layout_fonts(pw, caption, SCENARIO)
    margin = max(20, int(round(pw * 0.028)))
    col_gap = max(16, int(round(pw * 0.018)))
    left = [
        (caption, fonts["cap"], INK),
        (SCENARIO, fonts["sc"], INK_SCENARIO),
        (DISCLOSURE, fonts["disc"], INK_DISCLOSURE),
    ]
    right = [
        (BRAND, fonts["brand"], INK),
        (SIGNATURE_NAME, fonts["name"], INK),
    ]

    def stack_height(rows: list[tuple[str, ImageFontFree, tuple[int, int, int]]]) -> int:
        total = 0
        for index, (text, font, _ink) in enumerate(rows):
            total += _measure(font, text)[1]
            if index:
                total += gap
        return total

    def stack_width(rows: list[tuple[str, ImageFontFree, tuple[int, int, int]]]) -> int:
        return max(_measure(font, text)[0] for text, font, _ink in rows)

    left_w = stack_width(left)
    right_w = stack_width(right)
    if margin + left_w + col_gap + right_w + margin > pw:
        raise SystemExit(f"label overflow on {pw}px: caption {caption!r}")

    content_top = bar_top + HAIRLINE
    content_h = BAR_H - HAIRLINE

    def draw_stack(rows: list[tuple[str, ImageFontFree, tuple[int, int, int]]], align: str) -> None:
        block_h = stack_height(rows)
        y = content_top + max(0, (content_h - block_h) // 2)
        block_w = stack_width(rows)
        for text, font, ink in rows:
            text_w, text_h = _measure(font, text)
            left_edge, top_edge, _right, _bottom = _bbox(font, text)
            x = margin if align == "left" else pw - margin - block_w
            if align == "right":
                x = x + (block_w - text_w)
            draw.text((x - left_edge, y - top_edge), text, font=font, fill=ink, anchor="lt")
            y += text_h + gap

    draw_stack(left, "left")
    draw_stack(right, "right")
    return canvas


# Pillow font type is only used for annotations; keep the alias local.
ImageFontFree = object


def bake_one(src: Path, dest: Path, fmt: str, caption: str, comment: str) -> None:
    tw, th = CANVAS[fmt]
    plate = fit(Image.open(src), tw, th)
    if plate.size != (tw, th):
        raise SystemExit(f"{src} fit to {plate.size}, expected {(tw, th)}")
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
        if saved.getpixel((2, th - 1))[:3] != BAR_BG:
            raise SystemExit(f"label bar background {dest}")
        if saved.getpixel((2, th - BAR_H))[:3] != HAIR:
            raise SystemExit(f"hairline missing {dest}")


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
