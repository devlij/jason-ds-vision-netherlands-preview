#!/usr/bin/env python3
"""Static-camera ambient clips for Netherlands 360 rebuild batch 5.

The camera stays locked on the genuine daylight 4:5 plate. The 190px label
bar under the photo is cropped off before any frame is made. Only sky, water,
foliage, and flags already in the plate are displaced, and only inside their
own masks, so architecture cannot smear, spawn, or flip.

This is not an orbit, a sweep, or an interpolation between generated views.
Pedestrians stay on the locked plate: a synthetic walk would invent limbs.
A subject-pinned slow pan is coded only as a fallback when in-frame life
covers less than DEAD_LIFE of the frame. It is a sine crop of an upscale of
the same plate, not an orbit.
"""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FPS = 24
FRAMES = 240  # exactly 10.0s
PHOTO_H = 1080
PHOTO_W = 864
DEAD_LIFE = 0.04

SCENES = (
    {
        "entry_id": "NL-01-063",
        "folder": "Dwingeloo",
        "life": "overcast cloud drift and heath grass; the sand path stays locked",
    },
    {
        "entry_id": "NL-01-065",
        "folder": "Oranjestad",
        "life": "cloud drift and a band of Caribbean sea; cannons and walkers stay locked",
    },
    {
        "entry_id": "NL-01-066",
        "folder": "The Bottom",
        "life": "cloud drift and crater foliage; houses and the road stay locked",
    },
    {
        "entry_id": "NL-01-068",
        "folder": "Heusden",
        "life": "cloud drift, harbour water, and rampart trees; the mills stay locked",
    },
    {
        "entry_id": "NL-01-069",
        "folder": "Nuenen",
        "life": "cloud drift and churchyard trees; the brick church stays locked",
    },
    {
        "entry_id": "NL-01-070",
        "folder": "Zwolle",
        "life": "cloud drift over the gate; the Sassenpoort stays locked",
    },
    {
        "entry_id": "NL-01-071",
        "folder": "Kampen",
        "life": "cloud drift and IJssel water; houses and the bridge stay locked",
    },
    {
        "entry_id": "NL-01-072",
        "folder": "Elburg",
        "life": "cloud drift and harbour water; the Vischpoort and hulls stay locked",
    },
    {
        "entry_id": "NL-01-073",
        "folder": "Zutphen",
        "life": "sky, Berkel water, and bank trees; the water gate stays locked",
    },
    {
        "entry_id": "NL-01-074",
        "folder": "Arnhem",
        "life": "cloud drift and park trees; the white villa stays locked",
    },
)


def anchor_path(scene: dict) -> Path:
    slug = scene["entry_id"].lower()
    return ROOT / "library/world/Netherlands" / scene["folder"] / f"{slug}-daylight-4x5.png"


def out_path(scene: dict) -> Path:
    slug = scene["entry_id"].lower()
    return ROOT / "library/world/Netherlands" / scene["folder"] / f"{slug}-motion-10s-4x5.mp4"


def poster_path(scene: dict) -> Path:
    slug = scene["entry_id"].lower()
    return ROOT / "library/world/Netherlands" / scene["folder"] / f"{slug}-motion-10s-4x5-poster.jpg"


def crop_plate(path: Path) -> np.ndarray:
    im = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if im is None:
        raise SystemExit(f"missing anchor {path}")
    if im.shape[1] != PHOTO_W or im.shape[0] < PHOTO_H + 2:
        raise SystemExit(f"{path} is {im.shape[1]}x{im.shape[0]}, expected {PHOTO_W}x>={PHOTO_H + 2}")
    plate = im[:PHOTO_H].copy()
    if float(plate[-1].std()) < 4:
        raise SystemExit(f"{path} bottom photo row looks like the label bar")
    # The label bar is #0e0e12. Refuse if the crop still starts on that bar.
    bar = im[PHOTO_H:]
    if bar.size and float(np.median(bar[:8], axis=(0, 1)).max()) > 40:
        raise SystemExit(f"{path} rows under the photo are not the dark label bar")
    return plate


def _components(mask: np.ndarray, pred) -> np.ndarray:
    n, labels, stats, _ = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), connectivity=4)
    keep = np.zeros(mask.shape, np.uint8)
    for i in range(1, n):
        x, y, w, hh, area = (int(v) for v in stats[i])
        if pred(x, y, w, hh, area):
            keep[labels == i] = 255
    return keep


