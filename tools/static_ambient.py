#!/usr/bin/env python3
"""Netherlands motion tool.

Locked camera (default): the camera stays locked on a genuine daylight 4:5
plate. The 190px label bar under the photo is cropped off before any frame
is made. Only sky, water, foliage, and flags already in the plate are
displaced, and only inside their own masks, so architecture cannot smear,
spawn, or flip. That path is not an orbit, a sweep, or an interpolation
between generated views.

Sideways sweep (``--sweep``): a slow left-to-right glide across the genuine
daylight 16:9 plate only. The label bar is removed and the photo plate is
1920×1080. An 864-wide window then eases across about 18% of that width.
The window stays on the subject, so the subject remains centered and fully
framed and the glide does not travel past it. No locked hold, orbit, zoom,
roll, or vertical move.
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
BAR_TOP = 1080

# Genuine daylight anchors. NL-01-002 and NL-01-006..010 are the approved
# late-afternoon masters (Open-Meteo is_day 1). Their *-daylight-* files are
# derivatives of a night re-light and are not used. NL-01-017..020 night
# masters are not used; the anchor is the genuine-daylight 4:5 master.
SCENES = (
    {
        "entry_id": "NL-01-002",
        "anchor": "library/world/Netherlands/Amsterdam/nl-01-002-4x5.png",
        "out": "library/world/Netherlands/Amsterdam/nl-01-002-motion-10s-4x5.mp4",
        "poster": "library/world/Netherlands/Amsterdam/nl-01-002-motion-10s-4x5-poster.jpg",
        "anchor_kind": "approved late-afternoon master (is_day 1); derived *-daylight-* variant not used",
    },
    {
        "entry_id": "NL-01-006",
        "anchor": "library/world/Netherlands/Giethoorn/nl-01-006-4x5.png",
        "out": "library/world/Netherlands/Giethoorn/nl-01-006-motion-10s-4x5.mp4",
        "poster": "library/world/Netherlands/Giethoorn/nl-01-006-motion-10s-4x5-poster.jpg",
        "anchor_kind": "approved late-afternoon master (is_day 1); derived *-daylight-* variant not used",
    },
    {
        "entry_id": "NL-01-007",
        "anchor": "library/world/Netherlands/Rotterdam/nl-01-007-4x5.png",
        "out": "library/world/Netherlands/Rotterdam/nl-01-007-motion-10s-4x5.mp4",
        "poster": "library/world/Netherlands/Rotterdam/nl-01-007-motion-10s-4x5-poster.jpg",
        "anchor_kind": "approved late-afternoon master (is_day 1); derived *-daylight-* variant not used",
    },
    {
        "entry_id": "NL-01-008",
        "anchor": "library/world/Netherlands/Rotterdam/nl-01-008-4x5.png",
        "out": "library/world/Netherlands/Rotterdam/nl-01-008-motion-10s-4x5.mp4",
        "poster": "library/world/Netherlands/Rotterdam/nl-01-008-motion-10s-4x5-poster.jpg",
        "anchor_kind": "approved late-afternoon master (is_day 1); derived *-daylight-* variant not used",
    },
    {
        "entry_id": "NL-01-009",
        "anchor": "library/world/Netherlands/The Hague/nl-01-009-4x5.png",
        "out": "library/world/Netherlands/The Hague/nl-01-009-motion-10s-4x5.mp4",
        "poster": "library/world/Netherlands/The Hague/nl-01-009-motion-10s-4x5-poster.jpg",
        "anchor_kind": "approved late-afternoon master (is_day 1); derived *-daylight-* variant not used",
    },
    {
        "entry_id": "NL-01-010",
        "anchor": "library/world/Netherlands/Utrecht/nl-01-010-4x5.png",
        "out": "library/world/Netherlands/Utrecht/nl-01-010-motion-10s-4x5.mp4",
        "poster": "library/world/Netherlands/Utrecht/nl-01-010-motion-10s-4x5-poster.jpg",
        "anchor_kind": "approved late-afternoon master (is_day 1); derived *-daylight-* variant not used",
    },
    {
        "entry_id": "NL-01-017",
        "anchor": "library/world/Netherlands/Amsterdam/nl-01-017-daylight-4x5.png",
        "out": "library/world/Netherlands/Amsterdam/nl-01-017-motion-10s-4x5.mp4",
        "poster": "library/world/Netherlands/Amsterdam/nl-01-017-motion-10s-4x5-poster.jpg",
        "anchor_kind": "genuine-daylight 4:5 master; night master not used",
    },
    {
        "entry_id": "NL-01-018",
        "anchor": "library/world/Netherlands/Amsterdam/nl-01-018-daylight-4x5.png",
        "out": "library/world/Netherlands/Amsterdam/nl-01-018-motion-10s-4x5.mp4",
        "poster": "library/world/Netherlands/Amsterdam/nl-01-018-motion-10s-4x5-poster.jpg",
        "anchor_kind": "genuine-daylight 4:5 master; night master not used",
    },
    {
        "entry_id": "NL-01-019",
        "anchor": "library/world/Netherlands/Amsterdam/nl-01-019-daylight-4x5.png",
        "out": "library/world/Netherlands/Amsterdam/nl-01-019-motion-10s-4x5.mp4",
        "poster": "library/world/Netherlands/Amsterdam/nl-01-019-motion-10s-4x5-poster.jpg",
        "anchor_kind": "genuine-daylight 4:5 master; night master not used",
    },
    {
        "entry_id": "NL-01-020",
        "anchor": "library/world/Netherlands/Amsterdam/nl-01-020-daylight-4x5.png",
        "out": "library/world/Netherlands/Amsterdam/nl-01-020-motion-10s-4x5.mp4",
        "poster": "library/world/Netherlands/Amsterdam/nl-01-020-motion-10s-4x5-poster.jpg",
        "anchor_kind": "genuine-daylight 4:5 master; night master not used",
    },
)


def crop_plate(path: Path) -> np.ndarray:
    im = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if im is None:
        raise SystemExit(f"missing anchor {path}")
    if im.shape[1] != PHOTO_W or im.shape[0] < PHOTO_H + 2:
        raise SystemExit(f"{path} is {im.shape[1]}x{im.shape[0]}, expected {PHOTO_W}x>={PHOTO_H + 2}")
    # Photo is the top 1080 rows. The 190px bar, including its 2px hairline, starts at y=1080.
    plate = im[:PHOTO_H].copy()
    if float(plate[-1].std()) < 4:
        raise SystemExit(f"{path} bottom photo row looks like the label bar")
    return plate


def _components(mask: np.ndarray, pred) -> np.ndarray:
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=4)
    keep = np.zeros(mask.shape, np.uint8)
    for i in range(1, n):
        x, y, w, h, area = (int(v) for v in stats[i])
        if pred(x, y, w, h, area):
            keep[labels == i] = 255
    return keep


def build_masks(plate: np.ndarray) -> dict[str, np.ndarray]:
    hsv = cv2.cvtColor(plate, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    height, width = h.shape
    yy = np.arange(height)[:, None]

    # Overcast skies are bright and dull. Late-afternoon skies in this set are a saturated blue (S often 130–180).
    overcast = (s < 70) & (v > 145)
    blue_sky = (h >= 90) & (h <= 125) & (s >= 15) & (s < 210) & (v > 145)
    sky_cand = (overcast | blue_sky).astype(np.uint8)
    sky_cand[(h >= 32) & (h <= 88) & (s > 48)] = 0
    sky_cand[((h < 12) | (h > 168)) & (s > 55)] = 0
    sky = _components(sky_cand, lambda x, y, w, hh, area: y <= 8 and area > 400)
    sky = cv2.erode(sky, np.ones((3, 3), np.uint8), iterations=1)

    # Blue-green water only. Dull stone and shadow read as low-saturation "dark water"
    # and were pulling facades into the mask.
    blue_water = (h >= 88) & (h <= 128) & (s >= 40) & (s <= 180) & (v >= 35) & (v <= 185)
    water_cand = (blue_water & (sky == 0) & (yy > int(height * 0.28))).astype(np.uint8)
    water_cand[(h >= 35) & (h <= 88) & (s > 42)] = 0
    water = _components(
        water_cand,
        lambda x, y, w, hh, area: (
            area > 2200
            and w > 48
            and w > hh * 0.45
            and (y + hh / 2) > height * 0.40
        ),
    )
    water = cv2.erode(water, np.ones((3, 3), np.uint8), iterations=1)
    # Erosion can leave a tall spike on a pylon. Drop anything that is no longer a horizontal body of water.
    water = _components(
        water,
        lambda x, y, w, hh, area: area > 800 and w > 24 and hh < w * 2.0 and (y + hh / 2) > height * 0.45,
    )

    fol_cand = ((h >= 18) & (h <= 100) & (s >= 28) & (v >= 20) & (sky == 0) & (water == 0)).astype(np.uint8)
    foliage = _components(fol_cand, lambda x, y, w, hh, area: area > 120)
    foliage = cv2.erode(foliage, np.ones((3, 3), np.uint8), iterations=1)

    red = (((h <= 8) | (h >= 170)) & (s >= 150) & (v >= 100)).astype(np.uint8)
    blue = ((h >= 105) & (h <= 130) & (s >= 160) & (v >= 80) & (sky == 0)).astype(np.uint8)
    flag_cand = cv2.bitwise_or(red, blue)
    flag_cand[water > 0] = 0
    flags = _components(flag_cand, lambda x, y, w, hh, area: 40 <= area <= 4200 and hh < 180 and w < 160)
    flags = cv2.erode(flags, np.ones((2, 2), np.uint8), iterations=1)

    # Life masks must not overlap. Sky wins over nothing else; water/foliage/flags are exclusive.
    foliage[water > 0] = 0
    flags[foliage > 0] = 0
    flags[water > 0] = 0
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
    # Every displacement is a sine that is 0 at frame 0 and frame FRAMES, so the loop closes.
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
        # Drift is strongest deep in the sky and falls to zero at the skyline.
        dx = (22.0 * s1 * factors["sky"]).astype(np.float32)
        dy = (2.0 * s1 * factors["sky"]).astype(np.float32)
        _apply(out, plate, masks["sky"], dx, dy)
        # A flat blue sky barely changes under a small shift. A slow brightness
        # wave, zero at the skyline, keeps cloud life visible without touching stone.
        breath = (10.0 * s1 * np.sin(xs * 0.03 + ys * 0.012) * factors["sky"]).astype(np.float32)
        region = masks["sky"] > 0
        lifted = out.astype(np.float32)
        lifted[region] += breath[region, None]
        out[region] = np.clip(lifted[region], 0, 255).astype(np.uint8)

    life = (masks["sky"] | masks["water"] | masks["foliage"] | masks["flags"]) > 0
    if not np.array_equal(out[~life], plate[~life]):
        raise SystemExit("architecture pixel moved; refusing to encode")
    return out


def encode(plate: np.ndarray, masks: dict[str, np.ndarray], dest: Path) -> None:
    factors = {
        "sky": _factor(masks["sky"], 32.0),
        "water": _factor(masks["water"], 14.0),
        "foliage": _factor(masks["foliage"], 16.0),
        "flags": _factor(masks["flags"], 6.0),
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s",
        f"{PHOTO_W}x{PHOTO_H}",
        "-r",
        str(FPS),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "18",
        "-preset",
        "medium",
        "-movflags",
        "+faststart",
        str(dest),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for n in range(FRAMES):
            frame = render_frame(plate, masks, factors, n)
            proc.stdin.write(frame.tobytes())
    finally:
        proc.stdin.close()
    err = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
    code = proc.wait()
    if code != 0:
        raise SystemExit(f"ffmpeg failed for {dest}\n{err[-2000:]}")


def write_poster(plate: np.ndarray, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    ok = cv2.imwrite(str(dest), plate, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not ok:
        raise SystemExit(f"poster write failed {dest}")


def coverage(masks: dict[str, np.ndarray]) -> dict[str, float]:
    total = float(PHOTO_H * PHOTO_W)
    return {name: round(float(np.count_nonzero(mask)) / total, 4) for name, mask in masks.items()}


def debug_scene(scene: dict, debug_dir: Path) -> dict:
    plate = crop_plate(ROOT / scene["anchor"])
    masks = build_masks(plate)
    overlay = plate.copy()
    colors = {"sky": (255, 180, 40), "water": (255, 80, 20), "foliage": (40, 180, 40), "flags": (40, 40, 220)}
    for name, color in colors.items():
        sel = masks[name] > 0
        overlay[sel] = (0.55 * overlay[sel] + 0.45 * np.array(color)).astype(np.uint8)
    debug_dir.mkdir(parents=True, exist_ok=True)
    slug = scene["entry_id"]
    cv2.imwrite(str(debug_dir / f"{slug}-mask.jpg"), overlay, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    mid = render_frame(plate, masks, {k: _factor(v, {"sky": 32, "water": 14, "foliage": 16, "flags": 6}[k]) for k, v in masks.items()}, FRAMES // 2)
    cv2.imwrite(str(debug_dir / f"{slug}-mid.jpg"), mid, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    diff = cv2.absdiff(mid, plate)
    heat = cv2.applyColorMap(cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY), cv2.COLORMAP_INFERNO)
    cv2.imwrite(str(debug_dir / f"{slug}-diff.jpg"), heat, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    return {"entry_id": slug, "coverage": coverage(masks), "mid_mad": round(float(diff.mean()), 3)}


# Sideways sweep. Used only by --sweep. The locked-camera path above is unchanged.
PLATE_W = 1920
# Share of the 1920-wide plate the window travels. Kept inside 15–20%.
SWEEP_TRAVEL_FRAC = 0.18
# These daylight plates compose the landmark on the center of the frame.
SUBJECT_X = PLATE_W / 2.0

SWEEP_SCENES = (
    {"entry_id": "NL-01-017", "folder": "Amsterdam"},
    {"entry_id": "NL-01-018", "folder": "Amsterdam"},
    {"entry_id": "NL-01-019", "folder": "Amsterdam"},
    {"entry_id": "NL-01-020", "folder": "Amsterdam"},
    {"entry_id": "NL-01-021", "folder": "Amsterdam"},
    {"entry_id": "NL-01-022", "folder": "Volendam"},
    {"entry_id": "NL-01-023", "folder": "Marken"},
    {"entry_id": "NL-01-024", "folder": "Alkmaar"},
    {"entry_id": "NL-01-025", "folder": "Hoorn"},
    {"entry_id": "NL-01-026", "folder": "Enkhuizen"},
    {"entry_id": "NL-01-027", "folder": "Rotterdam"},
    {"entry_id": "NL-01-028", "folder": "Rotterdam"},
)


def sweep_paths(scene: dict) -> tuple[Path, Path]:
    slug = scene["entry_id"].lower()
    folder = scene["folder"]
    base = ROOT / "library" / "world" / "Netherlands" / folder
    anchor = base / f"{slug}-daylight-16x9.png"
    dest = base / f"{slug}-motion-10s-4x5.mp4"
    return anchor, dest


def load_sweep_plate(path: Path) -> np.ndarray:
    """Daylight 16:9 master with the label bar removed, as a 1920×1080 plate.

    The photo rows are already 1920×1080. They are not resampled. A plate that
    is not already that size is scaled to it. No new picture is generated.
    """
    im = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if im is None:
        raise SystemExit(f"missing daylight master {path}")
    if im.shape[0] < PHOTO_H:
        raise SystemExit(f"{path} is {im.shape[1]}x{im.shape[0]}")
    plate = im[:PHOTO_H]
    if plate.shape[1] != PLATE_W or plate.shape[0] != PHOTO_H:
        plate = cv2.resize(plate, (PLATE_W, PHOTO_H), interpolation=cv2.INTER_LANCZOS4)
    if plate.shape != (PHOTO_H, PLATE_W, 3):
        raise SystemExit(f"sweep plate {path} is {plate.shape}")
    return plate


def sweep_x(n: int) -> float:
    """Origin of the 864-wide window. Left to right, ease in and out, no vertical."""
    travel = PLATE_W * SWEEP_TRAVEL_FRAC
    # Mid-glide puts the subject on the center of the 864 frame.
    mid = SUBJECT_X - (PHOTO_W / 2.0)
    u = n / (FRAMES - 1)
    ease = 0.5 - 0.5 * math.cos(math.pi * u)
    return (mid - travel / 2.0) + travel * ease


def assert_sweep_path() -> None:
    xs = [sweep_x(n) for n in range(FRAMES)]
    travel = xs[-1] - xs[0]
    frac = travel / PLATE_W
    if not (0.15 - 1e-9 <= frac <= 0.20 + 1e-9):
        raise SystemExit(f"sweep travel {frac:.3f} of plate width is outside 15–20%")
    if xs[0] >= xs[-1]:
        raise SystemExit("sweep does not move left to right")
    for i in range(1, FRAMES):
        if xs[i] + 1e-6 < xs[i - 1]:
            raise SystemExit("sweep reversed direction")
    half = PHOTO_W / 2.0
    for x in xs:
        if x < -1e-3 or x + PHOTO_W > PLATE_W + 1e-3:
            raise SystemExit(f"window {x:.2f} leaves the plate")
        subject_in_frame = SUBJECT_X - x
        if not (0.0 <= subject_in_frame <= PHOTO_W):
            raise SystemExit("subject left the frame")
        # Middle half of the frame. The glide is symmetric about the subject,
        # so the window never runs past it to the edge of the plate.
        if not (PHOTO_W * 0.25 <= subject_in_frame <= PHOTO_W * 0.75):
            raise SystemExit(f"subject left the middle half at window {x:.2f}")
        if abs((x + half) - SUBJECT_X) - (travel / 2.0) > 0.05:
            raise SystemExit("window traveled past the subject")


def render_sweep_frame(plate: np.ndarray, n: int) -> np.ndarray:
    x = np.float32(sweep_x(n))
    map_x = np.broadcast_to(np.arange(PHOTO_W, dtype=np.float32) + x, (PHOTO_H, PHOTO_W)).copy()
    map_y = np.broadcast_to(np.arange(PHOTO_H, dtype=np.float32)[:, None], (PHOTO_H, PHOTO_W)).copy()
    # One source pixel per output pixel, and the row index never changes.
    if abs(float(map_x[0, 1] - map_x[0, 0]) - 1.0) > 1e-5:
        raise SystemExit("sweep changed scale")
    if float(map_y[0, 0]) != 0.0 or float(map_y[-1, 0]) != float(PHOTO_H - 1):
        raise SystemExit("sweep moved vertically")
    frame = cv2.remap(
        plate,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0),
    )
    if frame.shape != (PHOTO_H, PHOTO_W, 3):
        raise SystemExit(f"sweep frame is {frame.shape}")
    return frame


def encode_sweep(plate: np.ndarray, dest: Path) -> float:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s",
        f"{PHOTO_W}x{PHOTO_H}",
        "-r",
        str(FPS),
        "-i",
        "-",
        "-frames:v",
        str(FRAMES),
        "-an",
        "-c:v",
        "libx264",
        "-profile:v",
        "high",
        "-level:v",
        "3.2",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "18",
        "-preset",
        "medium",
        "-movflags",
        "+faststart",
        str(dest),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    first = last = None
    try:
        for n in range(FRAMES):
            frame = render_sweep_frame(plate, n)
            if n == 0:
                first = frame
            elif n == FRAMES - 1:
                last = frame
            proc.stdin.write(frame.tobytes())
    finally:
        proc.stdin.close()
    err = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
    code = proc.wait()
    if code != 0:
        raise SystemExit(f"ffmpeg failed for {dest}\n{err[-2000:]}")
    if first is None or last is None:
        raise SystemExit(f"sweep did not render {dest}")
    mae = float(np.mean(np.abs(first.astype(np.int16) - last.astype(np.int16))))
    if mae < 8.0:
        raise SystemExit(f"{dest} sweep MAE {mae:.2f} is a locked hold")
    return mae


def probe_sweep(path: Path) -> dict:
    raw = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,nb_frames,codec_name,pix_fmt,avg_frame_rate",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ]
    )
    return json.loads(raw)


def run_sweep(only: list[str]) -> None:
    assert_sweep_path()
    scenes = [s for s in SWEEP_SCENES if not only or s["entry_id"] in only]
    if only and len(scenes) != len(only):
        raise SystemExit("refusing ids outside the sideways-sweep pack")
    for scene in scenes:
        anchor, dest = sweep_paths(scene)
        plate = load_sweep_plate(anchor)
        mae = encode_sweep(plate, dest)
        info = probe_sweep(dest)
        stream = info["streams"][0]
        duration = float(info["format"]["duration"])
        if int(stream["width"]) != PHOTO_W or int(stream["height"]) != PHOTO_H:
            raise SystemExit(f"{dest} is {stream['width']}x{stream['height']}")
        if abs(duration - 10.0) > 0.05:
            raise SystemExit(f"{dest} duration {duration}")
        if stream["codec_name"] != "h264" or stream["pix_fmt"] != "yuv420p":
            raise SystemExit(f"{dest} codec {stream['codec_name']} {stream['pix_fmt']}")
        if stream.get("avg_frame_rate") != f"{FPS}/1":
            raise SystemExit(f"{dest} frame rate {stream.get('avg_frame_rate')}")
        print(
            json.dumps(
                {
                    "entry_id": scene["entry_id"],
                    "method": "sideways-sweep",
                    "anchor": str(anchor.relative_to(ROOT)),
                    "out": str(dest.relative_to(ROOT)),
                    "travel_frac": SWEEP_TRAVEL_FRAC,
                    "ends_mae": round(mae, 3),
                    "width": int(stream["width"]),
                    "height": int(stream["height"]),
                    "duration_s": duration,
                    "codec": stream["codec_name"],
                    "pix_fmt": stream["pix_fmt"],
                    "fps": stream["avg_frame_rate"],
                }
            )
        )


def main() -> None:
    import sys

    if "--sweep" in sys.argv:
        only = [a for a in sys.argv[1:] if a.startswith("NL-")]
        run_sweep(only)
        return

    debug = "--debug" in sys.argv
    only = [a for a in sys.argv[1:] if a.startswith("NL-")]
    rows = []
    for scene in SCENES:
        if only and scene["entry_id"] not in only:
            continue
        if debug:
            row = debug_scene(scene, Path("/tmp/ambient"))
            print(json.dumps(row))
            rows.append(row)
            continue
        plate = crop_plate(ROOT / scene["anchor"])
        masks = build_masks(plate)
        cov = coverage(masks)
        life = sum(cov.values())
        if life < 0.04:
            raise SystemExit(f"{scene['entry_id']} life coverage {life} is too thin for static ambient")
        encode(plate, masks, ROOT / scene["out"])
        write_poster(plate, ROOT / scene["poster"])
        print(json.dumps({"entry_id": scene["entry_id"], "coverage": cov, "out": scene["out"]}))
    if debug:
        (Path("/tmp/ambient") / "coverage.json").write_text(json.dumps(rows, indent=2) + "\n")


if __name__ == "__main__":
    main()
