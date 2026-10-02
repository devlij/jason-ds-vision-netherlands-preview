#!/usr/bin/env python3
"""Batch 3 static-ambient clips for the Netherlands 360 rebuild.

The camera stays locked. Only sky, water, foliage, flags, and detected
pedestrians already in the daylight plate are displaced, and every
displacement is a sine that returns to the plate so the 10s loop closes.
No orbit, no sweep, no viewpoint interpolation, no optical-flow blend.

The 190px label bar (and its 2px hairline) is cropped off the genuine
daylight 4:5 master before any motion. Night masters are not read.

A subject-pinned slow pan is used only when that ambient life is visibly
dead. It slides a window across the same daylight 16:9 photograph so the
subject stays inside the central band of every frame. It is not an orbit.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BAR = 190
PHOTO_H = 1080
OUT_W = 864
FPS = 24
FRAMES = 240  # exactly 10.0s
DEAD_LIFE = 0.035
DEAD_MOVE = 0.80
# A pan smaller than this is not worth leaving the locked camera.
MIN_PAN_PX = 12
MAX_PAN_PX = 48

SCENES = [
    {
        "entry_id": "NL-01-031",
        "caption": "Markt, Gouda",
        "city": "Gouda",
        "folder": "Gouda",
        "life": "cloud drift and tree sway; the square, the town hall, and any figures stay locked",
    },
    {
        "entry_id": "NL-01-032",
        "caption": "Grote Kerk, Dordrecht",
        "city": "Dordrecht",
        "folder": "Dordrecht",
        "life": "harbour water, cloud drift, and a little foliage; boats stay locked",
    },
    {
        "entry_id": "NL-01-033",
        "caption": "Oudegracht, Utrecht",
        "city": "Utrecht",
        "folder": "Utrecht",
        "life": "canal water, cloud drift, and tree sway; the wharf houses stay locked",
    },
    {
        "entry_id": "NL-01-034",
        "caption": "Schröder House, Utrecht",
        "city": "Utrecht",
        "folder": "Utrecht",
        "life": "cloud drift and tree sway; the house and the street stay locked",
    },
    {
        "entry_id": "NL-01-036",
        "caption": "Duurstede Castle, Wijk bij Duurstede",
        "city": "Wijk bij Duurstede",
        "folder": "Wijk bij Duurstede",
        "life": "moat water, cloud drift, and tree sway; the castle stays locked",
    },
    {
        "entry_id": "NL-01-039",
        "caption": "Breda Castle, Breda",
        "city": "Breda",
        "folder": "Breda",
        "life": "moat water, cloud drift, and tree sway; the towers stay locked",
    },
    {
        "entry_id": "NL-01-042",
        "caption": "Noordhavenpoort, Zierikzee",
        "city": "Zierikzee",
        "folder": "Zierikzee",
        "life": "harbour water and cloud drift; the gate and the boats stay locked",
    },
    {
        "entry_id": "NL-01-043",
        "caption": "Oosterscheldekering, Neeltje Jans",
        "city": "Neeltje Jans",
        "folder": "Neeltje Jans",
        "life": "sea surface and cloud drift; the piers stay locked",
    },
    {
        "entry_id": "NL-01-045",
        "caption": "Lebuinuskerk, Deventer",
        "city": "Deventer",
        "folder": "Deventer",
        "life": "cloud drift and tree sway; the church and the square stay locked",
    },
    {
        "entry_id": "NL-01-049",
        "caption": "Basilica of Saint Servatius, Maastricht",
        "city": "Maastricht",
        "folder": "Maastricht",
        "life": "cloud drift and tree sway; the basilica stays locked",
    },
]


def daylight_weather(entry_id: str) -> dict:
    path = ROOT / "evidence" / "weather" / "daylight" / f"{entry_id}.json"
    data = json.loads(path.read_text())
    return {
        "model_time": data.get("model_time"),
        "is_day": data.get("is_day"),
        "cloud_cover": data.get("cloud_cover"),
        "weather_code": data.get("weather_code"),
        "temperature_2m": data.get("temperature_2m"),
        "wind_speed_10m": data.get("wind_speed_10m"),
        "precipitation": data.get("precipitation"),
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "retrieval_timestamp": data.get("retrieval_timestamp"),
        "note": "Daylight-master Open-Meteo retrieval. The clip is not a live capture.",
    }


def load_daylight(scene: dict) -> tuple[np.ndarray, np.ndarray, Path]:
    path = (
        ROOT
        / "library/world/Netherlands"
        / scene["folder"]
        / f"{scene['entry_id'].lower()}-daylight-4x5.png"
    )
    im = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if im is None:
        raise SystemExit(f"missing daylight anchor {path}")
    if im.shape[1] != OUT_W or im.shape[0] < PHOTO_H + BAR:
        raise SystemExit(f"{path} is {im.shape[1]}x{im.shape[0]}, expected {OUT_W}x>={PHOTO_H + BAR}")
    hair = im[PHOTO_H : PHOTO_H + 2]
    body = im[PHOTO_H + 2 :]
    # Composited masters put a flat hairline, then the #0e0e12 bar, under the photo.
    # A pretext has no bar. The night master is a different file and is not opened.
    if float(hair.std()) > 12 or body.size == 0 or float(body.mean()) > 45:
        raise SystemExit(
            f"{path} bottom is not the label bar (hair std {float(hair.std()):.1f}, bar mean {float(body.mean()) if body.size else -1:.1f})"
        )
    plate = im[:PHOTO_H].copy()
    if float(plate[-1].std()) < 4 and float(plate[-1].mean()) < 30:
        raise SystemExit(f"{path} photo crop still includes the label bar")
    night = (
        ROOT
        / "library/world/Netherlands"
        / scene["folder"]
        / f"{scene['entry_id'].lower()}-4x5.png"
    )
    if path.resolve() == night.resolve():
        raise SystemExit(f"refusing night master {path}")
    return plate, im, path


def _components(mask: np.ndarray, pred) -> np.ndarray:
    n, labels, stats, _ = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), connectivity=8)
    keep = np.zeros(mask.shape, np.uint8)
    for i in range(1, n):
        x, y, w, h, area = (int(v) for v in stats[i])
        if pred(x, y, w, h, area):
            keep[labels == i] = 255
    return keep


def _median_1d(values: np.ndarray, radius: int) -> np.ndarray:
    pad = np.pad(values.astype(np.float32), (radius, radius), mode="edge")
    windows = np.lib.stride_tricks.sliding_window_view(pad, 2 * radius + 1)
    return np.median(windows, axis=1)


def _keep_real_water(plate: np.ndarray, hue: np.ndarray, sat: np.ndarray, water: np.ndarray) -> np.ndarray:
    """Drop paving, brick, and narrow shadow strips that only look smooth."""
    if not np.any(water):
        return water
    n, labels, stats, _ = cv2.connectedComponentsWithStats(water, connectivity=8)
    keep = np.zeros(water.shape, np.uint8)
    for i in range(1, n):
        x, y, w, hh, area = (int(v) for v in stats[i])
        sel = labels == i
        hmed = float(np.median(hue[sel]))
        smed = float(np.median(sat[sel]))
        blue = ((hue[sel] >= 85) & (hue[sel] <= 140) & (sat[sel] >= 20)).mean()
        if w < 160 and blue < 0.35:
            continue
        # Red-brown stone and grey paving. Real moats and canals sit above this.
        if hmed < 22 and blue < 0.25:
            continue
        if smed < 24 and blue < 0.25:
            continue
        # A small blue patch in the upper frame is a window or a sky hole, not a harbour.
        cy = y + hh / 2
        if cy < plate.shape[0] * 0.62 and area < 15000:
            continue
        keep[sel] = 255
    return keep


def build_masks(plate: np.ndarray) -> dict[str, np.ndarray]:
    hsv = cv2.cvtColor(plate, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    height, width = h.shape
    yy = np.arange(height)[:, None]
    gray = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gx = np.abs(np.diff(gray, axis=1, prepend=gray[:, :1]))
    gy = np.abs(np.diff(gray, axis=0, prepend=gray[:1, :]))
    edge = gx + gy
    local = cv2.GaussianBlur(gray, (0, 0), 3)
    local = np.abs(gray - local)

    blue = (h >= 90) & (h <= 130) & (s >= 18) & (v >= 90)
    # Bright, dull cloud. Flat white walls share this colour and are cut by the skyline.
    cloud = (s < 55) & (v > 165) & (local < 14)
    sky_like = blue | cloud
    bad = ~sky_like
    skyline = np.argmax(bad, axis=0).astype(np.int32)
    skyline[bad.any(axis=0) == 0] = height
    strong = gy > 26
    cut = np.argmax(strong, axis=0).astype(np.int32)
    cut[strong.any(axis=0) == 0] = height
    skyline = np.minimum(skyline, cut)
    skyline = _median_1d(skyline, 6).astype(np.int32)
    skyline = np.clip(skyline - 2, 0, height)
    sky = (yy < skyline[None, :]) & sky_like & (edge < 28)
    sky = _components(sky.astype(np.uint8), lambda x, y, w, hh, area: y <= 6 and area > 500)
    sky = cv2.erode(sky, np.ones((3, 3), np.uint8), iterations=1)

    # Ripples make water speckled. Close horizontally so a sheet becomes one
    # body, without bridging the wide piers and hulls that break the colour.
    blue_water = (h >= 85) & (h <= 135) & (s >= 18) & (v >= 28) & (edge < 34)
    green_water = (h >= 32) & (h <= 95) & (s >= 18) & (v >= 22) & (v <= 185) & (local < 18) & (edge < 26)
    # Muddy moats (Breda) are brown and smooth, and only in the lower frame.
    mud_water = (
        (h >= 10) & (h <= 42) & (s >= 28) & (s <= 120) & (v >= 36) & (v <= 145)
        & (local < 12) & (edge < 16) & (yy > int(height * 0.72))
    )
    water_cand = (
        ((blue_water | green_water) & (yy > int(height * 0.42)))
        | mud_water
    ) & (sky == 0)
    water_u8 = water_cand.astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (19, 5))
    water_u8 = cv2.morphologyEx(water_u8, cv2.MORPH_CLOSE, kernel)
    water_u8[edge > 36] = 0
    water = _components(
        water_u8,
        lambda x, y, w, hh, area: (
            area > 3500 and w > 90 and (y + hh / 2) > height * 0.50 and hh < w * 3.0
        ),
    )
    water = cv2.erode(water, np.ones((3, 3), np.uint8), iterations=1)
    water = _components(
        water,
        lambda x, y, w, hh, area: area > 2000 and w > 48 and not (w < 28 and hh > w * 2.5),
    )
    water = _keep_real_water(plate, h, s, water)

    fol_cand = (
        (h >= 18) & (h <= 95) & (s >= 30) & (v >= 25) & (v <= 210) & (sky == 0) & (water == 0) & (local > 4)
    ).astype(np.uint8)
    foliage = _components(fol_cand, lambda x, y, w, hh, area: area > 180)
    foliage = cv2.erode(foliage, np.ones((3, 3), np.uint8), iterations=1)
    foliage[water > 0] = 0
    foliage[sky > 0] = 0

    # Flag-coloured windows on these plates were brick edges, bargeboards, and
    # window frames, not cloth. Animating them would sway the building.
    # Pedestrian-sized blobs were lamp posts, bollards, and mullions. Both stay
    # on the locked plate. A synthetic walk would invent limbs.
    flags = np.zeros(sky.shape, np.uint8)
    pedestrians = np.zeros(sky.shape, np.uint8)

    return {
        "sky": sky,
        "water": water,
        "foliage": foliage,
        "flags": flags,
        "pedestrians": pedestrians,
    }


def _factor(mask: np.ndarray, reach: float) -> np.ndarray:
    dist = cv2.distanceTransform((mask > 0).astype(np.uint8), cv2.DIST_L2, 3)
    return np.clip(dist / reach, 0, 1).astype(np.float32)


def _apply(out: np.ndarray, plate: np.ndarray, mask: np.ndarray, dx: np.ndarray, dy: np.ndarray) -> None:
    if not np.any(mask):
        return
    height, width = mask.shape
    xs = np.broadcast_to(np.arange(width, dtype=np.float32), (height, width)).copy()
    ys = np.broadcast_to(np.arange(height, dtype=np.float32)[:, None], (height, width)).copy()
    warped = cv2.remap(
        plate,
        xs - dx,
        ys - dy,
        cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )
    src = cv2.remap(
        mask.astype(np.float32) / 255.0,
        xs - dx,
        ys - dy,
        cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
    )
    use = (mask > 0) & (src > 0.985)
    out[use] = warped[use]


def render_ambient(plate: np.ndarray, masks: dict[str, np.ndarray], factors: dict[str, np.ndarray], n: int) -> np.ndarray:
    t = n / FRAMES
    s1 = math.sin(2 * math.pi * t)
    s2 = math.sin(4 * math.pi * t)
    out = plate.copy()
    height, width = plate.shape[:2]
    ys = np.arange(height, dtype=np.float32)[:, None]
    xs = np.arange(width, dtype=np.float32)[None, :]

    if np.any(masks["foliage"]):
        phase = s1 * np.sin(ys * 0.035 + 0.4)
        dx = (4.2 * phase * factors["foliage"]).astype(np.float32)
        dy = (1.0 * s2 * factors["foliage"]).astype(np.float32)
        _apply(out, plate, masks["foliage"], dx, dy)

    if np.any(masks["water"]):
        dx = (3.2 * np.sin(2 * math.pi * t + ys * 0.045) * factors["water"]).astype(np.float32)
        dy = (1.5 * np.sin(4 * math.pi * t + xs * 0.05) * factors["water"]).astype(np.float32)
        _apply(out, plate, masks["water"], dx, dy)
        shimmer = (5.0 * np.sin(4 * math.pi * t + xs * 0.08 + ys * 0.03) * factors["water"]).astype(np.float32)
        region = masks["water"] > 0
        lifted = out.astype(np.float32)
        lifted[region] += shimmer[region, None]
        out[region] = np.clip(lifted[region], 0, 255).astype(np.uint8)

    if np.any(masks["flags"]):
        dx = (5.0 * np.sin(4 * math.pi * t + ys * 0.12) * factors["flags"]).astype(np.float32)
        dy = (1.1 * s2 * factors["flags"]).astype(np.float32)
        _apply(out, plate, masks["flags"], dx, dy)

    if np.any(masks["pedestrians"]):
        nlab, labels, stats, _ = cv2.connectedComponentsWithStats(masks["pedestrians"], connectivity=8)
        phase = np.zeros(masks["pedestrians"].shape, np.float32)
        for i in range(1, nlab):
            phase[labels == i] = (i * 1.7) % (2 * math.pi)
        dx = (2.6 * np.sin(2 * math.pi * t + phase) * factors["pedestrians"]).astype(np.float32)
        dy = (0.7 * np.sin(4 * math.pi * t + phase) * factors["pedestrians"]).astype(np.float32)
        _apply(out, plate, masks["pedestrians"], dx, dy)

    if np.any(masks["sky"]):
        dx = (18.0 * s1 * factors["sky"]).astype(np.float32)
        dy = (1.6 * s1 * factors["sky"]).astype(np.float32)
        _apply(out, plate, masks["sky"], dx, dy)
        breath = (8.0 * s1 * np.sin(xs * 0.028 + ys * 0.011) * factors["sky"]).astype(np.float32)
        region = masks["sky"] > 0
        lifted = out.astype(np.float32)
        lifted[region] += breath[region, None]
        out[region] = np.clip(lifted[region], 0, 255).astype(np.uint8)

    life = life_union(masks)
    if not np.array_equal(out[~life], plate[~life]):
        raise SystemExit("architecture pixel moved; refusing to encode")
    return out


def life_union(masks: dict[str, np.ndarray]) -> np.ndarray:
    life = np.zeros(next(iter(masks.values())).shape, np.bool_)
    for mask in masks.values():
        life |= mask > 0
    return life


def factors_for(masks: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    reach = {"sky": 28.0, "water": 14.0, "foliage": 14.0, "flags": 5.0, "pedestrians": 4.0}
    return {name: _factor(mask, reach[name]) for name, mask in masks.items()}


def coverage(masks: dict[str, np.ndarray]) -> dict[str, float]:
    total = float(next(iter(masks.values())).size)
    out = {name: round(float((mask > 0).sum()) / total, 4) for name, mask in masks.items()}
    out["life"] = round(float(life_union(masks).mean()), 4)
    return out


def moving_mae(plate: np.ndarray, frame: np.ndarray, life: np.ndarray) -> float:
    if not np.any(life):
        return 0.0
    return float(np.abs(frame.astype(np.int16) - plate.astype(np.int16))[life].mean())


def wide_match(scene: dict, plate: np.ndarray) -> dict | None:
    path = (
        ROOT
        / "library/world/Netherlands"
        / scene["folder"]
        / f"{scene['entry_id'].lower()}-daylight-16x9.png"
    )
    im = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if im is None or im.shape[0] < PHOTO_H or im.shape[1] < OUT_W:
        return None
    wide = im[:PHOTO_H]
    if wide.shape[1] <= OUT_W:
        return None
    # The 4:5 plate has to be a window of this same daylight photograph.
    step = 4
    plate_s = plate[:, ::2].astype(np.int16)
    best_x = 0
    best = 1e9
    for x in range(0, wide.shape[1] - OUT_W + 1, step):
        mae = float(np.abs(wide[:, x : x + OUT_W][:, ::2].astype(np.int16) - plate_s).mean())
        if mae < best:
            best = mae
            best_x = x
    # Refine within the step.
    for x in range(max(0, best_x - step), min(wide.shape[1] - OUT_W, best_x + step) + 1):
        mae = float(np.abs(wide[:, x : x + OUT_W].astype(np.int16) - plate.astype(np.int16)).mean())
        if mae < best:
            best = mae
            best_x = x
    return {"wide": wide, "x0": int(best_x), "mae": round(best, 3), "path": str(path.relative_to(ROOT))}


def pan_amplitude(wide_w: int, x0: int, subject_cx: float, subject_left: float, subject_right: float) -> int:
    """Largest slow shift that keeps the subject inside the central band."""
    # Subject centroid, measured inside the anchor window, must stay in the middle half.
    lo, hi = 0.28 * OUT_W, 0.72 * OUT_W
    # At +A the centroid moves left in the frame.
    limit_pos = subject_cx - lo
    limit_neg = hi - subject_cx
    # Subject bbox must remain inside the frame.
    limit_pos = min(limit_pos, subject_left - 8)
    limit_neg = min(limit_neg, (OUT_W - 8) - subject_right)
    # Window must stay on the photograph.
    limit_pos = min(limit_pos, x0)
    limit_neg = min(limit_neg, wide_w - OUT_W - x0)
    amp = int(math.floor(min(limit_pos, limit_neg, MAX_PAN_PX)))
    return max(0, amp)


def subject_span(plate: np.ndarray, masks: dict[str, np.ndarray]) -> tuple[float, float, float]:
    gray = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gx = np.abs(np.diff(gray, axis=1, prepend=gray[:, :1]))
    structure = (masks["sky"] == 0) & (gx > 12)
    if int(structure.sum()) < 500:
        return OUT_W / 2, OUT_W * 0.2, OUT_W * 0.8
    xs = np.arange(plate.shape[1])[None, :]
    weight = gx * structure
    cx = float((weight * xs).sum() / weight.sum())
    cols = structure.any(axis=0)
    idx = np.flatnonzero(cols)
    return cx, float(idx[0]), float(idx[-1])


def render_pan(wide: np.ndarray, x0: int, amplitude: int, n: int) -> np.ndarray:
    t = n / FRAMES
    shift = amplitude * math.sin(2 * math.pi * t)
    x = int(round(x0 + shift))
    x = max(0, min(wide.shape[1] - OUT_W, x))
    return wide[:, x : x + OUT_W].copy()


def encode(frames, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OUT_W}x{PHOTO_H}",
        "-r", str(FPS), "-i", "-",
        "-frames:v", str(FRAMES),
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-an",
        "-movflags", "+faststart",
        str(dest),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    for frame_bgr in frames:
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        proc.stdin.write(rgb.tobytes())
    proc.stdin.close()
    code = proc.wait()
    if code != 0:
        raise SystemExit(f"ffmpeg failed for {dest} ({code})")


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


def write_overlay(plate: np.ndarray, masks: dict[str, np.ndarray], dest: Path) -> None:
    overlay = plate.copy()
    colors = {
        "sky": (40, 180, 255),
        "water": (255, 80, 20),
        "foliage": (40, 180, 40),
        "flags": (40, 40, 220),
        "pedestrians": (220, 40, 220),
    }
    for name, color in colors.items():
        mask = masks[name] > 0
        overlay[mask] = (overlay[mask] * 0.45 + np.array(color) * 0.55).astype(np.uint8)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(dest), overlay, [int(cv2.IMWRITE_JPEG_QUALITY), 80])


def debug_scene(scene: dict, debug_dir: Path) -> dict:
    plate, _full, path = load_daylight(scene)
    masks = build_masks(plate)
    cov = coverage(masks)
    factors = factors_for(masks)
    peak = render_ambient(plate, masks, factors, FRAMES // 8)
    life = life_union(masks)
    move = moving_mae(plate, peak, life)
    locked = ~life
    lock = float(np.abs(peak.astype(np.int16) - plate.astype(np.int16))[locked].mean()) if locked.any() else 0.0
    match = wide_match(scene, plate)
    cx, left, right = subject_span(plate, masks)
    amp = 0
    if match is not None:
        amp = pan_amplitude(match["wide"].shape[1], match["x0"], cx, left, right)
    slug = scene["entry_id"].lower()
    write_overlay(plate, masks, debug_dir / f"{slug}-mask.jpg")
    cv2.imwrite(str(debug_dir / f"{slug}-peak.jpg"), peak, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    weather = daylight_weather(scene["entry_id"])
    if weather.get("is_day") != 1:
        raise SystemExit(f"{scene['entry_id']} daylight weather is_day={weather.get('is_day')}; night scenes get no clip")
    row = {
        "entry_id": scene["entry_id"],
        "coverage": cov,
        "moving_mae_peak": round(move, 3),
        "locked_mae_peak": round(lock, 3),
        "wide_match_mae": None if match is None else match["mae"],
        "wide_x0": None if match is None else match["x0"],
        "pan_amplitude_px": amp,
        "subject_cx": round(cx, 1),
        "feels_dead": cov["life"] < DEAD_LIFE or move < DEAD_MOVE,
    }
    print(
        f"{scene['entry_id']} life={cov['life']:.3f} sky={cov['sky']:.3f} water={cov['water']:.3f} "
        f"foliage={cov['foliage']:.3f} flags={cov['flags']:.3f} people={cov['pedestrians']:.3f} "
        f"move={move:.2f} lock={lock:.3f} wideMAE={row['wide_match_mae']} pan={amp} dead={row['feels_dead']}"
    )
    return row


def update_manifest(scene: dict, row: dict) -> None:
    path = ROOT / "manifests" / f"{scene['entry_id']}.json"
    data = json.loads(path.read_text())
    data["file_motion_10s_4x5"] = row["path"].split("library/world/", 1)[1]
    data["file_motion_poster"] = row["poster"].split("library/world/", 1)[1]
    data["motion_clip"] = {
        "status": "Candidate",
        "work_order": "wo-nl-360-rebuild-2026-10-02",
        "batch": 3,
        "method": row["method"],
        "duration_s": 10.0,
        "width": 864,
        "height": 1080,
        "fps": 24,
        "format": "4:5",
        "camera": row["camera"],
        "anchor": row["anchor"].split("library/world/", 1)[1],
        "anchor_kind": "genuine-daylight 4:5 master; label bar cropped; night master not used",
        "label_bar_px_cropped": BAR,
        "life": row["life"],
        "forbidden_method_not_used": "orbit, sweep, viewpoint interpolation, optical-flow blend between generated views",
        "qc": "Candidate only. Not Cosmo QC. Not approved. Do not merge.",
        "cosmo_qc_required": True,
        "do_not_merge": True,
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def render_scene(scene: dict) -> dict:
    plate, _full, path = load_daylight(scene)
    weather = daylight_weather(scene["entry_id"])
    if weather.get("is_day") != 1:
        raise SystemExit(f"{scene['entry_id']} is night; refusing a clip")
    masks = build_masks(plate)
    cov = coverage(masks)
    factors = factors_for(masks)
    peak = render_ambient(plate, masks, factors, FRAMES // 8)
    life = life_union(masks)
    move = moving_mae(plate, peak, life)
    feels_dead = cov["life"] < DEAD_LIFE or move < DEAD_MOVE
    match = wide_match(scene, plate) if feels_dead else None
    method = "static-ambient"
    camera = "locked"
    amplitude = 0
    if feels_dead:
        if match is None or match["mae"] > 8:
            raise SystemExit(
                f"{scene['entry_id']} ambient is dead and the daylight 16:9 is not the same plate "
                f"(match={None if match is None else match['mae']}). Refusing a sweep."
            )
        cx, left, right = subject_span(plate, masks)
        amplitude = pan_amplitude(match["wide"].shape[1], match["x0"], cx, left, right)
        if amplitude < MIN_PAN_PX:
            raise SystemExit(
                f"{scene['entry_id']} ambient is dead and a subject-pinned pan only has {amplitude}px. "
                "Refusing to invent travel."
            )
        method = "subject-pinned slow pan"
        camera = "subject-pinned slow pan"
        # Frame 0 of the pan must be the daylight 4:5 anchor.
        origin = render_pan(match["wide"], match["x0"], amplitude, 0)
        if float(np.abs(origin.astype(np.int16) - plate.astype(np.int16)).mean()) > 8:
            raise SystemExit(f"{scene['entry_id']} pan origin left the daylight 4:5 anchor")

    rel = f"Netherlands/{scene['folder']}/{scene['entry_id'].lower()}-motion-10s-4x5.mp4"
    poster_rel = f"Netherlands/{scene['folder']}/{scene['entry_id'].lower()}-motion-10s-4x5-poster.jpg"
    dest = ROOT / "library/world" / rel
    poster = ROOT / "library/world" / poster_rel

    def frames():
        for i in range(FRAMES):
            if method == "static-ambient":
                if i == 0:
                    yield plate
                else:
                    yield render_ambient(plate, masks, factors, i)
            else:
                assert match is not None
                yield render_pan(match["wide"], match["x0"], amplitude, i)

    encode(frames(), dest)
    cv2.imwrite(str(poster), plate, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    info = probe(dest)
    stream = info["streams"][0]
    duration = float(info["format"]["duration"])
    if int(stream["width"]) != OUT_W or int(stream["height"]) != PHOTO_H:
        raise SystemExit(f"{scene['entry_id']} encoded {stream['width']}x{stream['height']}")
    if abs(duration - 10.0) > 0.05:
        raise SystemExit(f"{scene['entry_id']} duration {duration} is not 10.0s")
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    row = {
        "entry_id": scene["entry_id"],
        "caption": scene["caption"],
        "method": method,
        "camera": camera,
        "orbit": False,
        "life": scene["life"],
        "life_coverage": cov,
        "moving_mae_peak": round(move, 3),
        "feels_dead": feels_dead,
        "pan_amplitude_px": amplitude,
        "duration_s": duration,
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "frames": int(stream.get("nb_frames") or FRAMES),
        "fps": FPS,
        "anchor": str(path.relative_to(ROOT)),
        "anchor_crop": f"top {OUT_W}x{PHOTO_H} (label bar and hairline removed)",
        "path": f"library/world/{rel}",
        "poster": f"library/world/{poster_rel}",
        "sha256": digest,
        "bytes": dest.stat().st_size,
        "open_meteo": weather,
        "cosmo_qc_required": True,
        "do_not_merge": True,
    }
    update_manifest(scene, row)
    print(
        f"{scene['entry_id']} {method} life={cov['life']:.3f} move={move:.2f} "
        f"{stream['width']}x{stream['height']} {duration}s pan={amplitude}"
    )
    return row


def main() -> None:
    debug = "--debug" in sys.argv
    if debug:
        debug_dir = Path("/tmp/nl360-b3")
        rows = [debug_scene(scene, debug_dir) for scene in SCENES]
        (debug_dir / "summary.json").write_text(json.dumps(rows, indent=2) + "\n")
        print("wrote", debug_dir)
        return
    rows = [render_scene(scene) for scene in SCENES]
    out = ROOT / "evidence/motion/NL-360-rebuild-batch3-2026-10-02.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "work_order": "wo-nl-360-rebuild-2026-10-02",
        "batch": 3,
        "of": 6,
        "status": "Candidate",
        "cosmo_qc_required": True,
        "do_not_merge": True,
        "qc": "Not Cosmo QC. Not approved. Do not merge.",
        "held_prs_not_touched": [32, 33, 34, 35, 36, 37, 38],
        "method_default": "static-ambient",
        "method_fallback": "subject-pinned slow pan",
        "not_used": [
            "orbit",
            "sweep",
            "viewpoint interpolation",
            "optical-flow blend between generated views",
            "night master",
            "finished night master",
            "verbatim re-roll of a failed prompt",
        ],
        "spec": {
            "duration_s": 10.0,
            "width": 864,
            "height": 1080,
            "fps": 24,
            "format": "4:5",
            "label_bar_px_cropped": BAR,
        },
        "scenes": rows,
    }
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print("wrote", out)


if __name__ == "__main__":
    main()