def _local_std(gray: np.ndarray, k: int) -> np.ndarray:
    blur = cv2.blur(gray, (k, k))
    blur2 = cv2.blur(gray * gray, (k, k))
    return np.sqrt(np.maximum(blur2 - blur * blur, 0.0))


def build_masks(plate: np.ndarray) -> dict[str, np.ndarray]:
    hsv = cv2.cvtColor(plate, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    height, width = h.shape
    yy = np.arange(height)[:, None]
    gray = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY).astype(np.float32)
    local = _local_std(gray, 7)

    b = plate[:, :, 0].astype(np.int16)
    g = plate[:, :, 1].astype(np.int16)
    r = plate[:, :, 2].astype(np.int16)
    overcast = (s < 55) & (v > 168) & (local < 16) & (h >= 70)
    blue_sky = (h >= 90) & (h <= 130) & (s >= 8) & (s < 220) & (v > 145)
    sky_cand = (overcast | blue_sky).astype(np.uint8)
    # Leaves, brick, and sunlit sea do not belong in the sky.
    sky_cand[(h >= 25) & (h <= 95) & (s > 36)] = 0
    sky_cand[((h < 12) | (h > 168)) & (s > 60)] = 0
    sky = _components(sky_cand, lambda x, y, w, hh, area: y <= 6 and area > 500)
    sky = cv2.erode(sky, np.ones((3, 3), np.uint8), iterations=1)
    # A warm bright band under the clouds is sea or haze, not cloud.
    warm_surface = (sky > 0) & (h < 70) & (s > 16) & (yy > int(height * 0.32))
    sky[warm_surface] = 0

    blue_cast = b + 6 >= g
    blue_water = (h >= 85) & (h <= 135) & (s >= 18) & (v >= 28) & (v <= 210) & blue_cast
    # Grey harbour and river. Green lawns fail the blue-cast test.
    grey_water = (
        (s < 24)
        & (v > 45)
        & (v < 185)
        & (local < 12)
        & blue_cast
        & (np.abs(b - g) < 16)
        & (yy > int(height * 0.70))
    )
    warm_water = warm_surface & (local < 18) & (yy > int(height * 0.36))
    water_cand = ((blue_water | grey_water | warm_water) & (sky == 0)).astype(np.uint8)
    water = _components(
        water_cand,
        lambda x, y, w, hh, area: area > 2200 and w > 70 and (y + hh / 2) > height * 0.40,
    )
    water = cv2.erode(water, np.ones((3, 3), np.uint8), iterations=1)
    water = _components(
        water,
        lambda x, y, w, hh, area: area > 800 and w > 40 and (y + hh / 2) > height * 0.40,
    )
    # Saturated green is grass or trees, even when it is smooth.
    grass = (water > 0) & (g > b + 8) & (s > 40)
    water[grass] = 0
    if int(np.count_nonzero(water)) < 12000:
        water[:] = 0

    fol_cand = (
        (
            ((h >= 18) & (h <= 95) & (s >= 28) & (v >= 22) & (v <= 210) & (g + 4 >= r))
            | grass
        )
        & (sky == 0)
        & (water == 0)
    ).astype(np.uint8)
    foliage = _components(fol_cand, lambda x, y, w, hh, area: area > 160)
    foliage = cv2.erode(foliage, np.ones((3, 3), np.uint8), iterations=1)

    red = (((h <= 8) | (h >= 170)) & (s >= 140) & (v >= 80)).astype(np.uint8)
    blue = ((h >= 100) & (h <= 135) & (s >= 110) & (v >= 60) & (sky == 0)).astype(np.uint8)
    red_s = _components(red, lambda x, y, w, hh, area: 30 <= area <= 9000 and hh < 260 and w < 220)
    blue_s = _components(blue, lambda x, y, w, hh, area: 20 <= area <= 7000 and hh < 260 and w < 200)
    kernel = np.ones((11, 11), np.uint8)
    near = cv2.dilate(red_s, kernel) & cv2.dilate(blue_s, kernel)
    near = cv2.dilate(near, np.ones((5, 5), np.uint8))
    white = ((s < 50) & (v > 150) & (near > 0)).astype(np.uint8)
    flags = ((red_s > 0) | (blue_s > 0) | (white > 0)) & (near > 0)
    flags = flags.astype(np.uint8) * 255
    flags[water > 0] = 0
    flags[sky > 0] = 0
    flags = _components(flags, lambda x, y, w, hh, area: 40 <= area <= 12000 and hh < 280 and w < 260)
    flags = cv2.erode(flags, np.ones((2, 2), np.uint8), iterations=1)

    foliage[water > 0] = 0
    foliage[sky > 0] = 0
    flags[foliage > 0] = 0
    return {"sky": sky, "water": water, "foliage": foliage, "flags": flags}


