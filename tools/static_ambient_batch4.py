#!/usr/bin/env python3
"""Static-camera ambient clips for Netherlands 360 rebuild batch 4.

The camera stays locked on the genuine daylight 4:5 master. The 190px label
bar under the photo is cropped off before any frame is made. Only sky, water,
foliage, and flags already in the plate are displaced, and only inside their
own masks, so architecture cannot smear, spawn, or flip.

This is not an orbit, a sweep, or an interpolation between generated views.
Night masters are not read. If a plate has almost no in-frame life, the
fallback is a subject-pinned slow pan of this same plate: one sine shift that
returns to the anchor, with the subject kept inside the frame. No second
viewpoint is generated.
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
DEAD_STRUCTURAL = 0.022  # water + foliage + flags; sky alone can be a flat overcast

SCENES = (
    {
        "entry_id": "NL-01-050",
        "folder": "Valkenburg",
        "caption": "Valkenburg Castle, Valkenburg",
        "life": "Clouds above the ruins and the trees on the slope. The limestone walls stay locked. The flags stay with the stone.",
    },
    {
        "entry_id": "NL-01-051",
        "folder": "Thorn",
        "caption": "Abbey square, Thorn",
        "life": "The white abbey fills the square. Canal, trees, and flags are too thin, and the white walls read as cloud, so the camera eases and the abbey stays framed.",
    },
    {
        "entry_id": "NL-01-052",
        "folder": "Vaals",
        "caption": "Vaalserberg, Vaals",
        "life": "The three flags and the woodland. The tripoint stone and paths stay locked. No crowd is added.",
    },
    {
        "entry_id": "NL-01-053",
        "folder": "Lelystad",
        "caption": "Bataviawerf, Lelystad",
        "life": "Harbour water, clouds, and the quay trees. The museum sheds stay locked. The empty Batavia berth is not filled.",
    },
    {
        "entry_id": "NL-01-054",
        "folder": "Urk",
        "caption": "Harbour, Urk",
        "life": "Harbour water, clouds, and foliage. The lighthouse, hulls, and flags stay locked.",
    },
    {
        "entry_id": "NL-01-055",
        "folder": "Schokland",
        "caption": "Schokland Museum, Schokland",
        "life": "Clouds and the grass on the former island. The wooden church and museum houses stay locked.",
    },
    {
        "entry_id": "NL-01-058",
        "folder": "Franeker",
        "caption": "Eise Eisinga Planetarium, Franeker",
        "life": "Clouds in the blue sky, the canal, and the trees. The clock-gable house stays locked. No dome is added.",
    },
    {
        "entry_id": "NL-01-059",
        "folder": "Hindeloopen",
        "caption": "Waterfront, Hindeloopen",
        "life": "Clouds, harbour water, trees, and flags. Houses and the church tower stay locked.",
    },
    {
        "entry_id": "NL-01-061",
        "folder": "Bourtange",
        "caption": "Vesting Bourtange, Bourtange",
        "life": "Clouds, the moat, and the grass on the bastion. The bridge, gate, and mill stay locked.",
    },
    {
        "entry_id": "NL-01-062",
        "folder": "Borger",
        "caption": "Hunebed D27, Borger",
        "life": "Clouds and the grass around the capstones. The stones and the museum front stay locked.",
    },
)


def anchor_path(scene: dict) -> Path:
    return (
        ROOT
        / "library/world/Netherlands"
        / scene["folder"]
        / f"{scene['entry_id'].lower()}-daylight-4x5.png"
    )


def out_path(scene: dict) -> Path:
    return (
        ROOT
        / "library/world/Netherlands"
        / scene["folder"]
        / f"{scene['entry_id'].lower()}-motion-10s-4x5.mp4"
    )


def poster_path(scene: dict) -> Path:
    return (
        ROOT
        / "library/world/Netherlands"
        / scene["folder"]
        / f"{scene['entry_id'].lower()}-motion-10s-4x5-poster.jpg"
    )


def crop_plate(path: Path) -> np.ndarray:
    im = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if im is None:
        raise SystemExit(f"missing anchor {path}")
    if im.shape[1] != PHOTO_W or im.shape[0] < PHOTO_H + 2:
        raise SystemExit(f"{path} is {im.shape[1]}x{im.shape[0]}, expected {PHOTO_W}x>={PHOTO_H + 2}")
    plate = im[:PHOTO_H].copy()
    # Two hairline rows sit at y=1080, then the #0e0e12 label bar. Text on the
    # bar raises its std, so the check is the flat dark field under the hairline.
    field = im[PHOTO_H + 4 : PHOTO_H + 24]
    if float(field.mean()) > 40 or float(field.std()) > 12:
        raise SystemExit(f"{path} rows below the hairline do not look like the label bar")
    if float(plate[-1].mean()) < 20 and float(plate[-1].std()) < 4:
        raise SystemExit(f"{path} bottom photo row looks like the label bar")
    return plate


def _components(mask: np.ndarray, pred) -> np.ndarray:
    n, labels, stats, _ = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), connectivity=4)
    keep = np.zeros(mask.shape, np.uint8)
    for i in range(1, n):
        x, y, w, h, area = (int(v) for v in stats[i])
        if pred(x, y, w, h, area):
            keep[labels == i] = 255
    return keep


def _skyline(color: np.ndarray, mag: np.ndarray) -> np.ndarray:
    """First row per column where the sky gives way to a hard edge and stays non-sky."""
    height, width = color.shape
    blocked = (mag > 42) | (~color)
    # Ignore texture in the top 36 rows so a thin cloud edge does not end the sky.
    blocked[:36, :] = False
    # A cloud edge is a one-pixel block with sky colour returning underneath.
    run = np.ones(width, dtype=bool)
    skyline = np.full(width, height, np.int32)
    seen = np.zeros(width, dtype=bool)
    # Walk in bands of 4 so a soft cloud does not trip the cut.
    for y in range(36, height - 8, 2):
        window = blocked[y : y + 8].all(axis=0)
        hard = (mag[y] > 55) & (~color[y])
        cut = (window | hard) & run & ~seen
        skyline[cut] = y
        seen |= cut
        run &= color[y] | ~blocked[y]
        if seen.all():
            break
    return skyline


def build_masks(plate: np.ndarray) -> dict[str, np.ndarray]:
    hsv = cv2.cvtColor(plate, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    gray = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(gx, gy)
    height, width = h.shape
    yy = np.arange(height)[:, None]

    overcast = (s < 62) & (v > 158)
    blue_sky = (h >= 95) & (h <= 125) & (s >= 35) & (s < 220) & (v > 130)
    sky_color = overcast | blue_sky
    sky_color[(h >= 32) & (h <= 92) & (s > 42)] = False
    sky_color[((h < 10) | (h > 170)) & (s > 80)] = False
    skyline = _skyline(sky_color, mag)
    sky = np.zeros((height, width), np.uint8)
    cols = np.arange(width)
    sky[(yy < skyline[None, :]) & sky_color & (mag < 36)] = 255
    sky = _components(sky, lambda x, y, w, hh, area: y <= 8 and area > 400)
    sky = cv2.erode(sky, np.ones((3, 3), np.uint8), iterations=1)
    # A white tower or facade is smooth like cloud, but it sits between vertical
    # edges. Open sky does not. Drop sky pixels near a vertical edge.
    vedge = (np.abs(gx) > 22).astype(np.uint8)
    gap = cv2.distanceTransform(1 - vedge, cv2.DIST_L2, 3)
    sky[gap < 16] = 0
    sky = _components(sky, lambda x, y, w, hh, area: y <= 12 and area > 300)

    red = (((h <= 8) | (h >= 170)) & (s >= 140) & (v >= 80)).astype(np.uint8) * 255
    blue = ((h >= 100) & (h <= 132) & (s >= 150) & (v >= 70) & (sky == 0)).astype(np.uint8) * 255
    flag_cand = cv2.bitwise_or(red, blue)
    flag_cand[sky > 0] = 0

    def flag_pred(x, y, w, hh, area):
        if not (80 <= area <= 28000):
            return False
        if hh > 360 or w > 220:
            return False
        if hh < 12 or w < 8:
            return False
        # Horizontal red roofs and brick courses are wider than they are tall.
        if w > hh * 2.1 and w > 70:
            return False
        if y > height * 0.78:
            return False
        return True

    flags = _components(flag_cand, flag_pred)
    # Pull in the white stripe of a flag without swallowing a white facade.
    if np.any(flags):
        near = cv2.dilate(flags, np.ones((7, 7), np.uint8), iterations=1)
        white_cloth = (s < 70) & (v > 150) & (mag < 40) & (near > 0) & (sky == 0)
        white_cloth = _components(
            white_cloth.astype(np.uint8) * 255,
            lambda x, y, w, hh, area: 20 <= area <= 12000 and hh < 280 and w < 180,
        )
        flags = cv2.bitwise_or(flags, white_cloth)
    flags = cv2.erode(flags, np.ones((2, 2), np.uint8), iterations=1)
    sky[flags > 0] = 0

    blue_water = (h >= 85) & (h <= 130) & (s >= 25) & (s <= 180) & (v >= 30) & (v <= 185)
    green_water = (h >= 35) & (h <= 95) & (s >= 18) & (s <= 130) & (v >= 28) & (v <= 160)
    blur = cv2.blur(gray.astype(np.float32), (11, 11))
    blur2 = cv2.blur(gray.astype(np.float32) ** 2, (11, 11))
    local = np.sqrt(np.maximum(blur2 - blur ** 2, 0))
    gray_water = (s < 42) & (v > 45) & (v < 165) & (local < 7.5) & (yy > int(height * 0.58))
    water_cand = ((blue_water | green_water | gray_water) & (sky == 0) & (flags == 0) & (yy > int(height * 0.34))).astype(np.uint8) * 255
    water_cand[(h >= 35) & (h <= 88) & (s > 55) & (local > 14)] = 0
    water = _components(
        water_cand,
        lambda x, y, w, hh, area: area > 2500 and w > 60 and w > hh * 0.55 and (y + hh / 2) > height * 0.42,
    )
    water = cv2.erode(water, np.ones((3, 3), np.uint8), iterations=1)
    water = _components(
        water,
        lambda x, y, w, hh, area: area > 900 and w > 36 and hh < w * 2.2 and (y + hh / 2) > height * 0.48,
    )

    # Green grass and leaf. Beige marl and whitewash sit at hue ~15–24 and a
    # higher value, so they are not foliage. Dark autumn canopy is allowed
    # only when it is textured and not bright stone.
    green = (h >= 30) & (h <= 95) & (s >= 32) & (v >= 22) & (v <= 200)
    canopy = (h >= 12) & (h <= 42) & (s >= 62) & (v >= 22) & (v <= 112) & (local > 12)
    fol_cand = ((green | canopy) & (sky == 0) & (water == 0) & (flags == 0)).astype(np.uint8) * 255
    foliage = _components(fol_cand, lambda x, y, w, hh, area: area > 140)
    foliage = cv2.erode(foliage, np.ones((3, 3), np.uint8), iterations=1)
    if np.any(foliage):
        nlab, labels, stats, _ = cv2.connectedComponentsWithStats(foliage, connectivity=4)
        for i in range(1, nlab):
            sel = labels == i
            if int(v[sel].mean()) > 145 or (int(h[sel].mean()) < 26 and int(v[sel].mean()) > 118):
                foliage[sel] = 0
    foliage[water > 0] = 0
    foliage[flags > 0] = 0
    flags[foliage > 0] = 0
    flags[water > 0] = 0
    water[sky > 0] = 0
    return {"sky": sky, "water": water, "foliage": foliage, "flags": flags, "skyline": skyline}


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


def render_ambient(plate: np.ndarray, masks: dict[str, np.ndarray], factors: dict[str, np.ndarray], n: int, sky_breath: float) -> np.ndarray:
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
        dx = (6.0 * np.sin(4 * math.pi * t + ys * 0.11) * factors["flags"]).astype(np.float32)
        dy = (1.4 * s2 * factors["flags"]).astype(np.float32)
        _apply(out, plate, masks["flags"], dx, dy)

    if np.any(masks["sky"]) and (abs(s1) > 0 or n == 0):
        dx = (16.0 * s1 * factors["sky"]).astype(np.float32)
        dy = (1.6 * s1 * factors["sky"]).astype(np.float32)
        _apply(out, plate, masks["sky"], dx, dy)
        if sky_breath > 0:
            breath = (sky_breath * s1 * np.sin(xs * 0.03 + ys * 0.012) * factors["sky"]).astype(np.float32)
            region = masks["sky"] > 0
            lifted = out.astype(np.float32)
            lifted[region] += breath[region, None]
            out[region] = np.clip(lifted[region], 0, 255).astype(np.uint8)

    life = (masks["sky"] | masks["water"] | masks["foliage"] | masks["flags"]) > 0
    if not np.array_equal(out[~life], plate[~life]):
        raise SystemExit("architecture pixel moved; refusing to encode")
    return out


def render_pan(plate: np.ndarray, n: int) -> np.ndarray:
    """Slow horizontal pan of this one plate. Frame 0 is the anchor.

    The shift is a sine that peaks at 14px and returns to zero, so the loop
    closes. A matching zoom creates the margin so the edge is not smeared.
    The subject, which fills the centre of these plates, stays framed.
    """
    t = n / FRAMES
    env = math.sin(2 * math.pi * t)
    # Exact anchor at the start, the midpoint, and the end of the loop.
    if abs(env) < 1e-6:
        return plate.copy()
    mag = abs(env)
    scale = 1.0 + 0.045 * mag
    shift = 14.0 * env
    height, width = plate.shape[:2]
    cx = (width - 1) / 2.0
    cy = (height - 1) / 2.0
    xs = np.arange(width, dtype=np.float32)
    ys = np.arange(height, dtype=np.float32)
    map_x = (cx + (xs[None, :] - cx - shift) / scale).astype(np.float32)
    map_y = (cy + (ys[:, None] - cy) / scale).astype(np.float32)
    map_x = np.broadcast_to(map_x, (height, width)).copy()
    map_y = np.broadcast_to(map_y, (height, width)).copy()
    return cv2.remap(plate, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)


def coverage(masks: dict[str, np.ndarray]) -> dict[str, float]:
    total = float(PHOTO_H * PHOTO_W)
    return {name: round(float(np.count_nonzero(masks[name])) / total, 4) for name in ("sky", "water", "foliage", "flags")}


def sky_texture(plate: np.ndarray, sky: np.ndarray) -> float:
    if not np.any(sky):
        return 0.0
    gray = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY)
    return float(gray[sky > 0].std())


def choose_method(cov: dict[str, float], texture: float) -> tuple[str, float]:
    structural = cov["water"] + cov["foliage"] + cov["flags"]
    # A flat overcast sky does not read as motion under a displacement.
    # A small brightness wave is used only when the sky already has cloud texture.
    breath = 6.0 if texture >= 14.0 and cov["sky"] >= 0.04 else 0.0
    if structural >= DEAD_STRUCTURAL or (cov["sky"] >= 0.08 and texture >= 14.0):
        return "static-ambient", breath
    return "subject-pinned-slow-pan", 0.0


def encode(frames, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{PHOTO_W}x{PHOTO_H}",
        "-r", str(FPS), "-i", "-",
        "-frames:v", str(FRAMES),
        "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "18", "-preset", "medium", "-movflags", "+faststart",
        str(dest),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for frame in frames:
            proc.stdin.write(np.ascontiguousarray(frame).tobytes())
    finally:
        proc.stdin.close()
    err = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
    code = proc.wait()
    if code != 0:
        raise SystemExit(f"ffmpeg failed for {dest}\n{err[-2000:]}")


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
    cov = coverage(masks)
    texture = sky_texture(plate, masks["sky"])
    method, breath = choose_method(cov, texture)
    overlay = plate.copy()
    colors = {"sky": (255, 180, 40), "water": (255, 80, 20), "foliage": (40, 180, 40), "flags": (40, 40, 220)}
    for name, color in colors.items():
        sel = masks[name] > 0
        overlay[sel] = (0.55 * overlay[sel] + 0.45 * np.array(color)).astype(np.uint8)
    factors = {k: _factor(masks[k], {"sky": 28, "water": 14, "foliage": 16, "flags": 6}[k]) for k in ("sky", "water", "foliage", "flags")}
    if method == "static-ambient":
        peak = render_ambient(plate, masks, factors, FRAMES // 4, breath)
    else:
        peak = render_pan(plate, FRAMES // 4)
    debug_dir.mkdir(parents=True, exist_ok=True)
    slug = scene["entry_id"]
    cv2.imwrite(str(debug_dir / f"{slug}-mask.jpg"), overlay, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    cv2.imwrite(str(debug_dir / f"{slug}-peak.jpg"), peak, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    diff = cv2.absdiff(peak, plate)
    heat = cv2.applyColorMap(cv2.min(diff * 4, 255), cv2.COLORMAP_INFERNO)
    cv2.imwrite(str(debug_dir / f"{slug}-diff.jpg"), heat, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    life = (masks["sky"] | masks["water"] | masks["foliage"] | masks["flags"]) > 0
    if method == "static-ambient":
        locked_mae = 0.0 if np.array_equal(peak[~life], plate[~life]) else float(np.abs(peak[~life].astype(np.int16) - plate[~life].astype(np.int16)).mean())
        moving_mae = float(np.abs(peak[life].astype(np.int16) - plate[life].astype(np.int16)).mean()) if life.any() else 0.0
    else:
        locked_mae = None
        moving_mae = float(diff.mean())
    return {
        "entry_id": slug,
        "method": method,
        "sky_breath": breath,
        "sky_texture": round(texture, 2),
        "coverage": cov,
        "structural": round(cov["water"] + cov["foliage"] + cov["flags"], 4),
        "locked_mae": locked_mae,
        "moving_mae": round(moving_mae, 3),
    }


def main() -> None:
    import sys

    debug = "--debug" in sys.argv
    only = [a for a in sys.argv[1:] if a.startswith("NL-")]
    rows = []
    debug_dir = Path("/tmp/nl-batch4")
    for scene in SCENES:
        if only and scene["entry_id"] not in only:
            continue
        if debug:
            row = debug_scene(scene, debug_dir)
            print(json.dumps(row))
            rows.append(row)
            continue
        plate = crop_plate(anchor_path(scene))
        masks = build_masks(plate)
        cov = coverage(masks)
        texture = sky_texture(plate, masks["sky"])
        method, breath = choose_method(cov, texture)
        factors = {k: _factor(masks[k], {"sky": 28, "water": 14, "foliage": 16, "flags": 6}[k]) for k in ("sky", "water", "foliage", "flags")}
        if method == "static-ambient":
            peak = render_ambient(plate, masks, factors, FRAMES // 4, breath)
            life = (masks["sky"] | masks["water"] | masks["foliage"] | masks["flags"]) > 0
            if not np.array_equal(peak[~life], plate[~life]):
                raise SystemExit(f"{scene['entry_id']} locked pixels moved")
            moving_mae = float(np.abs(peak[life].astype(np.int16) - plate[life].astype(np.int16)).mean()) if life.any() else 0.0
            if moving_mae < 0.45:
                # Static life did not read. Switch this one plate to a slow pan.
                method = "subject-pinned-slow-pan"
                breath = 0.0

            def frames_ambient(plate=plate, masks=masks, factors=factors, breath=breath, method=method):
                for i in range(FRAMES):
                    if method == "static-ambient":
                        if i == 0:
                            yield plate
                        else:
                            yield render_ambient(plate, masks, factors, i, breath)
                    else:
                        yield render_pan(plate, i)

            encode(frames_ambient(), out_path(scene))
        else:
            moving_mae = None

            def frames_pan(plate=plate):
                for i in range(FRAMES):
                    yield render_pan(plate, i)

            encode(frames_pan(), out_path(scene))
        poster = poster_path(scene)
        poster.parent.mkdir(parents=True, exist_ok=True)
        ok = cv2.imwrite(str(poster), plate, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if not ok:
            raise SystemExit(f"poster write failed {poster}")
        info = probe(out_path(scene))
        stream = info["streams"][0]
        duration = float(info["format"]["duration"])
        if int(stream["width"]) != PHOTO_W or int(stream["height"]) != PHOTO_H:
            raise SystemExit(f"{scene['entry_id']} is {stream['width']}x{stream['height']}")
        if abs(duration - 10.0) > 0.05:
            raise SystemExit(f"{scene['entry_id']} duration {duration}")
        row = {
            "entry_id": scene["entry_id"],
            "caption": scene["caption"],
            "method": method,
            "life": (
                scene["life"]
                if method == "static-ambient"
                else "In-frame life was too thin to carry a locked camera. Slow pan of this one daylight plate, sine of 14px with a matching zoom so the edge is not smeared. The subject stays framed. " + scene["life"]
            ),
            "coverage": cov,
            "sky_texture": round(texture, 2),
            "sky_breath": breath,
            "moving_mae_peak": None if moving_mae is None else round(moving_mae, 3),
            "duration_s": duration,
            "width": int(stream["width"]),
            "height": int(stream["height"]),
            "frames": int(stream.get("nb_frames") or FRAMES),
            "fps": FPS,
            "anchor": str(anchor_path(scene).relative_to(ROOT)),
            "anchor_kind": "genuine-daylight 4:5 master; night master not used; finished master not used",
            "anchor_crop": "top 864x1080; 190px label bar and hairline removed",
            "path": str(out_path(scene).relative_to(ROOT)),
            "poster": str(poster_path(scene).relative_to(ROOT)),
            "camera": "locked" if method == "static-ambient" else "subject-pinned slow pan, sine, max 14px, returns to anchor",
            "pedestrians": "Left on the plate. A warp would smear limbs, so people are not a life mask.",
            "forbidden_method_not_used": "orbit, sweep, viewpoint interpolation, optical-flow blend between generated views, night plate",
            "qc": "Candidate only. cosmo_qc_required=true. Not approved. Do not merge.",
        }
        print(json.dumps({k: row[k] for k in ("entry_id", "method", "coverage", "moving_mae_peak", "duration_s")}))
        rows.append(row)
    if debug:
        (debug_dir / "coverage.json").write_text(json.dumps(rows, indent=2) + "\n")
        return
    evidence = ROOT / "evidence/motion/NL-360-rebuild-batch4-2026-10-02.json"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "work_order": "wo-nl-360-rebuild-2026-10-02",
        "batch": 4,
        "approach": "static-ambient / subject-pinned slow pan",
        "cosmo_qc_required": True,
        "do_not_merge": True,
        "scenes": rows,
    }
    evidence.write_text(json.dumps(payload, indent=2) + "\n")
    print("wrote", evidence)


if __name__ == "__main__":
    main()
