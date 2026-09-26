#!/usr/bin/env python3
"""Lift the known scrim off a Cosmo-approved master and bake the label bar.

The source is the approved scrim master (origin/main). The overlay is the one
drawn by the 4c6f044 bake: a black gradient from y = int(height * 0.68) with
alpha = int(190 * t ** 1.2), then DejaVu shadow text. Rows above that line are
copied unchanged, so the composition is not regenerated. The scrim band is
inverted with the Pillow alpha_composite preimage. Glyph pixels are filled from
the inverted neighbors. A 190px label bar is then appended.

9:16 has no approved master. It is a center crop of the cleaned 16:9. The
cleaned 4:5 is the approved 4:5 frame with the same overlay removed.

GenerateImage, prompt regeneration, and any new composition are not used.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from composite_masters import (  # noqa: E402
    BAR_BG,
    BAR_H,
    HAIR,
    HAIRLINE,
    PHOTO,
    composite_one,
    is_locked,
    load_catalogue_row,
    load_scenario,
    master_paths,
    pretext_paths,
)
from publish import approval_md  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
SIGNATURE = "Jason D\u2019s Vision"
DISCLOSURE = "AI-generated artistic interpretation \u00b7 Not a photograph."

# Approved scenes whose masters on origin/main still carry the scrim bake.
# NL-01-001–010 are green-lit. NL-01-026–055 stay locked.
FAITHFUL_LO = (
    ("NL-01-001", "NL-01-010"),
    ("NL-01-011", "NL-01-025"),
    ("NL-01-056", "NL-01-144"),
    ("NL-01-145", "NL-01-159"),
    ("NL-01-160", "NL-01-174"),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _in_faithful_range(entry_id: str) -> bool:
    return any(lo <= entry_id <= hi for lo, hi in FAITHFUL_LO)


def _measure(text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = font.getbbox(text)
    return box[2] - box[0], box[3] - box[1]


def _layout(w: int, h: int, caption: str, scenario: str) -> dict:
    fonts = {
        "cap": ImageFont.truetype(FONT_BOLD, round(w * 0.016)),
        "sc": ImageFont.truetype(FONT, round(w * 0.012)),
        "disc": ImageFont.truetype(FONT, round(w * 0.010)),
        "sig": ImageFont.truetype(FONT_BOLD, round(w * 0.018)),
    }
    cap_h = _measure(caption, fonts["cap"])[1]
    sc_h = _measure(scenario, fonts["sc"])[1]
    disc_h = _measure(DISCLOSURE, fonts["disc"])[1]
    sig_w, sig_h = _measure(SIGNATURE, fonts["sig"])
    margin_x = round(w * 0.028)
    margin_b = round(h * 0.030)
    gap = round(w * 0.006)
    y_disc = h - margin_b - disc_h
    y_sc = y_disc - gap - sc_h
    y_cap = y_sc - gap - cap_h
    return {
        "fonts": fonts,
        "margin_x": margin_x,
        "y_cap": y_cap,
        "y_sc": y_sc,
        "y_disc": y_disc,
        "sig_x": w - margin_x - sig_w,
        "sig_y": y_cap + max(0, (cap_h - sig_h) // 2),
        "cap_h": cap_h,
        "sc_h": sc_h,
        "disc_h": disc_h,
        "sig_w": sig_w,
        "sig_h": sig_h,
    }


def _stamp_mask(w: int, h: int, caption: str, scenario: str) -> Image.Image:
    lay = _layout(w, h, caption, scenario)
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    rows = (
        (lay["margin_x"], lay["y_cap"], caption, lay["fonts"]["cap"]),
        (lay["margin_x"], lay["y_sc"], scenario, lay["fonts"]["sc"]),
        (lay["margin_x"], lay["y_disc"], DISCLOSURE, lay["fonts"]["disc"]),
        (lay["sig_x"], lay["sig_y"], SIGNATURE, lay["fonts"]["sig"]),
    )
    for x, y, text, font in rows:
        draw.text((x + 1, y + 1), text, font=font, fill=255)
        draw.text((x, y), text, font=font, fill=255)
    return mask


def build_scrim_luts() -> np.ndarray:
    """Median Pillow preimage of a black overlay. Shape (191, 256) int16. -1 = unreachable."""
    tables = np.full((191, 256), -1, dtype=np.int16)
    for alpha in range(191):
        dest = Image.new("RGBA", (256, 1))
        dest.putdata([(i, i, i, 255) for i in range(256)])
        overlay = Image.new("RGBA", (256, 1), (0, 0, 0, alpha))
        observed = np.asarray(Image.alpha_composite(dest, overlay))[0, :, 0]
        buckets: list[list[int]] = [[] for _ in range(256)]
        for src, value in enumerate(observed.tolist()):
            buckets[value].append(src)
        for value, opts in enumerate(buckets):
            if opts:
                tables[alpha, value] = opts[len(opts) // 2]
    return tables


SCRIM_LUTS = build_scrim_luts()


def _apply_scrim(rgb: np.ndarray) -> np.ndarray:
    image = Image.fromarray(rgb, "RGB").convert("RGBA")
    w, h = image.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    grad = ImageDraw.Draw(overlay)
    start = int(h * 0.68)
    for y in range(start, h):
        t = (y - start) / max(1, (h - start))
        alpha = int(190 * (t ** 1.2))
        grad.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))
    return np.asarray(Image.alpha_composite(image, overlay).convert("RGB"))


def _inpaint(image: np.ndarray, hole: np.ndarray) -> np.ndarray:
    acc = image.astype(np.float32)
    filled = ~hole
    remain = hole.copy()
    h, w = hole.shape
    shifts = ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1))
    for _ in range(64):
        if not remain.any():
            break
        total = np.zeros_like(acc)
        count = np.zeros((h, w), np.float32)
        for dy, dx in shifts:
            ys = slice(max(0, -dy), h - max(0, dy))
            xs = slice(max(0, -dx), w - max(0, dx))
            ysrc = slice(max(0, dy), h - max(0, -dy))
            xsrc = slice(max(0, dx), w - max(0, -dx))
            known = np.zeros((h, w), dtype=bool)
            known[ys, xs] = filled[ysrc, xsrc]
            vals = np.zeros_like(acc)
            vals[ys, xs] = acc[ysrc, xsrc]
            total += vals * known[..., None]
            count += known
        newly = remain & (count > 0)
        if not newly.any():
            break
        acc[newly] = total[newly] / count[newly, None]
        filled[newly] = True
        remain[newly] = False
    if remain.any():
        raise SystemExit(f"inpaint left {int(remain.sum())} pixels")
    return np.clip(np.rint(acc), 0, 255).astype(np.uint8)


def remove_overlay(approved: Image.Image, caption: str, scenario: str) -> tuple[Image.Image, dict]:
    """Return the photo with the known scrim and on-image type removed."""
    arr = np.asarray(approved.convert("RGB"))
    h, w = arr.shape[:2]
    if (w, h) not in ((1920, 1080), (864, 1080)):
        raise SystemExit(f"expected a scrim master, got {w}x{h}")
    start = int(h * 0.68)
    raw_mask = _stamp_mask(w, h, caption, scenario)
    mask = np.asarray(raw_mask) > 0
    dilated = np.asarray(raw_mask.filter(ImageFilter.MaxFilter(5))) > 0

    lay = _layout(w, h, caption, scenario)
    band = np.zeros((h, w), dtype=bool)
    band[max(0, lay["y_cap"] - 4) :, :] = True
    white = (arr.max(axis=2) > 180) & ((arr.max(axis=2).astype(np.int16) - arr.min(axis=2).astype(np.int16)) < 40)
    missed = int((white & band & ~mask).sum())
    covered = int((white & band & mask).sum())

    cleaned = arr.copy()
    unreachable = 0
    for y in range(start, h):
        t = (y - start) / max(1, (h - start))
        alpha = int(190 * (t ** 1.2))
        table = SCRIM_LUTS[alpha]
        keep = ~dilated[y]
        mapped = table[arr[y]]
        bad = keep & (mapped < 0).any(axis=1)
        unreachable += int(bad.sum())
        mapped = np.clip(mapped, 0, 255).astype(np.uint8)
        cleaned[y, keep] = mapped[keep]
    cleaned[:start] = arr[:start]
    inpainted = int(dilated.sum())
    cleaned = _inpaint(cleaned, dilated)
    cleaned[:start] = arr[:start]

    above_changed = int(np.any(cleaned[:start] != arr[:start], axis=2).sum()) if start else 0
    outside = np.zeros((h, w), dtype=bool)
    outside[start:] = True
    outside &= ~dilated
    residual = np.abs(_apply_scrim(cleaned).astype(np.int16) - arr.astype(np.int16))
    residual_max = int(residual[outside].max()) if outside.any() else 0
    stats = {
        "width": w,
        "height": h,
        "scrim_start": start,
        "above_scrim_changed_pixels": above_changed,
        "white_glyphs_covered": covered,
        "white_glyphs_missed": missed,
        "inpainted_pixels": inpainted,
        "unreachable_unmasked": unreachable,
        "recomposite_max_abs": residual_max,
    }
    if above_changed != 0:
        raise SystemExit("rows above the scrim changed")
    if missed != 0:
        raise SystemExit(f"text mask missed {missed} near-white pixels ({covered} covered)")
    if unreachable != 0:
        raise SystemExit(f"{unreachable} unmasked scrim pixels are not a black-overlay preimage")
    if residual_max != 0:
        raise SystemExit(f"scrim recomposite residual {residual_max}")
    return Image.fromarray(cleaned, "RGB"), stats


def _self_test() -> None:
    """The inverse must reproduce a known gradient photo above the scrim exactly."""
    h, w = 1080, 1920
    yy, xx = np.mgrid[0:h, 0:w]
    photo = np.stack(
        [
            40 + (xx * 180) // w + (yy * 30) // h,
            20 + (yy * 200) // h,
            90 + (xx * 40) // w,
        ],
        axis=2,
    ).astype(np.uint8)
    photo[80:200, 700:820] = (230, 200, 140)
    caption = "Markt, Delft"
    scenario = "Scenario: 25 September 2026 · 18:27 Europe/Amsterdam"
    image = Image.fromarray(photo, "RGB").convert("RGBA")
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    grad = ImageDraw.Draw(overlay)
    start = int(h * 0.68)
    for y in range(start, h):
        t = (y - start) / max(1, (h - start))
        alpha = int(190 * (t ** 1.2))
        grad.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))
    image = Image.alpha_composite(image, overlay)
    lay = _layout(w, h, caption, scenario)
    draw = ImageDraw.Draw(image)

    def shadow_text(x: int, y: int, text: str, font: ImageFont.FreeTypeFont) -> None:
        draw.text((x + 1, y + 1), text, font=font, fill=(0, 0, 0, 170))
        draw.text((x, y), text, font=font, fill=(255, 255, 255, 235))

    shadow_text(lay["margin_x"], lay["y_cap"], caption, lay["fonts"]["cap"])
    shadow_text(lay["margin_x"], lay["y_sc"], scenario, lay["fonts"]["sc"])
    shadow_text(lay["margin_x"], lay["y_disc"], DISCLOSURE, lay["fonts"]["disc"])
    shadow_text(lay["sig_x"], lay["sig_y"], SIGNATURE, lay["fonts"]["sig"])
    cleaned, stats = remove_overlay(image.convert("RGB"), caption, scenario)
    got = np.asarray(cleaned)
    if not np.array_equal(got[:start], photo[:start]):
        raise SystemExit("self-test: clock region was not exact")
    if stats["recomposite_max_abs"] != 0 or stats["white_glyphs_missed"] != 0:
        raise SystemExit(f"self-test failed: {stats}")
    err = np.abs(got.astype(np.int16) - photo.astype(np.int16))
    if int(err.max()) > 4:
        raise SystemExit(f"self-test: cleaned photo drifted by {int(err.max())}")


def _evidence_lines(text: str) -> list[str]:
    return [
        line
        for line in text.splitlines()
        if line.startswith("- **Weather:**") or line.startswith("- **Scenario:**")
    ]


def _reanchor_manifest(entry_id: str, folder: str, src16: str, src45: str, sha16: str, sha45: str, sha916: str) -> dict:
    path = ROOT / "manifests" / f"{entry_id}.json"
    data = json.loads(path.read_text())
    if data.get("approval_status") != "Approved":
        raise SystemExit(f"{entry_id} manifest is not Approved")
    stem = entry_id.lower()
    rel916 = f"Netherlands/{folder}/{stem}-9x16.png"
    ordered: dict = {}
    for key, value in data.items():
        if key in {"file_9x16", "sha256_9x16", "faithful_refinish"}:
            continue
        ordered[key] = value
        if key == "file_4x5":
            ordered["file_9x16"] = rel916
    if "file_9x16" not in ordered:
        ordered["file_9x16"] = rel916
    ordered["sha256_16x9"] = sha16
    ordered["sha256_4x5"] = sha45
    ordered["sha256_9x16"] = sha916
    # New 9:16 pixels stay Candidate. 16:9 and 4:5 keep the existing approval.
    ordered["format_9x16_approval_status"] = "Candidate"
    ordered["faithful_refinish"] = (
        "2026-09-26 faithful re-finish of the origin/main approved master. "
        "The 4c6f044 scrim and on-image text were removed without a new render. "
        f"Source SHA-256 16:9 {src16}. Source SHA-256 4:5 {src45}. "
        "Photo rows above the scrim match that approved master. "
        "The 9:16 frame is new pixels from a center crop and stays Candidate. "
        "It does not inherit the 16:9 or 4:5 approval. Those finished-format SHA-256 anchors are unchanged."
    )
    path.write_text(json.dumps(ordered, indent=2, ensure_ascii=False) + "\n")
    return ordered


def _splice_index(manifest: dict) -> None:
    path = ROOT / "index.html"
    html = path.read_text()
    entry_id = manifest["entry_id"]
    token = '{"entry_id": "' + entry_id + '"'
    start = html.find(token)
    if start < 0 or html.find(token, start + len(token)) >= 0:
        raise SystemExit(f"scene object not unique: {entry_id}")
    nxt = html.find('{"entry_id": "', start + len(token))
    if nxt < 0 or html[nxt - 3 : nxt] != "}, ":
        raise SystemExit(f"scene separator missing for {entry_id}")
    blob = json.dumps(manifest, ensure_ascii=False, separators=(", ", ": "))
    html = html[:start] + blob + html[nxt - 2 :]
    marker = "const SCENES = "
    scene_at = html.find(marker)
    if scene_at < 0:
        raise SystemExit("SCENES array missing")
    array_start = scene_at + len(marker)
    array_end = html.find(";\n", array_start)
    json.loads(html[array_start:array_end])
    if manifest["file_9x16"] not in html:
        raise SystemExit(f"index missing {manifest['file_9x16']}")
    path.write_text(html)


def _greenlit_lock(entry_id: str) -> bool:
    return "NL-01-001" <= entry_id <= "NL-01-010"


def refinish_one(entry_id: str) -> dict:
    if not _in_faithful_range(entry_id) or (is_locked(entry_id) and not _greenlit_lock(entry_id)):
        raise SystemExit(f"{entry_id} is outside the faithful re-finish set")
    row = load_catalogue_row(entry_id)
    scenario_label = load_scenario(entry_id)
    scenario = f"Scenario: {scenario_label}"
    outs = master_paths(row["folder"], entry_id)
    src16 = sha256_file(outs["16x9"])
    src45 = sha256_file(outs["4x5"])
    with Image.open(outs["16x9"]) as im16, Image.open(outs["4x5"]) as im45:
        if im16.size != (1920, 1080) or im45.size != (864, 1080):
            raise SystemExit(f"{entry_id} is not an approved scrim master {im16.size} {im45.size}")
        approved16 = np.asarray(im16.convert("RGB")).copy()
        approved45 = np.asarray(im45.convert("RGB")).copy()
        clean16, stats16 = remove_overlay(im16, row["caption"], scenario)
        clean45, stats45 = remove_overlay(im45, row["caption"], scenario)

    pretext = pretext_paths(row["folder"], entry_id)
    if pretext["9x16"].exists():
        pretext["9x16"].unlink()
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        path16 = folder / "clean-16x9.png"
        path45 = folder / "clean-4x5.png"
        clean16.save(path16, format="PNG")
        clean45.save(path45, format="PNG")
        composite_one(
            entry_id,
            row["folder"],
            row["caption"],
            scenario_label,
            source=path16,
            source_4x5=path45,
            allow_locked=_greenlit_lock(entry_id),
        )

    start16 = int(approved16.shape[0] * 0.68)
    start45 = int(approved45.shape[0] * 0.68)
    with Image.open(outs["16x9"]) as baked16, Image.open(outs["4x5"]) as baked45:
        photo16 = np.asarray(baked16.convert("RGB").crop((0, 0, 1920, 1080)))
        photo45 = np.asarray(baked45.convert("RGB").crop((0, 0, 864, 1080)))
        if baked16.size != (1920, 1270) or baked45.size != (864, 1270):
            raise SystemExit(f"{entry_id} label-bar size {baked16.size} {baked45.size}")
        if baked16.getpixel((2, baked16.height - 1))[:3] != BAR_BG:
            raise SystemExit(f"{entry_id} bar")
        if baked16.getpixel((2, 1080))[:3] != HAIR:
            raise SystemExit(f"{entry_id} hairline")
        if baked16.height - 1080 != BAR_H or HAIRLINE != 2:
            raise SystemExit("bar geometry constants drifted")
    if not np.array_equal(photo16[:start16], approved16[:start16]):
        raise SystemExit(f"{entry_id} 16:9 clock region does not match the approved master")
    if not np.array_equal(photo45[:start45], approved45[:start45]):
        raise SystemExit(f"{entry_id} 4:5 upper frame does not match the approved master")
    if not np.array_equal(photo16, np.asarray(clean16)) or not np.array_equal(photo45, np.asarray(clean45)):
        raise SystemExit(f"{entry_id} baked photo area is not the cleaned source")

    sha16 = sha256_file(outs["16x9"])
    sha45 = sha256_file(outs["4x5"])
    sha916 = sha256_file(outs["9x16"])
    note_path = ROOT / "approvals" / f"{entry_id}.md"
    previous = note_path.read_text()
    weather = json.loads((ROOT / "evidence" / "weather" / f"{entry_id}.json").read_text())
    note = approval_md(row, weather, sha16, sha45, sha916)
    if _evidence_lines(note) != _evidence_lines(previous):
        raise SystemExit(f"{entry_id} weather or scenario line changed")
    if "approval_status: Candidate" not in note or "approval_status: Approved" in note:
        raise SystemExit(f"{entry_id} approval note must stay Candidate")
    note_path.write_text(note)
    manifest = _reanchor_manifest(entry_id, row["folder"], src16, src45, sha16, sha45, sha916)
    _splice_index(manifest)
    return {
        "entry_id": entry_id,
        "caption": row["caption"],
        "folder": row["folder"],
        "scenario_label": scenario_label,
        "source_sha256_16x9": src16,
        "source_sha256_4x5": src45,
        "sha256_16x9": sha16,
        "sha256_4x5": sha45,
        "sha256_9x16": sha916,
        "stats_16x9": stats16,
        "stats_4x5": stats45,
        "paths": {fmt: str(path.relative_to(ROOT)) for fmt, path in outs.items()},
        "pretext_16x9": str(pretext["16x9"].relative_to(ROOT)),
        "pretext_4x5": str(pretext["4x5"].relative_to(ROOT)),
    }


def _guard_hashes() -> dict[str, str]:
    watched = []
    for n in list(range(1, 11)) + list(range(26, 56)) + list(range(56, 145)) + [145, 288]:
        entry_id = f"NL-01-{n:03d}"
        row = load_catalogue_row(entry_id)
        for path in master_paths(row["folder"], entry_id).values():
            if path.exists():
                watched.append(path)
        manifest = ROOT / "manifests" / f"{entry_id}.json"
        watched.append(manifest)
    return {str(path.relative_to(ROOT)): sha256_file(path) for path in watched}


def main(argv: list[str] | None = None) -> None:
    ids = argv if argv is not None else sys.argv[1:]
    if not ids:
        raise SystemExit("pass entry ids, for example NL-01-011")
    _self_test()
    before = _guard_hashes()
    reports = [refinish_one(entry_id) for entry_id in ids]
    after = _guard_hashes()
    for entry_id in ids:
        row = load_catalogue_row(entry_id)
        for path in master_paths(row["folder"], entry_id).values():
            after.pop(str(path.relative_to(ROOT)), None)
        after.pop(f"manifests/{entry_id}.json", None)
    drifted = [key for key, digest in after.items() if before.get(key) != digest]
    if drifted:
        raise SystemExit("untouched files changed: " + ", ".join(drifted[:8]))
    print(json.dumps(reports, indent=2))


if __name__ == "__main__":
    main()
