#!/usr/bin/env python3
"""Composite exact on-image text and EU AI Act Art. 50 PNG chunks onto masters."""

from __future__ import annotations

import json
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

ROOT = Path(__file__).resolve().parents[1]
RAW = Path("/opt/cursor/artifacts/assets")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

TITLE = "Jason D's Vision — AI-generated artistic interpretation"
DESCRIPTION = (
    "AI-generated artistic interpretation from the Jason D's Vision Netherlands gallery. "
    "Created with generative AI; not a photograph."
)
COPYRIGHT = "Jason D's Vision — AI-generated content"
SOFTWARE = "Jason D's Vision library pipeline"
COMMENT = (
    "EU AI Act Art. 50 transparency note: this image is AI-generated content. "
    "Machine-readable disclosure embedded 2026-09-24."
)
SIGNATURE = "Jason D\u2019s Vision"
DISCLOSURE = "AI-generated artistic interpretation \u00b7 Not a photograph."


def pnginfo() -> PngImagePlugin.PngInfo:
    info = PngImagePlugin.PngInfo()
    info.add_itxt("Title", TITLE)
    info.add_text("Description", DESCRIPTION)
    info.add_itxt("Copyright", COPYRIGHT)
    info.add_text("Software", SOFTWARE)
    info.add_text("Comment", COMMENT)
    return info


def fit(im: Image.Image, tw: int, th: int) -> Image.Image:
    im = im.convert("RGB")
    w, h = im.size
    target = tw / th
    current = w / h
    if current > target:
        new_w = int(round(h * target))
        left = (w - new_w) // 2
        im = im.crop((left, 0, left + new_w, h))
    elif current < target:
        new_h = int(round(w / target))
        top = max(0, (h - new_h) // 2)
        im = im.crop((0, top, w, top + new_h))
    return im.resize((tw, th), Image.Resampling.LANCZOS)


def draw_text(base: Image.Image, caption: str, scenario: str) -> Image.Image:
    im = base.convert("RGBA")
    w, h = im.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    grad = ImageDraw.Draw(overlay)
    start = int(h * 0.68)
    for y in range(start, h):
        t = (y - start) / max(1, (h - start))
        alpha = int(190 * (t ** 1.2))
        grad.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))
    im = Image.alpha_composite(im, overlay)

    cap_size = round(w * 0.016)
    sc_size = round(w * 0.012)
    disc_size = round(w * 0.010)
    sig_size = round(w * 0.018)
    cap_font = ImageFont.truetype(FONT_BOLD, cap_size)
    sc_font = ImageFont.truetype(FONT, sc_size)
    disc_font = ImageFont.truetype(FONT, disc_size)
    sig_font = ImageFont.truetype(FONT_BOLD, sig_size)

    def measure(text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
        box = font.getbbox(text)
        return box[2] - box[0], box[3] - box[1]

    cap_w, cap_h = measure(caption, cap_font)
    sc_w, sc_h = measure(scenario, sc_font)
    disc_w, disc_h = measure(DISCLOSURE, disc_font)
    sig_w, sig_h = measure(SIGNATURE, sig_font)

    margin_x = round(w * 0.028)
    margin_b = round(h * 0.030)
    gap = round(w * 0.006)

    y_disc = h - margin_b - disc_h
    y_sc = y_disc - gap - sc_h
    y_cap = y_sc - gap - cap_h
    sig_x = w - margin_x - sig_w
    sig_y = y_cap + max(0, (cap_h - sig_h) // 2)

    draw = ImageDraw.Draw(im)

    def shadow_text(x: int, y: int, text: str, font: ImageFont.FreeTypeFont) -> None:
        draw.text((x + 1, y + 1), text, font=font, fill=(0, 0, 0, 170))
        draw.text((x, y), text, font=font, fill=(255, 255, 255, 235))

    shadow_text(margin_x, y_cap, caption, cap_font)
    shadow_text(margin_x, y_sc, scenario, sc_font)
    shadow_text(margin_x, y_disc, DISCLOSURE, disc_font)
    shadow_text(sig_x, sig_y, SIGNATURE, sig_font)
    return im.convert("RGB")


def save_master(im: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, format="PNG", pnginfo=pnginfo(), compress_level=9)


def read_text_chunks(path: Path) -> dict[str, tuple[str, str]]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(f"not a png: {path}")
    i = 8
    found: dict[str, tuple[str, str]] = {}
    while i + 8 <= len(data):
        length = struct.unpack(">I", data[i : i + 4])[0]
        ctype = data[i + 4 : i + 8]
        chunk = data[i + 8 : i + 8 + length]
        if ctype == b"tEXt":
            key, value = chunk.split(b"\x00", 1)
            found[key.decode("latin-1")] = ("tEXt", value.decode("latin-1"))
        elif ctype == b"iTXt":
            key, rest = chunk.split(b"\x00", 1)
            comp_flag = rest[0]
            rest = rest[2:]  # skip comp method
            lang, rest = rest.split(b"\x00", 1)
            tkey, text = rest.split(b"\x00", 1)
            if comp_flag:
                import zlib

                text = zlib.decompress(text)
            found[key.decode("latin-1")] = ("iTXt", text.decode("utf-8"))
        i += 12 + length
        if ctype == b"IEND":
            break
    return found


def composite_one(entry_id: str, folder: str, caption: str, scenario_label: str) -> tuple[Path, Path]:
    scenario = f"Scenario: {scenario_label}"
    raw16 = RAW / f"{entry_id.lower()}-16x9-raw.png"
    raw45 = RAW / f"{entry_id.lower()}-4x5-raw.png"
    if not raw16.exists() or not raw45.exists():
        raise SystemExit(f"missing raw for {entry_id}")
    out_dir = ROOT / "library" / "world" / "Netherlands" / folder
    out16 = out_dir / f"{entry_id.lower()}-16x9.png"
    out45 = out_dir / f"{entry_id.lower()}-4x5.png"
    save_master(draw_text(fit(Image.open(raw16), 1920, 1080), caption, scenario), out16)
    save_master(draw_text(fit(Image.open(raw45), 864, 1080), caption, scenario), out45)
    for path, wh in ((out16, (1920, 1080)), (out45, (864, 1080))):
        with Image.open(path) as im:
            if im.size != wh:
                raise SystemExit(f"bad size {path} {im.size}")
        chunks = read_text_chunks(path)
        expected = {
            "Title": ("iTXt", TITLE),
            "Description": ("tEXt", DESCRIPTION),
            "Copyright": ("iTXt", COPYRIGHT),
            "Software": ("tEXt", SOFTWARE),
            "Comment": ("tEXt", COMMENT),
        }
        for key, val in expected.items():
            if chunks.get(key) != val:
                raise SystemExit(f"metadata mismatch {path} {key}: {chunks.get(key)!r}")
    return out16, out45


def main() -> None:
    import sys

    catalogue = json.loads((ROOT / "tools" / "catalogue.json").read_text())
    weather_dir = ROOT / "evidence" / "weather"
    wanted = sys.argv[1:] or [row["entry_id"] for row in catalogue]
    for row in catalogue:
        if row["entry_id"] not in wanted:
            continue
        weather = json.loads((weather_dir / f"{row['entry_id']}.json").read_text())
        out16, out45 = composite_one(
            row["entry_id"], row["folder"], row["caption"], weather["scenario_label"]
        )
        print(f"composited {row['entry_id']} {out16.name} {out45.name}")


if __name__ == "__main__":
    main()
