#!/usr/bin/env python3
"""Static-camera ambient clips from genuine daylight 4:5 masters.

The camera is locked. Only sky, water, and foliage move, and they return to
the cropped master at the loop point. No orbit, sweep, or optical-flow blend.
The 190px label bar (and its 2px hairline) is cropped off before any motion.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BAR_AND_HAIRLINE = 190  # photo is the top 1080 rows of a 1270px master
PHOTO_H = 1080
OUT_W = 864
FPS = 24
FRAMES = 240  # exactly 10.0s
# Life masks below this fraction of the frame are too still for ambient-only.
DEAD_LIFE = 0.035

SCENES = [
    {
        "entry_id": "NL-01-021",
        "caption": "NEMO, Amsterdam",
        "city": "Amsterdam",
        "folder": "Amsterdam",
        "latitude": 52.374,
        "longitude": 4.9122,
        "life": "water in the foreground, cloud drift, tree sway",
    },
    {
        "entry_id": "NL-01-022",
        "caption": "Harbour, Volendam",
        "city": "Volendam",
        "folder": "Volendam",
        "latitude": 52.495,
        "longitude": 5.0714,
        "life": "harbour water, cloud drift, tree sway",
    },
    {
        "entry_id": "NL-01-023",
        "caption": "Harbour, Marken",
        "city": "Marken",
        "folder": "Marken",
        "latitude": 52.4597,
        "longitude": 5.1056,
        "life": "harbour water, cloud drift, tree sway",
    },
    {
        "entry_id": "NL-01-024",
        "caption": "Waag, Alkmaar",
        "city": "Alkmaar",
        "folder": "Alkmaar",
        "latitude": 52.6317,
        "longitude": 4.7486,
        "life": "cloud drift and tree sway; the weigh house stays locked",
    },
    {
        "entry_id": "NL-01-025",
        "caption": "Hoofdtoren, Hoorn",
        "city": "Hoorn",
        "folder": "Hoorn",
        "latitude": 52.6383,
        "longitude": 5.0594,
        "life": "harbour water and cloud drift",
    },
    {
        "entry_id": "NL-01-026",
        "caption": "Zuiderzeemuseum, Enkhuizen",
        "city": "Enkhuizen",
        "folder": "Enkhuizen",
        "latitude": 52.7075,
        "longitude": 5.298,
        "life": "harbour water, cloud drift, tree sway",
    },
    {
        "entry_id": "NL-01-027",
        "caption": "Markthal, Rotterdam",
        "city": "Rotterdam",
        "folder": "Rotterdam",
        "latitude": 51.92,
        "longitude": 4.4867,
        "life": "cloud drift and tree sway; the arch stays locked",
    },
    {
        "entry_id": "NL-01-028",
        "caption": "Euromast, Rotterdam",
        "city": "Rotterdam",
        "folder": "Rotterdam",
        "latitude": 51.9054,
        "longitude": 4.4668,
        "life": "cloud drift, tree sway, water at the base",
    },
    {
        "entry_id": "NL-01-029",
        "caption": "Peace Palace, The Hague",
        "city": "The Hague",
        "folder": "The Hague",
        "latitude": 52.0865,
        "longitude": 4.2958,
        "life": "fountain water, cloud drift, tree sway",
    },
    {
        "entry_id": "NL-01-030",
        "caption": "Scheveningen pier, The Hague",
        "city": "The Hague",
        "folder": "The Hague",
        "latitude": 52.1155,
        "longitude": 4.2785,
        "life": "sea surface and cloud drift",
    },
]


def box_blur(a: np.ndarray, r: int) -> np.ndarray:
    if r <= 0:
        return a
    k = 2 * r + 1
    x = a.astype(np.float32)
    pad_x = np.pad(x, ((0, 0), (r, r)), mode="edge")
    c = np.concatenate(
        [np.zeros((x.shape[0], 1), np.float32), np.cumsum(pad_x, axis=1)], axis=1
    )
    h = (c[:, k:] - c[:, :-k]) / k
    pad_y = np.pad(h, ((r, r), (0, 0)), mode="edge")
    c = np.concatenate(
        [np.zeros((1, h.shape[1]), np.float32), np.cumsum(pad_y, axis=0)], axis=0
    )
    return (c[k:, :] - c[:-k, :]) / k


def rgb_to_hsv(rgb: np.ndarray):
    x = rgb.astype(np.float32) / 255.0
    r, g, b = x[:, :, 0], x[:, :, 1], x[:, :, 2]
    mx = np.max(x, axis=2)
    mn = np.min(x, axis=2)
    df = mx - mn
    h = np.zeros_like(mx)
    safe = df > 1e-6
    rmax = safe & (mx == r)
    gmax = safe & (mx == g)
    bmax = safe & (mx == b)
    h[rmax] = np.mod((g[rmax] - b[rmax]) / df[rmax], 6.0)
    h[gmax] = ((b[gmax] - r[gmax]) / df[gmax]) + 2.0
    h[bmax] = ((r[bmax] - g[bmax]) / df[bmax]) + 4.0
    h = np.mod(h / 6.0, 1.0)
    s = np.where(mx > 1e-6, df / np.maximum(mx, 1e-6), 0.0)
    return h, s, mx


def life_masks(rgb: np.ndarray):
    """Soft masks in 0..1. Buildings, streets, boats, and people stay near 0.

    Sky stops at the first real horizontal edge in each column, so a tower
    face cannot inherit the cloud drift. Water is only the smooth cool
    surface in the lower frame (harbour and sea), not paving.
    """
    h, s, v = rgb_to_hsv(rgb)
    gray = rgb.astype(np.float32).mean(axis=2)
    gx = np.abs(np.diff(gray, axis=1, prepend=gray[:, :1]))
    gy = np.abs(np.diff(gray, axis=0, prepend=gray[:1, :]))
    edge = gx + gy
    edge_s = box_blur(edge, 1)
    lock = np.clip((edge_s - 16.0) / 24.0, 0.0, 1.0)
    local = np.sqrt(np.maximum(box_blur(gray * gray, 4) - box_blur(gray, 4) ** 2, 0.0))
    local16 = np.sqrt(np.maximum(box_blur(gray * gray, 16) - box_blur(gray, 16) ** 2, 0.0))

    height = rgb.shape[0]
    yy = np.arange(height)[:, None]
    hedge = gy > 10
    has = hedge.any(axis=0)
    skyline = np.argmax(hedge, axis=0)
    skyline = np.where(has, skyline, height).astype(np.int32)
    skyline = np.maximum(skyline - 8, 0)

    blue = (h > 0.50) & (h < 0.75) & (s > 0.08) & (v > 0.45)
    cloud = (s < 0.35) & (v > 0.58)
    sky_like = (blue | cloud) & (local < 20.0)
    # A narrow mast or spire is smooth and bright, like cloud, but it sits
    # between vertical edges. Open sky does not.
    vedge = gx > 20.0
    # distance to the nearest vertical edge, capped
    dist_l = np.full(vedge.shape, 999, np.int16)
    dist_l[:, 0] = np.where(vedge[:, 0], 0, 999)
    for x in range(1, vedge.shape[1]):
        dist_l[:, x] = np.where(vedge[:, x], 0, np.minimum(dist_l[:, x - 1] + 1, 999))
    dist_r = np.full(vedge.shape, 999, np.int16)
    dist_r[:, -1] = np.where(vedge[:, -1], 0, 999)
    for x in range(vedge.shape[1] - 2, -1, -1):
        dist_r[:, x] = np.where(vedge[:, x], 0, np.minimum(dist_r[:, x + 1] + 1, 999))
    open_gap = np.minimum(dist_l, dist_r) > 28
    sky = (yy < skyline[None, :]) & sky_like & (open_gap | (blue & (s > 0.12)))
    sky = box_blur(sky.astype(np.float32), 2)
    sky = np.clip((sky - 0.25) / 0.50, 0.0, 1.0) * (1.0 - lock)

    # Grey paving (the Markthal street, palace paths) is smooth and cool
    # enough to look like water. Real harbour water carries a blue or green cast.
    blue_water = (s > 0.07) & (rgb[:, :, 2].astype(np.int16) >= rgb[:, :, 0].astype(np.int16) + 8)
    green_water = (h > 0.22) & (h < 0.45) & (s > 0.08) & (rgb[:, :, 1] > rgb[:, :, 0])
    water = (
        (yy > int(height * 0.58))
        & (blue_water | green_water)
        & (local16 < 11.0)
        & (edge_s < 12.0)
        & (v > 0.10)
        & (v < 0.58)
        & (s < 0.50)
    )
    water = box_blur(water.astype(np.float32), 1)
    water = np.clip((water - 0.45) / 0.40, 0.0, 1.0)
    water = water * (1.0 - np.clip(lock * 1.3, 0.0, 1.0)) * (sky < 0.15)

    green = (h > 0.16) & (h < 0.48) & (s > 0.16) & (v > 0.07) & (v < 0.75) & (local > 8.0)
    foliage = box_blur(green.astype(np.float32), 1)
    foliage = np.clip((foliage - 0.35) / 0.40, 0.0, 1.0)
    foliage = foliage * (1.0 - lock) * (1.0 - np.clip(water, 0.0, 1.0)) * (sky < 0.15)
    # A real harbour is a broad sheet. Small cool patches on paving are not.
    if int((water > 0.35).sum()) < 18000:
        water = np.zeros_like(water)
    sky = sky * (1.0 - np.clip(water, 0.0, 1.0)) * (1.0 - np.clip(foliage, 0.0, 1.0))
    return sky.astype(np.float32), water.astype(np.float32), foliage.astype(np.float32)


def displace(img: np.ndarray, dx: np.ndarray, dy: np.ndarray) -> np.ndarray:
    height, width = img.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width]
    xs = np.clip(xx.astype(np.float32) + dx, 0, width - 1)
    ys = np.clip(yy.astype(np.float32) + dy, 0, height - 1)
    x0 = np.floor(xs).astype(np.int32)
    y0 = np.floor(ys).astype(np.int32)
    x1 = np.clip(x0 + 1, 0, width - 1)
    y1 = np.clip(y0 + 1, 0, height - 1)
    wx = (xs - x0)[..., None]
    wy = (ys - y0)[..., None]
    a = img[y0, x0]
    b = img[y0, x1]
    c = img[y1, x0]
    d = img[y1, x1]
    top = a * (1 - wx) + b * wx
    bot = c * (1 - wx) + d * wx
    return top * (1 - wy) + bot * wy


def fields(frame: int, height: int, width: int, sky, water, foliage):
    phase = 2.0 * np.pi * frame / FRAMES
    env = np.sin(phase)
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    sky_falloff = np.clip(1.0 - yy / (height * 0.55), 0.0, 1.0)
    dx = (
        water * env * (
            2.4 * np.sin(2 * np.pi * yy / 34.0 + 2.0 * phase)
            + 1.2 * np.sin(2 * np.pi * xx / 57.0 + phase)
        )
        + sky * env * (8.0 * sky_falloff)
        + foliage * env * (1.7 * np.sin(2 * np.pi * yy / 68.0 + phase))
    )
    dy = (
        water * env * (1.15 * np.sin(2 * np.pi * xx / 28.0 + 2.0 * phase))
        + sky * env * (1.6 * np.sin(2 * np.pi * xx / 160.0 + phase))
        + foliage * env * (1.3 * np.sin(2 * np.pi * xx / 46.0 + 1.4 * phase))
    )
    shimmer = 1.0 + water * env * 0.04 * np.sin(
        2 * np.pi * (xx / 22.0 + yy / 36.0) + 2.0 * phase
    )
    return dx.astype(np.float32), dy.astype(np.float32), shimmer.astype(np.float32)


def load_anchor(path: Path) -> np.ndarray:
    rgb = np.asarray(Image.open(path).convert("RGB"))
    if rgb.shape[1] != OUT_W or rgb.shape[0] < PHOTO_H:
        raise SystemExit(f"{path} is {rgb.shape[1]}x{rgb.shape[0]}, expected {OUT_W}x>={PHOTO_H}")
    photo = rgb[:PHOTO_H]
    if photo.shape != (PHOTO_H, OUT_W, 3):
        raise SystemExit(f"cropped anchor {path} is {photo.shape}")
    return photo


def render_frame(base: np.ndarray, sky, water, foliage, frame: int) -> np.ndarray:
    dx, dy, shimmer = fields(frame, base.shape[0], base.shape[1], sky, water, foliage)
    warped = displace(base.astype(np.float32), dx, dy)
    out = warped * shimmer[..., None]
    return np.clip(np.round(out), 0, 255).astype(np.uint8)


def encode(frames_iter, dest: Path) -> None:
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
    for frame in frames_iter:
        proc.stdin.write(frame.tobytes())
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


def main() -> None:
    rows = []
    for scene in SCENES:
        src = (
            ROOT / "library/world/Netherlands" / scene["folder"]
            / f"{scene['entry_id'].lower()}-daylight-4x5.png"
        )
        base = load_anchor(src)
        sky, water, foliage = life_masks(base)
        life = float(((sky + water + foliage) > 0.25).mean())
        method = "static-camera ambient"
        if life < DEAD_LIFE:
            raise SystemExit(
                f"{scene['entry_id']} life coverage {life:.3f} is below {DEAD_LIFE}. "
                "Refusing to invent a pan; inspect the master."
            )
        rel = f"Netherlands/{scene['folder']}/{scene['entry_id'].lower()}-motion-10s-4x5.mp4"
        poster_rel = f"Netherlands/{scene['folder']}/{scene['entry_id'].lower()}-motion-10s-4x5-poster.jpg"
        dest = ROOT / "library/world" / rel
        poster = ROOT / "library/world" / poster_rel
        peak = render_frame(base, sky, water, foliage, FRAMES // 4)
        locked = (sky + water + foliage) < 0.05
        locked_mae = float(np.abs(peak.astype(np.int16) - base.astype(np.int16))[locked].mean())
        moving = (sky + water + foliage) > 0.45
        moving_mae = float(np.abs(peak.astype(np.int16) - base.astype(np.int16))[moving].mean()) if moving.any() else 0.0
        if locked_mae > 1.25:
            raise SystemExit(f"{scene['entry_id']} locked-pixel MAE {locked_mae:.2f} — camera or structure drifted")
        if moving_mae < 0.55:
            raise SystemExit(f"{scene['entry_id']} moving-pixel MAE {moving_mae:.2f} — ambient life is dead")

        def frames():
            for i in range(FRAMES):
                if i == 0:
                    yield base
                else:
                    yield render_frame(base, sky, water, foliage, i)

        encode(frames(), dest)
        Image.fromarray(base).save(poster, quality=90, subsampling=0)
        info = probe(dest)
        stream = info["streams"][0]
        rows.append({
            "entry_id": scene["entry_id"],
            "caption": scene["caption"],
            "method": method,
            "life": scene["life"],
            "life_coverage": round(life, 4),
            "locked_mae_peak": round(locked_mae, 3),
            "moving_mae_peak": round(moving_mae, 3),
            "duration_s": float(info["format"]["duration"]),
            "width": int(stream["width"]),
            "height": int(stream["height"]),
            "frames": int(stream.get("nb_frames") or FRAMES),
            "fps": FPS,
            "anchor": str(src.relative_to(ROOT)),
            "anchor_crop": f"top {OUT_W}x{PHOTO_H} (label bar and hairline removed)",
            "path": f"library/world/{rel}",
            "poster": f"library/world/{poster_rel}",
            "latitude": scene["latitude"],
            "longitude": scene["longitude"],
        })
        print(
            f"{scene['entry_id']} {method} life={life:.3f} "
            f"lockMAE={locked_mae:.2f} moveMAE={moving_mae:.2f} "
            f"{stream['width']}x{stream['height']} {info['format']['duration']}s"
        )
    out = ROOT / "evidence/motion/NL-360-rebuild-batch2-2026-10-02.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"work_order": "wo-nl-360-rebuild-2026-10-02", "batch": 2, "scenes": rows}, indent=2) + "\n")
    print("wrote", out)


if __name__ == "__main__":
    main()