def _factor(mask: np.ndarray, reach: float) -> np.ndarray:
    dist = cv2.distanceTransform((mask > 0).astype(np.uint8), cv2.DIST_L2, 3)
    return np.clip(dist / reach, 0, 1).astype(np.float32)


def _apply(out: np.ndarray, plate: np.ndarray, mask: np.ndarray, dx: np.ndarray, dy: np.ndarray) -> None:
    if not np.any(mask):
        return
    height, width = mask.shape
    xs = np.broadcast_to(np.arange(width, dtype=np.float32), (height, width)).copy()
    ys = np.broadcast_to(np.arange(height, dtype=np.float32)[:, None], (height, width)).copy()
    map_x = xs - dx
    map_y = ys - dy
    warped = cv2.remap(plate, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    src = cv2.remap(mask.astype(np.float32) / 255.0, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    use = (mask > 0) & (src > 0.985)
    out[use] = warped[use]


def render_frame(plate: np.ndarray, masks: dict[str, np.ndarray], factors: dict[str, np.ndarray], n: int) -> np.ndarray:
    t = n / FRAMES
    s1 = math.sin(2 * math.pi * t)
    s2 = math.sin(4 * math.pi * t)
    out = plate.copy()
    height, width = plate.shape[:2]
    ys = np.arange(height, dtype=np.float32)[:, None]
    xs = np.arange(width, dtype=np.float32)[None, :]

    if np.any(masks["foliage"]):
        phase = s1 * np.sin(ys * 0.035 + 0.4)
        dx = (4.6 * phase * factors["foliage"]).astype(np.float32)
        dy = (1.1 * s2 * factors["foliage"]).astype(np.float32)
        _apply(out, plate, masks["foliage"], dx, dy)

    if np.any(masks["water"]):
        dx = (3.4 * np.sin(2 * math.pi * t + ys * 0.045) * factors["water"]).astype(np.float32)
        dy = (1.6 * np.sin(4 * math.pi * t + xs * 0.05) * factors["water"]).astype(np.float32)
        _apply(out, plate, masks["water"], dx, dy)
        shimmer = (6.0 * np.sin(4 * math.pi * t + xs * 0.08 + ys * 0.03) * factors["water"]).astype(np.float32)
        region = masks["water"] > 0
        lifted = out.astype(np.float32)
        lifted[region] += shimmer[region, None]
        out[region] = np.clip(lifted[region], 0, 255).astype(np.uint8)

    if np.any(masks["flags"]):
        dx = (5.5 * np.sin(4 * math.pi * t + ys * 0.12) * factors["flags"]).astype(np.float32)
        dy = (1.2 * s2 * factors["flags"]).astype(np.float32)
        _apply(out, plate, masks["flags"], dx, dy)

    if np.any(masks["sky"]):
        dx = (18.0 * s1 * factors["sky"]).astype(np.float32)
        dy = (1.6 * s1 * factors["sky"]).astype(np.float32)
        _apply(out, plate, masks["sky"], dx, dy)
        breath = (8.0 * s1 * np.sin(xs * 0.028 + ys * 0.01) * factors["sky"]).astype(np.float32)
        region = masks["sky"] > 0
        lifted = out.astype(np.float32)
        lifted[region] += breath[region, None]
        out[region] = np.clip(lifted[region], 0, 255).astype(np.uint8)

    life = (masks["sky"] | masks["water"] | masks["foliage"] | masks["flags"]) > 0
    if not np.array_equal(out[~life], plate[~life]):
        raise SystemExit("architecture pixel moved; refusing to encode")
    return out


def life_coverage(masks: dict[str, np.ndarray]) -> dict[str, float]:
    total = float(PHOTO_H * PHOTO_W)
    return {name: round(float(np.count_nonzero(mask)) / total, 4) for name, mask in masks.items()}


def factors_for(masks: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    return {
        "sky": _factor(masks["sky"], 28.0),
        "water": _factor(masks["water"], 14.0),
        "foliage": _factor(masks["foliage"], 16.0),
        "flags": _factor(masks["flags"], 6.0),
    }


def encode_frames(frames, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{PHOTO_W}x{PHOTO_H}",
        "-r", str(FPS), "-i", "-",
        "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "18", "-preset", "medium", "-movflags", "+faststart",
        str(dest),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for frame in frames:
            proc.stdin.write(frame.tobytes())
    finally:
        proc.stdin.close()
    err = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
    code = proc.wait()
    if code != 0:
        raise SystemExit(f"ffmpeg failed for {dest}\n{err[-2000:]}")


def subject_centroid(plate: np.ndarray, masks: dict[str, np.ndarray]) -> tuple[float, float]:
    life = (masks["sky"] | masks["water"]) > 0
    subject = ~life
    ys, xs = np.nonzero(subject)
    if len(xs) < 100:
        return PHOTO_W / 2, PHOTO_H / 2
    return float(xs.mean()), float(ys.mean())


def render_pinned_pan(plate: np.ndarray, masks: dict[str, np.ndarray], n: int) -> np.ndarray:
    """Slow horizontal pan of an upscale of this same plate.

    The subject's centroid stays inside the central third of every frame.
    No second viewpoint is generated and nothing is optically blended.
    """
    scale = 1.08
    scaled = cv2.resize(plate, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    sh, sw = scaled.shape[:2]
    cx, cy = subject_centroid(plate, masks)
    sx = cx * scale
    sy = cy * scale
    amp = min(28.0, max(0.0, (sw - PHOTO_W) / 2 - 2))
    shift = amp * math.sin(2 * math.pi * n / FRAMES)
    left = int(round(sx - PHOTO_W / 2 + shift))
    top = int(round(sy - PHOTO_H / 2))
    left = max(0, min(left, sw - PHOTO_W))
    top = max(0, min(top, sh - PHOTO_H))
    crop = scaled[top:top + PHOTO_H, left:left + PHOTO_W]
    if crop.shape != (PHOTO_H, PHOTO_W, 3):
        raise SystemExit(f"pinned pan crop {crop.shape}")
    # Where the centroid lands in the output.
    out_x = sx - left
    if not (PHOTO_W * 0.34 <= out_x <= PHOTO_W * 0.66):
        raise SystemExit(f"subject centroid x={out_x:.1f} left the central third")
    return crop


def probe(path: Path) -> dict:
    raw = subprocess.check_output(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,nb_frames,duration,codec_name,avg_frame_rate",
            "-show_entries", "format=duration",
            "-of", "json", str(path),
        ]
    )
    return json.loads(raw)


def debug_scene(scene: dict, debug_dir: Path) -> dict:
    plate = crop_plate(anchor_path(scene))
    masks = build_masks(plate)
    overlay = plate.copy()
    colors = {"sky": (255, 180, 40), "water": (255, 80, 20), "foliage": (40, 180, 40), "flags": (40, 40, 220)}
    for name, color in colors.items():
        sel = masks[name] > 0
        overlay[sel] = (0.55 * overlay[sel] + 0.45 * np.array(color)).astype(np.uint8)
    debug_dir.mkdir(parents=True, exist_ok=True)
    slug = scene["entry_id"]
    cv2.imwrite(str(debug_dir / f"{slug}-mask.jpg"), overlay, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    cov = life_coverage(masks)
    life = sum(cov.values())
    row = {"entry_id": slug, "coverage": cov, "life": round(life, 4)}
    if life >= DEAD_LIFE:
        fac = factors_for(masks)
        mid = render_frame(plate, masks, fac, FRAMES // 4)
        diff = cv2.absdiff(mid, plate)
        row["mid_mad"] = round(float(diff.mean()), 3)
        life_sel = (masks["sky"] | masks["water"] | masks["foliage"] | masks["flags"]) > 0
        row["locked_max"] = int(diff[~life_sel].max()) if np.any(~life_sel) else 0
        row["moving_mad"] = round(float(diff[life_sel].mean()), 3) if np.any(life_sel) else 0.0
        small = cv2.resize(overlay, (432, 540), interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(debug_dir / f"{slug}-mask-small.jpg"), small, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    return row


def main() -> None:
    import sys

    debug = "--debug" in sys.argv
    only = [a for a in sys.argv[1:] if a.startswith("NL-")]
    rows = []
    for scene in SCENES:
        if only and scene["entry_id"] not in only:
            continue
        if debug:
            row = debug_scene(scene, Path("/tmp/ambient5"))
            print(json.dumps(row))
            rows.append(row)
            continue
        plate = crop_plate(anchor_path(scene))
        masks = build_masks(plate)
        cov = life_coverage(masks)
        life = sum(cov.values())
        method = "static-ambient"
        if life < DEAD_LIFE:
            method = "subject-pinned-slow-pan"

            def frames_pan(plate=plate, masks=masks):
                for n in range(FRAMES):
                    yield render_pinned_pan(plate, masks, n)

            encode_frames(frames_pan(), out_path(scene))
        else:
            fac = factors_for(masks)
            peak = render_frame(plate, masks, fac, FRAMES // 4)
            diff = cv2.absdiff(peak, plate)
            life_sel = (masks["sky"] | masks["water"] | masks["foliage"] | masks["flags"]) > 0
            moving_mad = float(diff[life_sel].mean()) if np.any(life_sel) else 0.0
            if moving_mad < 0.45:
                raise SystemExit(f"{scene['entry_id']} moving MAD {moving_mad:.2f} — ambient life is dead")

            def frames_still(plate=plate, masks=masks, fac=fac):
                for n in range(FRAMES):
                    yield render_frame(plate, masks, fac, n)

            encode_frames(frames_still(), out_path(scene))
        cv2.imwrite(str(poster_path(scene)), plate, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        info = probe(out_path(scene))
        stream = info["streams"][0]
        duration = float(info["format"]["duration"])
        if int(stream["width"]) != PHOTO_W or int(stream["height"]) != PHOTO_H:
            raise SystemExit(f"{scene['entry_id']} size {stream['width']}x{stream['height']}")
        if abs(duration - 10.0) > 0.05:
            raise SystemExit(f"{scene['entry_id']} duration {duration}")
        rows.append({
            "entry_id": scene["entry_id"],
            "method": method,
            "life": scene["life"],
            "coverage": cov,
            "life_coverage": round(life, 4),
            "duration_s": duration,
            "width": int(stream["width"]),
            "height": int(stream["height"]),
            "frames": int(stream.get("nb_frames") or FRAMES),
            "fps": FPS,
            "anchor": str(anchor_path(scene).relative_to(ROOT)),
            "anchor_kind": "genuine-daylight 4:5 master; label bar cropped; night master not used",
            "label_bar_px_cropped": 190,
            "path": str(out_path(scene).relative_to(ROOT)),
            "poster": str(poster_path(scene).relative_to(ROOT)),
            "pedestrians": "Left on the locked plate. A synthetic walk would invent limbs.",
            "camera": "locked" if method == "static-ambient" else "subject-pinned slow pan",
        })
        print(json.dumps(rows[-1]))
    if debug:
        (Path("/tmp/ambient5") / "coverage.json").write_text(json.dumps(rows, indent=2) + "\n")
        return
    evidence = {
        "work_order": "wo-nl-360-rebuild-2026-10-02",
        "batch": 5,
        "status": "Candidate",
        "qc": "Not Cosmo QC. Not approved. Do not merge.",
        "cosmo_qc_required": True,
        "do_not_merge": True,
        "method_default": "static-ambient",
        "camera": "locked unless a scene notes subject-pinned slow pan",
        "not_used": [
            "orbit",
            "sweep",
            "viewpoint interpolation",
            "optical-flow blend between generated views",
            "verbatim re-roll of the held pack 6 and pack 7 prompts",
            "night master",
            "finished master with the label bar left on",
        ],
        "spec": {
            "duration_s": 10.0,
            "width": 864,
            "height": 1080,
            "fps": 24,
            "format": "4:5",
            "label_bar_px_cropped": 190,
        },
        "caribbean": {
            "NL-01-065": "Proceeded. Genuine daylight anchor, Open-Meteo is_day 1, sunlit Fort Oranje.",
            "NL-01-066": "Proceeded. Genuine daylight anchor, Open-Meteo is_day 1, sunlit crater village.",
        },
        "scenes": rows,
    }
    dest = ROOT / "evidence/motion/NL-360-rebuild-batch5-2026-10-02.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(evidence, indent=2) + "\n")
    print("wrote", dest)


if __name__ == "__main__":
    main()
