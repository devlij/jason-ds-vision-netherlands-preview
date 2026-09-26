#!/usr/bin/env python3
"""Bake the label-bar finishing standard from a durable pre-text photograph.

The photograph stays 100% pure: no tint, scrim, shadow, or type over the art.
A uniform 190px bar is added under the photo, with a 2px hairline between them.

Masters
  16:9  1920×1270   photo 1920×1080
  4:5    864×1270   photo 864×1080
  9:16  1080×2110   photo 1080×1920

The primary pre-text is kept at
  library/pretext/Netherlands/<folder>/<entry>-16x9.png
Optional honest re-frames (same viewpoint, still pure photos) live beside it as
  <entry>-4x5.png and <entry>-9x16.png.
When a format-specific source is absent, that master is a center crop of the
primary pre-text, resized with Lanczos. Cropping a finished scrim master is
not a source.

EU AI Act Art. 50: five PNG text chunks are inserted before IEND after the
image is encoded, so IDAT is not rewritten to attach the metadata.
"""

from __future__ import annotations

import argparse
import json
import struct
import zlib
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SANS = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
SANS_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
ALLURA = Path(__file__).resolve().parent / "fonts" / "Allura-Regular.ttf"

# Straight apostrophe (U+0027) and em dash (U+2014). Character-for-character.
TITLE = "Jason D\u0027s Vision \u2014 AI-generated artistic interpretation"
DESCRIPTION = (
    "AI-generated artistic interpretation from the Jason D\u0027s Vision Netherlands gallery. "
    "Created with generative AI; not a photograph."
)
COPYRIGHT = "Jason D\u0027s Vision \u2014 AI-generated content"
SOFTWARE = "Jason D\u0027s Vision library pipeline"
COMMENT = (
    "EU AI Act Art. 50 transparency note: this image is AI-generated content. "
    "Machine-readable disclosure embedded 2026-09-24."
)

# On-image signature keeps the curly apostrophe (U+2019).
BRAND = "Jason D\u2019s Vision"
SIGNATURE_NAME = "Jason A. Devlin"
DISCLOSURE = "AI-generated artistic interpretation \u00b7 Not a photograph."

BAR_H = 190
HAIRLINE = 2
BAR_BG = (0x0E, 0x0E, 0x12)
HAIR = (0xE4, 0xE4, 0xEA)
INK = (255, 255, 255)
INK_SCENARIO = (214, 214, 222)
INK_DISCLOSURE = (176, 176, 186)

PHOTO = {"16x9": (1920, 1080), "4x5": (864, 1080), "9x16": (1080, 1920)}
CANVAS = {"16x9": (1920, 1270), "4x5": (864, 1270), "9x16": (1080, 2110)}
PNG_SIG = b"\x89PNG\r\n\x1a\n"
ART50_KEYS = ("Title", "Description", "Copyright", "Software", "Comment")

# Cosmo night+daylight, and Cosmo-approved manifests. Refused unless asked.
LOCKED_RANGES = (("NL-01-001", "NL-01-010"), ("NL-01-026", "NL-01-055"))


def is_locked(entry_id: str) -> bool:
    return any(lo <= entry_id <= hi for lo, hi in LOCKED_RANGES)


def pretext_paths(folder: str, entry_id: str) -> dict[str, Path]:
    directory = ROOT / "library" / "pretext" / "Netherlands" / folder
    stem = entry_id.lower()
    return {
        "16x9": directory / f"{stem}-16x9.png",
        "4x5": directory / f"{stem}-4x5.png",
        "9x16": directory / f"{stem}-9x16.png",
    }


def master_paths(folder: str, entry_id: str) -> dict[str, Path]:
    directory = ROOT / "library" / "world" / "Netherlands" / folder
    stem = entry_id.lower()
    return {
        "16x9": directory / f"{stem}-16x9.png",
        "4x5": directory / f"{stem}-4x5.png",
        "9x16": directory / f"{stem}-9x16.png",
    }


def _chunk(ctype: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(ctype + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + ctype + data + struct.pack(">I", crc)


def _text_chunk(key: str, value: str) -> bytes:
    data = key.encode("latin-1") + b"\x00" + value.encode("latin-1")
    return _chunk(b"tEXt", data)


def _itxt_chunk(key: str, value: str) -> bytes:
    data = (
        key.encode("latin-1")
        + b"\x00"
        + b"\x00"  # compression flag: uncompressed
        + b"\x00"  # compression method
        + b"\x00"  # language tag
        + b"\x00"  # translated keyword
        + value.encode("utf-8")
    )
    return _chunk(b"iTXt", data)


def art50_chunks() -> list[bytes]:
    return [
        _itxt_chunk("Title", TITLE),
        _text_chunk("Description", DESCRIPTION),
        _itxt_chunk("Copyright", COPYRIGHT),
        _text_chunk("Software", SOFTWARE),
        _text_chunk("Comment", COMMENT),
    ]


def inject_art50(path: Path) -> None:
    """Insert the five Art. 50 chunks before IEND without touching IDAT."""
    data = path.read_bytes()
    if data[:8] != PNG_SIG:
        raise SystemExit(f"not a png: {path}")
    out = [data[:8]]
    i = 8
    inserted = False
    while i + 12 <= len(data):
        length = struct.unpack(">I", data[i : i + 4])[0]
        ctype = data[i + 4 : i + 8]
        end = i + 12 + length
        if end > len(data):
            raise SystemExit(f"truncated png: {path}")
        payload = data[i + 8 : i + 8 + length]
        if ctype in (b"tEXt", b"iTXt", b"zTXt"):
            key = payload.split(b"\x00", 1)[0].decode("latin-1")
            if key in ART50_KEYS:
                i = end
                continue
        if ctype == b"IEND":
            out.extend(art50_chunks())
            out.append(data[i:end])
            inserted = True
            i = end
            break
        out.append(data[i:end])
        i = end
    if not inserted:
        raise SystemExit(f"IEND missing: {path}")
    path.write_bytes(b"".join(out))


def read_text_chunks(path: Path) -> dict[str, tuple[str, str]]:
    data = path.read_bytes()
    if data[:8] != PNG_SIG:
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
            rest = rest[2:]
            _lang, rest = rest.split(b"\x00", 1)
            _tkey, text = rest.split(b"\x00", 1)
            if comp_flag:
                text = zlib.decompress(text)
            found[key.decode("latin-1")] = ("iTXt", text.decode("utf-8"))
        i += 12 + length
        if ctype == b"IEND":
            break
    return found


def expected_art50() -> dict[str, tuple[str, str]]:
    return {
        "Title": ("iTXt", TITLE),
        "Description": ("tEXt", DESCRIPTION),
        "Copyright": ("iTXt", COPYRIGHT),
        "Software": ("tEXt", SOFTWARE),
        "Comment": ("tEXt", COMMENT),
    }


def assert_art50(path: Path) -> None:
    chunks = read_text_chunks(path)
    for key, val in expected_art50().items():
        if chunks.get(key) != val:
            raise SystemExit(f"metadata mismatch {path} {key}: {chunks.get(key)!r}")


def fit(im: Image.Image, tw: int, th: int) -> Image.Image:
    """Center-crop to the target aspect, then Lanczos to the exact photo size."""
    im = im.convert("RGB")
    w, h = im.size
    target = tw / th
    current = w / h
    if abs(current - target) > 1e-6:
        if current > target:
            new_w = int(round(h * target))
            left = (w - new_w) // 2
            im = im.crop((left, 0, left + new_w, h))
        else:
            new_h = int(round(w / target))
            top = max(0, (h - new_h) // 2)
            im = im.crop((0, top, w, top + new_h))
    if im.size != (tw, th):
        im = im.resize((tw, th), Image.Resampling.LANCZOS)
    return im


def _bbox(font: ImageFont.FreeTypeFont, text: str) -> tuple[int, int, int, int]:
    return font.getbbox(text, anchor="lt")


def _measure(font: ImageFont.FreeTypeFont, text: str) -> tuple[int, int]:
    left, top, right, bottom = _bbox(font, text)
    return right - left, bottom - top


def _fonts(scale: float) -> dict[str, ImageFont.FreeTypeFont]:
    def px(size: float, floor: int) -> int:
        return max(floor, int(round(size * scale)))

    return {
        "cap": ImageFont.truetype(str(SANS_BOLD), px(28, 15)),
        "sc": ImageFont.truetype(str(SANS), px(18, 12)),
        "disc": ImageFont.truetype(str(SANS), px(16, 11)),
        "brand": ImageFont.truetype(str(SANS), px(20, 13)),
        "name": ImageFont.truetype(str(ALLURA), px(46, 28)),
    }


def _stack_size(lines: list[tuple[str, ImageFont.FreeTypeFont]], gap: int) -> tuple[int, int]:
    width = 0
    height = 0
    for index, (text, font) in enumerate(lines):
        w, h = _measure(font, text)
        width = max(width, w)
        height += h
        if index:
            height += gap
    return width, height


def layout_fonts(width: int, caption: str, scenario: str) -> tuple[dict[str, ImageFont.FreeTypeFont], int]:
    if not ALLURA.exists():
        raise SystemExit(f"Allura font missing: {ALLURA}")
    scale = 1.0 if width >= 1600 else (0.9 if width >= 1000 else 0.78)
    for _ in range(18):
        fonts = _fonts(scale)
        gap = max(4, int(round(6 * scale)))
        margin = max(20, int(round(width * 0.028)))
        col_gap = max(16, int(round(width * 0.018)))
        left_w, left_h = _stack_size(
            [(caption, fonts["cap"]), (scenario, fonts["sc"]), (DISCLOSURE, fonts["disc"])],
            gap,
        )
        right_w, right_h = _stack_size(
            [(BRAND, fonts["brand"]), (SIGNATURE_NAME, fonts["name"])],
            gap,
        )
        content_h = BAR_H - HAIRLINE
        if (
            margin * 2 + col_gap + left_w + right_w <= width
            and left_h <= content_h - 16
            and right_h <= content_h - 12
        ):
            return fonts, gap
        scale *= 0.94
    raise SystemExit(f"label text does not fit a {width}px bar")


def draw_label_bar(photo: Image.Image, caption: str, scenario_label: str) -> Image.Image:
    photo = photo.convert("RGB")
    pw, ph = photo.size
    canvas = Image.new("RGB", (pw, ph + BAR_H), BAR_BG)
    canvas.paste(photo, (0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, ph, pw - 1, ph + HAIRLINE - 1), fill=HAIR)

    fonts, gap = layout_fonts(pw, caption, f"Scenario: {scenario_label}")
    margin = max(20, int(round(pw * 0.028)))
    col_gap = max(16, int(round(pw * 0.018)))
    scenario = f"Scenario: {scenario_label}"
    left = [
        (caption, fonts["cap"], INK),
        (scenario, fonts["sc"], INK_SCENARIO),
        (DISCLOSURE, fonts["disc"], INK_DISCLOSURE),
    ]
    right = [
        (BRAND, fonts["brand"], INK),
        (SIGNATURE_NAME, fonts["name"], INK),
    ]

    def stack_height(rows: list[tuple[str, ImageFont.FreeTypeFont, tuple[int, int, int]]]) -> int:
        total = 0
        for index, (text, font, _ink) in enumerate(rows):
            total += _measure(font, text)[1]
            if index:
                total += gap
        return total

    def stack_width(rows: list[tuple[str, ImageFont.FreeTypeFont, tuple[int, int, int]]]) -> int:
        return max(_measure(font, text)[0] for text, font, _ink in rows)

    left_w = stack_width(left)
    right_w = stack_width(right)
    if margin + left_w + col_gap + right_w + margin > pw:
        raise SystemExit(f"label overflow on {pw}px: caption {caption!r}")

    content_top = ph + HAIRLINE
    content_h = BAR_H - HAIRLINE

    def draw_stack(rows: list[tuple[str, ImageFont.FreeTypeFont, tuple[int, int, int]]], x_align: str) -> None:
        block_h = stack_height(rows)
        y = content_top + max(0, (content_h - block_h) // 2)
        block_w = stack_width(rows)
        for text, font, ink in rows:
            text_w, text_h = _measure(font, text)
            left_edge, top_edge, _right, _bottom = _bbox(font, text)
            x = margin if x_align == "left" else pw - margin - block_w
            if x_align == "right":
                x = x + (block_w - text_w)
            draw.text((x - left_edge, y - top_edge), text, font=font, fill=ink, anchor="lt")
            y += text_h + gap

    draw_stack(left, "left")
    draw_stack(right, "right")
    return canvas


def _place(src: Path, dest: Path) -> None:
    """Store a pure photo as a durable PNG. JPEG input is converted, not cropped."""
    if not src.exists():
        raise SystemExit(f"missing pre-text: {src}")
    if src.resolve() == dest.resolve():
        if dest.read_bytes()[:8] != PNG_SIG:
            raise SystemExit(f"durable pre-text is not a PNG: {dest}")
        return
    im = Image.open(src).convert("RGB")
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, format="PNG", compress_level=9)
    if dest.read_bytes()[:8] != PNG_SIG:
        raise SystemExit(f"failed to write pre-text PNG: {dest}")


def _photo_for(fmt: str, paths: dict[str, Path]) -> Image.Image:
    tw, th = PHOTO[fmt]
    specific = paths.get(fmt)
    if specific is not None and specific.exists():
        return fit(Image.open(specific), tw, th)
    primary = paths["16x9"]
    if not primary.exists():
        raise SystemExit(f"missing primary pre-text: {primary}")
    return fit(Image.open(primary), tw, th)


def save_master(im: Image.Image, path: Path, photo: Image.Image) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, format="PNG", compress_level=9)
    inject_art50(path)
    with Image.open(path) as saved:
        saved.load()
        if saved.size != im.size:
            raise SystemExit(f"bad size {path} {saved.size}")
        top = saved.crop((0, 0, photo.width, photo.height)).convert("RGB")
        if ImageChops.difference(top, photo).getbbox() is not None:
            raise SystemExit(f"photo pixels were altered: {path}")
        bar_px = saved.getpixel((2, saved.height - 1))
        if bar_px[:3] != BAR_BG:
            raise SystemExit(f"label bar background {path} {bar_px}")
        hair_px = saved.getpixel((2, photo.height))
        if hair_px[:3] != HAIR:
            raise SystemExit(f"hairline missing {path} {hair_px}")
    assert_art50(path)


def composite_one(
    entry_id: str,
    folder: str,
    caption: str,
    scenario_label: str,
    source: Path | None = None,
    source_4x5: Path | None = None,
    source_9x16: Path | None = None,
    allow_locked: bool = False,
) -> tuple[Path, Path, Path]:
    if is_locked(entry_id) and not allow_locked:
        raise SystemExit(f"{entry_id} is Cosmo-locked; refusing to rebake")
    if "Scenario:" in scenario_label:
        raise SystemExit(f"{entry_id} scenario_label should not include the Scenario prefix")
    paths = pretext_paths(folder, entry_id)
    if source is not None:
        _place(source, paths["16x9"])
    if source_4x5 is not None:
        _place(source_4x5, paths["4x5"])
    if source_9x16 is not None:
        _place(source_9x16, paths["9x16"])
    if not paths["16x9"].exists():
        raise SystemExit(
            f"missing durable pre-text for {entry_id}: {paths['16x9']}. "
            "Regenerate a pure photo. Do not crop a finished master."
        )
    photos = {fmt: _photo_for(fmt, paths) for fmt in ("16x9", "4x5", "9x16")}
    outs = master_paths(folder, entry_id)
    for fmt, photo in photos.items():
        if photo.size != PHOTO[fmt]:
            raise SystemExit(f"{entry_id} {fmt} photo {photo.size}")
        finished = draw_label_bar(photo, caption, scenario_label)
        if finished.size != CANVAS[fmt]:
            raise SystemExit(f"{entry_id} {fmt} canvas {finished.size}")
        save_master(finished, outs[fmt], photo)
    return outs["16x9"], outs["4x5"], outs["9x16"]


def load_catalogue_row(entry_id: str) -> dict:
    catalogue = json.loads((ROOT / "tools" / "catalogue.json").read_text())
    for row in catalogue:
        if row["entry_id"] == entry_id:
            return row
    raise SystemExit(f"unknown entry {entry_id}")


def load_scenario(entry_id: str) -> str:
    weather = json.loads((ROOT / "evidence" / "weather" / f"{entry_id}.json").read_text())
    label = weather["scenario_label"]
    if not label:
        raise SystemExit(f"{entry_id} has no scenario_label")
    return label


def check_entry(entry_id: str) -> None:
    row = load_catalogue_row(entry_id)
    outs = master_paths(row["folder"], entry_id)
    paths = pretext_paths(row["folder"], entry_id)
    if not paths["16x9"].exists():
        raise SystemExit(f"missing pre-text {paths['16x9']}")
    for fmt, path in outs.items():
        if not path.exists():
            raise SystemExit(f"missing master {path}")
        with Image.open(path) as im:
            if im.size != CANVAS[fmt]:
                raise SystemExit(f"bad size {path} {im.size}")
        assert_art50(path)
        print(f"ok {entry_id} {fmt} {path.relative_to(ROOT)} {CANVAS[fmt][0]}x{CANVAS[fmt][1]}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Bake label-bar masters from a durable pre-text PNG.")
    parser.add_argument("entry_ids", nargs="*", help="Catalogue ids, for example NL-01-100")
    parser.add_argument("--source", type=Path, help="Primary pure-photo PNG. Copied into library/pretext.")
    parser.add_argument("--source-4x5", type=Path, dest="source_4x5", help="Optional pure 4:5 re-frame.")
    parser.add_argument("--source-9x16", type=Path, dest="source_9x16", help="Optional pure 9:16 re-frame.")
    parser.add_argument(
        "--allow-locked",
        action="store_true",
        help="Permit Cosmo-locked ids NL-01-001–010 and NL-01-026–055.",
    )
    parser.add_argument("--check", action="store_true", help="Verify pre-text, sizes, and Art. 50 chunks.")
    args = parser.parse_args(argv)
    if not args.entry_ids:
        raise SystemExit("pass one or more entry ids")
    if args.source and len(args.entry_ids) != 1:
        raise SystemExit("--source applies to a single entry id")
    if args.check and not any((args.source, args.source_4x5, args.source_9x16)):
        for entry_id in args.entry_ids:
            check_entry(entry_id)
        return
    for entry_id in args.entry_ids:
        row = load_catalogue_row(entry_id)
        scenario = load_scenario(entry_id)
        outs = composite_one(
            entry_id,
            row["folder"],
            row["caption"],
            scenario,
            source=args.source,
            source_4x5=args.source_4x5,
            source_9x16=args.source_9x16,
            allow_locked=args.allow_locked,
        )
        for path in outs:
            with Image.open(path) as im:
                print(f"composited {entry_id} {path.relative_to(ROOT)} {im.size[0]}x{im.size[1]}")


if __name__ == "__main__":
    main()
