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
    {"entry_id": "NL-01-029", "folder": "The Hague"},
    {"entry_id": "NL-01-030", "folder": "The Hague"},
    {"entry_id": "NL-01-031", "folder": "Gouda"},
    {"entry_id": "NL-01-032", "folder": "Dordrecht"},
    {"entry_id": "NL-01-033", "folder": "Utrecht"},
    {"entry_id": "NL-01-034", "folder": "Utrecht"},
    {"entry_id": "NL-01-036", "folder": "Wijk bij Duurstede"},
    {"entry_id": "NL-01-039", "folder": "Breda"},
    {"entry_id": "NL-01-042", "folder": "Zierikzee"},
    {"entry_id": "NL-01-043", "folder": "Neeltje Jans"},
    {"entry_id": "NL-01-044", "folder": "Domburg"},
    {"entry_id": "NL-01-045", "folder": "Deventer"},
    {"entry_id": "NL-01-046", "folder": "Arnhem"},
    {"entry_id": "NL-01-049", "folder": "Maastricht"},
    {"entry_id": "NL-01-050", "folder": "Valkenburg"},
    {"entry_id": "NL-01-051", "folder": "Thorn"},
    {"entry_id": "NL-01-052", "folder": "Vaals"},
    {"entry_id": "NL-01-053", "folder": "Lelystad"},
    {"entry_id": "NL-01-054", "folder": "Urk"},
    {"entry_id": "NL-01-055", "folder": "Schokland"},
    {"entry_id": "NL-01-058", "folder": "Franeker"},
    {"entry_id": "NL-01-059", "folder": "Hindeloopen"},
    {"entry_id": "NL-01-061", "folder": "Bourtange"},
    {"entry_id": "NL-01-062", "folder": "Borger"},
    {"entry_id": "NL-01-063", "folder": "Dwingeloo"},
    {"entry_id": "NL-01-065", "folder": "Oranjestad"},
    {"entry_id": "NL-01-066", "folder": "The Bottom"},
    {"entry_id": "NL-01-068", "folder": "Heusden"},
    {"entry_id": "NL-01-069", "folder": "Nuenen"},
    {"entry_id": "NL-01-070", "folder": "Zwolle"},
    {"entry_id": "NL-01-071", "folder": "Kampen"},
    {"entry_id": "NL-01-072", "folder": "Elburg"},
    {"entry_id": "NL-01-073", "folder": "Zutphen"},
    {"entry_id": "NL-01-074", "folder": "Arnhem"},
    {"entry_id": "NL-01-075", "folder": "Nijmegen"},
    {"entry_id": "NL-01-076", "folder": "Naarden"},
    {"entry_id": "NL-01-078", "folder": "Haarzuilens"},
    {"entry_id": "NL-01-079", "folder": "The Hague"},
    {"entry_id": "NL-01-080", "folder": "Delft"},
    {"entry_id": "NL-01-081", "folder": "Holwerd"},
    {"entry_id": "NL-01-082", "folder": "Zoutkamp"},
    {"entry_id": "NL-01-083", "folder": "Assen"},
    {"entry_id": "NL-01-084", "folder": "Amerongen"},
    {"entry_id": "NL-01-085", "folder": "Poederoijen"},
    {"entry_id": "NL-01-086", "folder": "Gorinchem"},
    {"entry_id": "NL-01-087", "folder": "Brielle"},
    {"entry_id": "NL-01-088", "folder": "Hoek van Holland"},
    # The lighthouse stands right of plate center. Same glide, aimed at the
    # tower measured on this daylight plate (x 1012–1402), so the shaft stays
    # inside the 864 frame. The default center anchor is unchanged.
    {
        "entry_id": "NL-01-089",
        "folder": "Katwijk",
        "subject_x": 1207.0,
        "subject_span": (1012.0, 1402.0),
    },
    # The lighthouse stands left of plate center. Same glide, aimed as close
    # to the tower as the plate allows (measured x 464–710). The tower center
    # would put the window off the plate. The shaft stays inside the 864 frame.
    # The default center anchor is unchanged.
    {
        "entry_id": "NL-01-090",
        "folder": "Noordwijk",
        "subject_x": 605.0,
        "subject_span": (464.0, 710.0),
    },
    # The Speeltoren stands left of plate center. Same glide, aimed at the
    # tower measured on this daylight plate (x 613–860), so the shaft stays
    # inside the 864 frame. The default center anchor is unchanged.
    {
        "entry_id": "NL-01-091",
        "folder": "Edam",
        "subject_x": 736.5,
        "subject_span": (613.0, 860.0),
    },
    {"entry_id": "NL-01-092", "folder": "Monnickendam"},
    {"entry_id": "NL-01-093", "folder": "Spakenburg"},
    # The Vischpoort stands left of plate center. Same glide, aimed at the
    # gate measured on this daylight plate (x 521–707), so the arch stays
    # inside the 864 frame. The default center anchor is unchanged.
    {
        "entry_id": "NL-01-094",
        "folder": "Harderwijk",
        "subject_x": 614.0,
        "subject_span": (521.0, 707.0),
    },
    {"entry_id": "NL-01-095", "folder": "Doesburg"},
    {"entry_id": "NL-01-096", "folder": "Roermond"},
    {"entry_id": "NL-01-097", "folder": "Bergen op Zoom"},
    {"entry_id": "NL-01-098", "folder": "s-Hertogenbosch"},
    {"entry_id": "NL-01-099", "folder": "Tilburg"},
    {"entry_id": "NL-01-100", "folder": "Helmond"},
    # The onion dome and the square tower stand too far right for the 18%
    # glide to hold them without running off the plate. This clip eases a
    # shorter distance and finishes against the plate's right edge, so the
    # dome and tower (x 1476–1764) stay inside the 864 frame. The left nave
    # is what leaves. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-101",
        "folder": "Venlo",
        "subject_x": 1620.0,
        "subject_span": (1476.0, 1764.0),
        "window_start": 912.0,
        "window_end": 1056.0,
    },
    {"entry_id": "NL-01-102", "folder": "Sittard"},
    # The Pancratiuskerk tower stands left of plate center. The 18% glide
    # cannot hold the shaft (x 301–526) without running off the plate. This
    # clip eases a shorter distance and starts against the plate's left edge,
    # so the tower stays inside the 864 frame. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-103",
        "folder": "Heerlen",
        "subject_x": 413.5,
        "subject_span": (301.0, 526.0),
        "window_start": 0.0,
        "window_end": 289.0,
    },
    {"entry_id": "NL-01-104", "folder": "Kerkrade"},
    # The Gevangentoren stands left of plate center. The 18% glide cannot
    # hold the round tower (x 267–528) without running off the plate. This
    # clip eases a shorter distance and starts against the plate's left edge,
    # so the tower stays inside the 864 frame. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-105",
        "folder": "Vlissingen",
        "subject_x": 397.5,
        "subject_span": (267.0, 528.0),
        "window_start": 0.0,
        "window_end": 255.0,
    },
    # The lighthouse stands right of plate center. Same glide, aimed at the
    # tower measured on this daylight plate (x 1048–1210), so the shaft stays
    # inside the 864 frame. The default center anchor is unchanged.
    {
        "entry_id": "NL-01-106",
        "folder": "Westkapelle",
        "subject_x": 1129.0,
        "subject_span": (1048.0, 1210.0),
    },
    {"entry_id": "NL-01-107", "folder": "Yerseke"},
    {"entry_id": "NL-01-108", "folder": "Goes"},
    # The tied arch, springing to springing, is x 788–1660 on this daylight
    # plate. That is wider than the 864 frame, so an 18% glide travels past
    # it and cuts one foot off as the other comes in. This clip eases only
    # across the slack that remains after the largest portion that fits
    # (x 808–1641, crown included) is held inside every frame with a 12px
    # pad. The window stays on the plate. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-109",
        "folder": "Culemborg",
        "subject_x": 1224.5,
        "subject_span": (808.0, 1641.0),
        "window_start": 789.0,
        "window_end": 796.0,
    },
    # The Waterpoort stands right of plate center. Same glide, aimed at the
    # gate measured on this daylight plate (x 1119–1345), so the gate stays
    # inside the 864 frame. The default center anchor is unchanged.
    {
        "entry_id": "NL-01-110",
        "folder": "Tiel",
        "subject_x": 1232.0,
        "subject_span": (1119.0, 1345.0),
    },
    {"entry_id": "NL-01-111", "folder": "Wageningen"},
    # The tower and dome stand right of plate center. Same glide, aimed at
    # that mass measured on this daylight plate (x 852–1249), so the tower
    # and dome stay inside the 864 frame. The default center anchor is unchanged.
    {
        "entry_id": "NL-01-112",
        "folder": "Radio Kootwijk",
        "subject_x": 1050.5,
        "subject_span": (852.0, 1249.0),
    },
    {"entry_id": "NL-01-113", "folder": "Nes"},
    {"entry_id": "NL-01-114", "folder": "West-Terschelling"},
    {"entry_id": "NL-01-115", "folder": "Oost-Vlieland"},
    # The Noordertoren stands right of plate center. Same glide, aimed at the
    # tower measured on this daylight plate (x 1156–1330), so the shaft stays
    # inside the 864 frame. The default center anchor is unchanged.
    {
        "entry_id": "NL-01-116",
        "folder": "Schiermonnikoog",
        "subject_x": 1243.0,
        "subject_span": (1156.0, 1330.0),
    },
    {"entry_id": "NL-01-117", "folder": "Den Oever"},
    # The Dudok tower and its canopy stand right of plate center. Same glide,
    # aimed at the tower measured on this daylight plate (canopy x 1233–1438),
    # so the monument stays inside the 864 frame. The default center anchor
    # is unchanged.
    {
        "entry_id": "NL-01-118",
        "folder": "Afsluitdijk",
        "subject_x": 1299.0,
        "subject_span": (1233.0, 1438.0),
    },
    {"entry_id": "NL-01-129", "folder": "Haarlem"},
    {"entry_id": "NL-01-130", "folder": "Amsterdam"},
    # The Overhoeks tower stands right of plate center. Same glide, aimed at
    # the shaft measured on this daylight plate (x 1095–1381), so the tower
    # stays inside the 864 frame. The default center anchor is unchanged.
    {
        "entry_id": "NL-01-131",
        "folder": "Amsterdam",
        "subject_x": 1238.0,
        "subject_span": (1095.0, 1381.0),
    },
    {"entry_id": "NL-01-132", "folder": "Amsterdam"},
    {"entry_id": "NL-01-133", "folder": "Rotterdam"},
    # The three glass slabs, taken together, are wider than an 18% glide can
    # hold. This clip eases only across the slack that keeps those slabs
    # (x 620–1186) inside every frame with a 12px pad. The window stays on
    # the plate. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-134",
        "folder": "Rotterdam",
        "subject_x": 903.0,
        "subject_span": (620.0, 1186.0),
        "window_start": 338.0,
        "window_end": 604.0,
    },
    {"entry_id": "NL-01-135", "folder": "The Hague"},
    # Paleis Noordeinde's facade is wider than the 864 frame. This clip
    # eases only across the slack that remains after the largest central
    # portion (the pediment and the equestrian statue, x 564–1356) is held
    # inside every frame with a 12px pad. The outer wings stay out, so one
    # end does not leave as the other comes in. The window stays on the
    # plate. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-136",
        "folder": "The Hague",
        "subject_x": 960.0,
        "subject_span": (564.0, 1356.0),
        "window_start": 504.0,
        "window_end": 552.0,
    },
    # The Burcht shell keep stands left of plate center. Same glide, aimed
    # at the keep measured on this daylight plate (x 655–1035), so the
    # brick ring stays inside the 864 frame. The default center anchor is
    # unchanged.
    {
        "entry_id": "NL-01-137",
        "folder": "Leiden",
        "subject_x": 843.5,
        "subject_span": (655.0, 1035.0),
    },
    # Oostpoort's two towers, taken together, are wider than an 18% glide
    # can hold. This clip eases only across the slack that keeps both
    # towers (x 694–1504) inside every frame with a 12px pad. The window
    # stays on the plate. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-138",
        "folder": "Delft",
        "subject_x": 1099.0,
        "subject_span": (694.0, 1504.0),
        "window_start": 652.0,
        "window_end": 682.0,
    },
    # Huis Van Gijn's straight cornice, taken as the house, is wider than
    # an 18% glide can hold. This clip eases only across the slack that
    # keeps the house (x 600–1340) inside every frame with a 12px pad. The
    # window stays on the plate. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-139",
        "folder": "Dordrecht",
        "subject_x": 970.0,
        "subject_span": (600.0, 1340.0),
        "window_start": 488.0,
        "window_end": 588.0,
    },
    # The unfinished west wall of the Domkerk stands right of plate center.
    # Same glide, aimed at the wall measured on this daylight plate
    # (x 1100–1500), so the Gothic front stays inside the 864 frame. The
    # default center anchor is unchanged.
    {
        "entry_id": "NL-01-140",
        "folder": "Utrecht",
        "subject_x": 1299.0,
        "subject_span": (1100.0, 1500.0),
    },
    {"entry_id": "NL-01-141", "folder": "Breda"},
    # The Lichttoren stands right of plate center. Same glide, aimed at the
    # shaft measured on this daylight plate (x 840–1260), so the tower stays
    # inside the 864 frame. The default center anchor is unchanged.
    {
        "entry_id": "NL-01-142",
        "folder": "Eindhoven",
        "subject_x": 1050.5,
        "subject_span": (840.0, 1260.0),
    },
    # Helpoort's left round tower (x 210–340) and the right cone (tip at
    # x 1036, eave near x 1112) are wider than 864. This clip eases only
    # across the slack that keeps that tower and the cone tip inside every
    # frame with a 12px pad. The right slope past the tip is the part that
    # does not fit. The window stays on the plate. The default center
    # sweep is unchanged.
    {
        "entry_id": "NL-01-143",
        "folder": "Maastricht",
        "subject_x": 625.0,
        "subject_span": (210.0, 1040.0),
        "window_start": 190.0,
        "window_end": 198.0,
    },
    # Forum's stacked blocks, taken together, are wider than an 18% glide
    # can hold. This clip eases only across the slack that keeps the
    # building (x 900–1620) inside every frame with a 12px pad. The window
    # stays on the plate. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-144",
        "folder": "Groningen",
        "subject_x": 1260.0,
        "subject_span": (900.0, 1620.0),
        "window_start": 768.0,
        "window_end": 888.0,
    },
    # The Quill's cone is wider than the 864 frame. This clip eases only
    # across the slack that remains after the largest portion that fits
    # (the peak and the upper slopes, x 590–1410) is held inside every
    # frame with a 12px pad. One slope does not leave as the other comes
    # in. The window stays on the plate. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-145",
        "folder": "Oranjestad",
        "subject_x": 1000.0,
        "subject_span": (590.0, 1410.0),
        "window_start": 558.0,
        "window_end": 578.0,
    },
    {"entry_id": "NL-01-146", "folder": "Bonaire"},
    {"entry_id": "NL-01-147", "folder": "Windwardside"},
    # The Poldertoren stands on the plate center (shaft x 870–1049). The
    # default 18% glide holds it. The center anchor is unchanged.
    {"entry_id": "NL-01-148", "folder": "Emmeloord"},
    # The brick wing and the round tower, taken together, run x 432–1476,
    # wider than 864. This clip eases only across the slack that keeps the
    # round tower and the wing that still fits (x 652–1476) inside every
    # frame with a 12px pad. The far left of the wing stays out. The
    # default center sweep is unchanged.
    {
        "entry_id": "NL-01-149",
        "folder": "Coevorden",
        "subject_x": 1064.0,
        "subject_span": (652.0, 1476.0),
        "window_start": 624.0,
        "window_end": 640.0,
    },
    # The radio dish (rim to rim, x 540–1356) is wider than an 18% glide
    # can hold. This clip eases only across the slack that keeps the whole
    # dish inside every frame with a 12px pad. The window stays on the
    # plate. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-150",
        "folder": "Dwingeloo",
        "subject_x": 948.0,
        "subject_span": (540.0, 1356.0),
        "window_start": 504.0,
        "window_end": 528.0,
    },
    # NL-01-151 is not swept. The three hanging kitchens span about
    # x 483–1801, wider than 864, so a 4:5 frame cannot keep every kitchen.
    #
    # The low Bentheimer hall is wider than 864. This clip eases only
    # across the slack that keeps the ridge turret and the hall that still
    # fits (x 546–1366) inside every frame with a 12px pad. The right end
    # of the hall stays out. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-152",
        "folder": "Ootmarsum",
        "subject_x": 956.0,
        "subject_span": (546.0, 1366.0),
        "window_start": 514.0,
        "window_end": 534.0,
    },
    # The near stage mill stands left of plate center. An 18% glide
    # cannot hold its sails (tips about x 272 and x 740, top sail on the
    # plate's top row) without running off the plate. This clip eases a
    # shorter distance from the left edge and stops while every sail is
    # still inside the 864 frame, so the glide does not walk past the
    # mill. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-153",
        "folder": "Schiedam",
        "subject_x": 509.0,
        "subject_span": (248.0, 770.0),
        "window_start": 0.0,
        "window_end": 140.0,
    },
    # The parked barrier arm's lattice runs wider than 864. This clip
    # eases only across the slack that keeps the main truss (x 240–1060)
    # inside every frame with a 12px pad. The window stays on the plate.
    # The default center sweep is unchanged.
    {
        "entry_id": "NL-01-154",
        "folder": "Hoek van Holland",
        "subject_x": 650.0,
        "subject_span": (240.0, 1060.0),
        "window_start": 208.0,
        "window_end": 228.0,
    },
    # The white balance bridge is wider than 864. This clip eases only
    # across the slack that keeps the central arch (x 560–1380) inside
    # every frame with a 12px pad. The approaches stay out, so one end
    # does not leave as the other comes in. The default center sweep is
    # unchanged.
    {
        "entry_id": "NL-01-155",
        "folder": "Amsterdam",
        "subject_x": 970.0,
        "subject_span": (560.0, 1380.0),
        "window_start": 528.0,
        "window_end": 548.0,
    },
    # De Adriaan stands right of plate center. Same glide, aimed at the
    # mill measured on this daylight plate (sails x 992–1358), so the cap
    # and sails stay inside the 864 frame. The default center anchor is
    # unchanged.
    {
        "entry_id": "NL-01-156",
        "folder": "Haarlem",
        "subject_x": 1175.0,
        "subject_span": (992.0, 1358.0),
    },
    # The Eusebius tower stands right of plate center. Same glide, aimed
    # at the crown measured on this daylight plate (x 840–1300), so the
    # shaft and the 1964 crown stay inside the 864 frame. The default
    # center anchor is unchanged.
    {
        "entry_id": "NL-01-157",
        "folder": "Arnhem",
        "subject_x": 1070.0,
        "subject_span": (840.0, 1300.0),
    },
    # The crossing tower and its 1957 crown stand on the plate center
    # (x 828–1102). The default 18% glide holds them. The center anchor
    # is unchanged.
    {"entry_id": "NL-01-158", "folder": "Hulst"},
    # NL-01-159 is not swept. Seven limestone arches run about x 559–1662,
    # wider than 864, so a 4:5 frame cannot keep every arch.
    #
    # The Oudenbosch colonnade and dome run about x 833–1755, wider than
    # 864. This clip eases only across the slack that keeps the dome and
    # the facade that still fits (x 932–1748) inside every frame with a
    # 12px pad. The far left of the colonnade stays out. The default
    # center sweep is unchanged.
    {
        "entry_id": "NL-01-160",
        "folder": "Oudenbosch",
        "subject_x": 1340.0,
        "subject_span": (932.0, 1748.0),
        "window_start": 896.0,
        "window_end": 920.0,
    },
    # The two Waterpoort towers, taken together, are wider than an 18%
    # glide can hold. This clip eases only across the slack that keeps
    # both spires (x 620–1296) inside every frame with a 12px pad. The
    # window stays on the plate. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-161",
        "folder": "Sneek",
        "subject_x": 958.0,
        "subject_span": (620.0, 1296.0),
        "window_start": 444.0,
        "window_end": 608.0,
    },
    # The Woudagemaal halls run about x 333–1600, wider than 864. This
    # clip eases only across the slack that keeps the chimney and the
    # hall through its right wall (x 820–1620) inside every frame with a
    # 12px pad. The left gables stay out. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-162",
        "folder": "Lemmer",
        "subject_x": 1220.0,
        "subject_span": (820.0, 1620.0),
        "window_start": 800.0,
        "window_end": 808.0,
    },
    # Menkemaborg's hipped roof is wider than an 18% glide can hold. This
    # clip eases only across the slack that keeps the house (x 755–1395)
    # inside every frame with a 12px pad. The window stays on the plate.
    # The default center sweep is unchanged.
    {
        "entry_id": "NL-01-163",
        "folder": "Uithuizen",
        "subject_x": 1075.0,
        "subject_span": (755.0, 1395.0),
        "window_start": 543.0,
        "window_end": 743.0,
    },
    # The silver cylinder (x 391–668) and the gold block (x 759–1061)
    # stay inside every frame. The blue pavilion begins near x 1104 and
    # runs past what an 864 frame can hold with them, so this clip does
    # not walk onto it. A short glide, window 216–236, keeps both buildings
    # inside with a 12px pad. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-164",
        "folder": "Groningen",
        "subject_x": 726.0,
        "subject_span": (384.0, 1068.0),
        "window_start": 216.0,
        "window_end": 236.0,
    },
    # NL-01-165 is not swept. The thatched hall-farmhouses around the brink
    # run wider than 864, so a 4:5 frame cannot keep every roof.
    #
    # The sandstone tower stands right of plate center. Same glide, aimed
    # at the shaft measured on this daylight plate (x 992–1281), so the
    # 1926 spire stays inside the 864 frame. The default center anchor is
    # unchanged.
    {
        "entry_id": "NL-01-166",
        "folder": "Enschede",
        "subject_x": 1136.5,
        "subject_span": (992.0, 1281.0),
    },
    # The Cuneratoren stands left of plate center. Same glide, aimed at
    # the shaft measured on this daylight plate (x 727–936). The spire
    # already reaches y 4 of the daylight plate, so the frame keeps that
    # top edge. The default center anchor is unchanged.
    {
        "entry_id": "NL-01-167",
        "folder": "Rhenen",
        "subject_x": 831.5,
        "subject_span": (727.0, 936.0),
    },
    # The Breda tower stands right of plate center. Same glide, aimed at
    # the crown measured on this daylight plate (x 1005–1278), so the
    # 1702 slate spire stays inside the 864 frame. The default center
    # anchor is unchanged.
    {
        "entry_id": "NL-01-168",
        "folder": "Breda",
        "subject_x": 1141.5,
        "subject_span": (1005.0, 1278.0),
    },
    # The Laurenskerk tower stands left of plate center. Same glide, aimed
    # at the crown measured on this daylight plate (x 484–776), so the
    # shaft stays inside the 864 frame. The default center anchor is
    # unchanged.
    {
        "entry_id": "NL-01-169",
        "folder": "Rotterdam",
        "subject_x": 630.0,
        "subject_span": (484.0, 776.0),
    },
    # NL-01-170 is not swept. The Delfshaven mill and the Pelgrimvaderskerk
    # turret together run wider than 864, so a 4:5 frame cannot keep the
    # sails and the turret.
    #
    # The octagonal lantern stands too far right for an 18% glide on its
    # own center to stay on the plate. Same glide, aimed as close to the
    # lantern as the plate allows (measured x 1210–1462), so the lantern
    # stays inside the 864 frame. The default center anchor is unchanged.
    {
        "entry_id": "NL-01-171",
        "folder": "Middelburg",
        "subject_x": 1314.0,
        "subject_span": (1210.0, 1462.0),
    },
    # The round keep and the later wings are one mass, x 784–1394, wider
    # than an 18% glide can hold. This clip eases only across the slack
    # that keeps the keep and the wings inside every frame with a 12px
    # pad. The white church across the street stays out. The default
    # center sweep is unchanged.
    {
        "entry_id": "NL-01-172",
        "folder": "Haamstede",
        "subject_x": 1089.0,
        "subject_span": (784.0, 1394.0),
        "window_start": 542.0,
        "window_end": 772.0,
    },
    # The white tower stands left of plate center. An 18% glide on the
    # tower's own center would leave the plate. Same glide, aimed as close
    # to the shaft as the plate allows (watch room and lantern x 458–616),
    # so the tower stays inside the 864 frame. The default center anchor
    # is unchanged.
    {
        "entry_id": "NL-01-173",
        "folder": "Egmond aan Zee",
        "subject_x": 605.0,
        "subject_span": (458.0, 616.0),
    },
    # The two onion-roof gate towers and the round keep, taken together,
    # are wider than an 18% glide can hold. This clip eases only across
    # the slack that keeps both onion roofs and the keep (x 361–1111)
    # inside every frame with a 12px pad. The far right wing stays out.
    # The default center sweep is unchanged.
    {
        "entry_id": "NL-01-174",
        "folder": "Hoensbroek",
        "subject_x": 736.0,
        "subject_span": (361.0, 1111.0),
        "window_start": 259.0,
        "window_end": 349.0,
    },
    # The keep and the cone turrets, including the far-left round turret,
    # run x 890–1642. That is wider than an 18% glide can hold. The previous
    # window ended at 965 and cut that left turret. This clip shortens the
    # glide so the left turret, the keep, and the other cone turrets stay
    # inside every frame with a 12px pad. The right curtain wall past that
    # span stays out. The main tower already touches the top row of the
    # daylight plate, so the frame keeps that edge. The default center
    # sweep is unchanged.
    {
        "entry_id": "NL-01-175",
        "folder": "'s-Heerenberg",
        "subject_x": 1266.0,
        "subject_span": (890.0, 1642.0),
        "window_start": 790.0,
        "window_end": 878.0,
    },
    # The white column and its red stripe stand left of plate center.
    # Same glide, aimed at the tower measured on this daylight plate
    # (x 719–817), so the shaft and the stripe stay inside the 864 frame.
    # The default center anchor is unchanged.
    {
        "entry_id": "NL-01-176",
        "folder": "Bonaire",
        "subject_x": 768.0,
        "subject_span": (719.0, 817.0),
    },
    # The former church's flat roof stands right of plate center. Same
    # glide, aimed at that roof measured on this daylight plate
    # (x 1049–1224), so the church stays inside the 864 frame. The
    # default center anchor is unchanged.
    {
        "entry_id": "NL-01-177",
        "folder": "Nagele",
        "subject_x": 1136.5,
        "subject_span": (1049.0, 1224.0),
    },
    # NL-01-178 is not swept. The Almere city hall's two wings run about
    # x 250–1360, wider than 864, so a 4:5 frame cannot keep both wings.
    #
    # Hunebed D53's capstones sit inside about x 410–1210. That is wider
    # than an 18% glide can hold. This clip eases only across the slack
    # that keeps the chamber inside every frame with a 12px pad. The
    # default center sweep is unchanged.
    {
        "entry_id": "NL-01-179",
        "folder": "Havelte",
        "subject_x": 810.0,
        "subject_span": (410.0, 1210.0),
        "window_start": 358.0,
        "window_end": 398.0,
    },
    # NL-01-180 is not swept. The colony houses form two groups, about
    # x 228–701 and x 1270–1722, so a 4:5 frame cannot keep every roof.
    #
    # The Meppeler Toren stands left of plate center. Same glide, aimed
    # at the shaft and cupola measured on this daylight plate (x 670–935),
    # so the 1827 cupola stays inside the 864 frame. The default center
    # anchor is unchanged.
    {
        "entry_id": "NL-01-181",
        "folder": "Meppel",
        "subject_x": 802.5,
        "subject_span": (670.0, 935.0),
    },
    # NL-01-182 is not swept. The merchant houses around the basin and
    # the lock run wider than 864, so a 4:5 frame cannot keep every gable.
    #
    # NL-01-183 is not swept. The church and the detached squat tower
    # together run wider than 864, so a 4:5 frame cannot keep both roofs.
    #
    # The sandstone west tower stands left of plate center. Same glide,
    # aimed at the shaft measured on this daylight plate (x 540–908), so
    # the spire stays inside the 864 frame. The default center anchor is
    # unchanged.
    {
        "entry_id": "NL-01-184",
        "folder": "Oldenzaal",
        "subject_x": 724.0,
        "subject_span": (540.0, 908.0),
    },
    # NL-01-185 is not swept. The U-shaped manor reaches the left of the
    # plate and the off-centre tower stands near x 1457, so a 4:5 frame
    # cannot keep the manor and that tower.
    #
    # The chapel is one brick nave. Its roof rises from about x 540 to the
    # right edge of the plate, so the whole building is wider than 864.
    # The near gable is that tall end: the roof meets the top of the
    # daylight plate around x 1820 and the wall continues to the plate
    # edge. This clip holds the largest portion that still includes that
    # gable and the nave windows (about x 1061–1899), eased only across
    # the slack that keeps them inside the 864 frame. The far end of the
    # nave, left of this window, does not fit. The default center sweep
    # is unchanged.
    {
        "entry_id": "NL-01-186",
        "folder": "Ter Apel",
        "subject_x": 1480.0,
        "subject_span": (1068.0, 1892.0),
        "window_start": 1040.0,
        "window_end": 1056.0,
    },
    # NL-01-187 is not swept. The water gate and the stage mill's sails
    # together run wider than 864, so a 4:5 frame cannot keep both.
    #
    # The open bell cupola stands just left of plate center. Same glide,
    # aimed at the cupola measured on this daylight plate (x 836–1088), so
    # the cupola stays inside the 864 frame. The long cornice outside that
    # span stays out. The default center anchor is unchanged.
    {
        "entry_id": "NL-01-188",
        "folder": "Dokkum",
        "subject_x": 962.0,
        "subject_span": (836.0, 1088.0),
    },
    # NL-01-189 is not swept. The piers and the cliff behind them fill
    # more of the plate than 864, so a 4:5 frame cannot keep the pier line.
    #
    # NL-01-190 is not swept. The ruined warehouse gables are a row of
    # separate roofs along the bay, so a 4:5 frame cannot keep every gable.
    #
    # NL-01-191 is not swept. The coral-stone huts run from about x 64 to
    # the right edge, so a 4:5 frame cannot keep every roof.
    #
    # NL-01-192 is not swept. The ferry terminal runs about x 900–1850,
    # wider than 864, so a 4:5 frame cannot keep the whole building.
    #
    # The Urk lighthouse stands too far right for an 18% glide on its own
    # center to stay on the plate. Same glide, aimed as close to the tower
    # as the plate allows (measured x 1255–1499), so the shaft and the
    # copper dome stay inside the 864 frame. The default center anchor is
    # unchanged.
    {
        "entry_id": "NL-01-193",
        "folder": "Urk",
        "subject_x": 1314.0,
        "subject_span": (1255.0, 1499.0),
    },
    # The timber barn, including the low left wing, the glass gable, and the
    # lookout, measures about x 73–1196. That is wider than 864, so a 4:5
    # frame cannot keep the left end and the gable together. This clip eases
    # only across the slack that keeps the largest portion still including
    # the glass gable and the lookout (about x 396–1204) inside every frame
    # with a 12px pad. The left end of the wing stays out. The default center
    # sweep is unchanged.
    {
        "entry_id": "NL-01-194",
        "folder": "Lelystad",
        "subject_x": 800.0,
        "subject_span": (396.0, 1204.0),
        "window_start": 352.0,
        "window_end": 384.0,
    },
    # NL-01-195 is not swept. The Wave's bays run about x 336–1580, wider
    # than 864, so a 4:5 frame cannot keep every crest.
    #
    # The keeper's house measures about x 660–1236. That is wider than an
    # 18% glide can hold. This clip eases only across the slack that keeps
    # the house inside every frame with a 12px pad. The default center
    # sweep is unchanged.
    {
        "entry_id": "NL-01-196",
        "folder": "Schokland",
        "subject_x": 948.0,
        "subject_span": (660.0, 1236.0),
        "window_start": 384.0,
        "window_end": 648.0,
    },
    # The Papeloze Kerk chamber and its right capstones measure about
    # x 880–1632. That is wider than an 18% glide can hold, and a longer
    # glide walks into the stones. This clip eases only across the slack
    # that keeps the chamber, including those capstones, inside every frame
    # with a 12px pad. The pines and the mound outside that span stay out.
    # The default center sweep is unchanged.
    {
        "entry_id": "NL-01-197",
        "folder": "Schoonoord",
        "subject_x": 1256.0,
        "subject_span": (880.0, 1632.0),
        "window_start": 792.0,
        "window_end": 824.0,
    },
    # NL-01-198 is not swept. Havezate Mensinge's two wings run about
    # x 400–1600, wider than 864, so a 4:5 frame cannot keep both wings.
    #
    # NL-01-199 is not swept. The sod-hut roofs run about x 0–925, wider
    # than 864, so a 4:5 frame cannot keep every roof.
    #
    # The Peperbus stands too far right for an 18% glide on its own center
    # to stay on the plate. Same glide, aimed as close to the dome as the
    # plate allows (shaft and dome about x 1124–1544), so the copper dome
    # stays inside the 864 frame. The dome already reaches near the top of
    # the daylight plate. The default center anchor is unchanged.
    {
        "entry_id": "NL-01-200",
        "folder": "Zwolle",
        "subject_x": 1314.0,
        "subject_span": (1124.0, 1544.0),
    },
    # NL-01-201 is not swept. The Waag's corner turrets and stair tower run
    # about x 688–1678, wider than 864, so a 4:5 frame cannot keep every turret.
    #
    # The two Koornmarktspoort towers, taken together, measure about
    # x 332–1140. That is wider than an 18% glide can hold. This clip eases
    # only across the slack that keeps both slate spires inside every frame
    # with a 12px pad. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-202",
        "folder": "Kampen",
        "subject_x": 736.0,
        "subject_span": (332.0, 1140.0),
        "window_start": 288.0,
        "window_end": 320.0,
    },
    # The Aa-kerk roof and its baroque spire measure about x 820–1560.
    # That is wider than an 18% glide can hold. An 18% glide aimed at the
    # spire leaves the left roof. This clip eases only across the slack that
    # keeps the nave roof and the spire inside every frame with a 12px pad.
    # The spire already reaches near the top of the daylight plate. The
    # default center sweep is unchanged.
    {
        "entry_id": "NL-01-203",
        "folder": "Groningen",
        "subject_x": 1190.0,
        "subject_span": (820.0, 1560.0),
        "window_start": 708.0,
        "window_end": 808.0,
    },
    # NL-01-204 is not swept. The Jacobuskerk nave (about x 515–1089) and
    # the free-standing saddle-roof tower (about x 1269–1490) together run
    # wider than 864, so a 4:5 frame cannot keep both roofs.
    #
    # The Plompe Toren stands left of plate center. Same glide, aimed at the
    # shaft measured on this daylight plate (x 530–688), so the brick tower
    # stays inside the 864 frame. The default center anchor is unchanged.
    {
        "entry_id": "NL-01-205",
        "folder": "Burgh-Haamstede",
        "subject_x": 609.0,
        "subject_span": (530.0, 688.0),
    },
    # The unfinished Sint-Lievensmonstertoren measures about x 748–1266.
    # That is wider than an 18% glide can hold. This clip eases only across
    # the slack that keeps the tower inside every frame with a 12px pad.
    # The default center sweep is unchanged.
    {
        "entry_id": "NL-01-206",
        "folder": "Zierikzee",
        "subject_x": 1007.0,
        "subject_span": (748.0, 1266.0),
        "window_start": 414.0,
        "window_end": 736.0,
    },
    # NL-01-207 is not swept. Batterij De Windt runs about x 0–961, wider
    # than 864, and meets the left edge of the plate.
    #
    # NL-01-208 is not swept. The red roofs at Hell's Gate step down from
    # the left edge to about x 1240, so a 4:5 frame cannot keep every roof.
    #
    # NL-01-209 is not swept. The curved roof starts at about x 322 and the
    # red tile tower's right face is about x 1236. That span is 914px, wider
    # than 864, so a 4:5 frame cannot keep the curved roof and the red tower
    # together.
    #
    # The pumping-station hall, the dark upper volume, and the white boxes
    # measure about x 512–1088. That is wider than an 18% glide can hold.
    # This clip eases only across the slack that keeps the dark volume's
    # right end and the white boxes inside every frame with a 12px pad. The
    # default center sweep is unchanged.
    {
        "entry_id": "NL-01-210",
        "folder": "Almere",
        "subject_x": 800.0,
        "subject_span": (512.0, 1088.0),
        "window_start": 260.0,
        "window_end": 300.0,
    },
    # The Kerkje aan de Zee, its onion lantern, and the far end of the nave
    # measure about x 268–984. An 18% glide on that center would leave the
    # plate. This clip eases a shorter distance so the tower, the lantern,
    # and the nave end stay inside every frame with a 12px pad. The lantern
    # already reaches near the top of the daylight plate. The default center
    # sweep is unchanged.
    {
        "entry_id": "NL-01-211",
        "folder": "Urk",
        "subject_x": 626.0,
        "subject_span": (268.0, 984.0),
        "window_start": 156.0,
        "window_end": 196.0,
    },
    # NL-01-212 is not swept. The Magnuskerk nave and its saddle-roof tower
    # run about x 520–1500, wider than 864, so a 4:5 frame cannot keep both roofs.
    #
    # NL-01-213 is not swept. The two Rolde chambers sit apart under the
    # oaks, about x 400–1500, so a 4:5 frame cannot keep both.
    #
    # The Niehove hall is one brick roof with a ridge turret near x 1010.
    # The hall runs wider than 864. This clip eases only across the slack
    # that keeps the turret and the roof that still fits (x 600–1420) inside
    # every frame with a 12px pad. The far ends of the hall stay out. The
    # default center sweep is unchanged.
    {
        "entry_id": "NL-01-214",
        "folder": "Niehove",
        "subject_x": 1010.0,
        "subject_span": (600.0, 1420.0),
        "window_start": 568.0,
        "window_end": 588.0,
    },
    # The Sint-Jozefkathedraal is one basilica: nave, hexagonal tower, and
    # open iron spire, about x 916–1654. That is wider than an 18% glide can
    # hold. This clip eases only across the slack that keeps the nave, the
    # tower, and the spire inside every frame with a 12px pad. The spire
    # tip is near y 35, under the top of the plate. The default center
    # sweep is unchanged.
    {
        "entry_id": "NL-01-215",
        "folder": "Groningen",
        "subject_x": 1285.0,
        "subject_span": (916.0, 1654.0),
        "window_start": 802.0,
        "window_end": 904.0,
    },
    # Museum de Fundatie's neoclassical front and the ceramic ellipse measure
    # about x 620–1440. That is wider than an 18% glide can hold. This clip
    # eases only across the slack that keeps the ellipse and that front
    # inside every frame with a 12px pad. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-216",
        "folder": "Zwolle",
        "subject_x": 1030.0,
        "subject_span": (620.0, 1440.0),
        "window_start": 588.0,
        "window_end": 608.0,
    },
    # The Bovenkerk tower and the nave, including the roof pinnacles, measure
    # about x 480–1300. That is wider than an 18% glide can hold. This clip
    # eases only across the slack that keeps the spire and the nave inside
    # every frame with a 12px pad. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-217",
        "folder": "Kampen",
        "subject_x": 890.0,
        "subject_span": (480.0, 1300.0),
        "window_start": 448.0,
        "window_end": 468.0,
    },
    # The Bolsward scroll gable and the roof tower, taken together, measure
    # about x 464–1291. That is wider than an 18% glide can hold. This clip
    # eases only across the slack that keeps the gable and the tower inside
    # every frame with a 12px pad. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-218",
        "folder": "Bolsward",
        "subject_x": 877.5,
        "subject_span": (464.0, 1291.0),
        "window_start": 439.0,
        "window_end": 452.0,
    },
    # The Hollum lighthouse stands right of plate center. Same glide, aimed
    # at the shaft measured on this daylight plate (x 1112–1348), so the
    # banded tower and the red lantern stay inside the 864 frame. The
    # default center anchor is unchanged.
    {
        "entry_id": "NL-01-219",
        "folder": "Hollum",
        "subject_x": 1230.0,
        "subject_span": (1112.0, 1348.0),
    },
    # The Bonnefantenmuseum's E-shaped wings run wider than 864. This clip
    # eases only across the slack that keeps the zinc dome and the central
    # mass that still fits (x 500–1320) inside every frame with a 12px pad.
    # The outer wings stay out, so one end does not leave as the other comes
    # in. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-220",
        "folder": "Maastricht",
        "subject_x": 910.0,
        "subject_span": (500.0, 1320.0),
        "window_start": 468.0,
        "window_end": 488.0,
    },
    # Kasteel Eijsden has no clip. The stepped gable left of the round tower
    # and the three helmet roofs do not fit together inside 864. On this
    # daylight plate the gable's leftmost brick is x 354 and the right helmet
    # roof reaches x 1471, a span of 1117. Holding the gable would drop a
    # helmet. Holding the helmets would drop the gable. The default center
    # sweep is unchanged.
    # The Onze Lieve Vrouwetoren stands just left of plate center. Same glide,
    # aimed at the shaft and onion crown measured on this daylight plate
    # (x 810–1100), so the free-standing tower stays inside the 864 frame.
    # The default center anchor is unchanged.
    {
        "entry_id": "NL-01-222",
        "folder": "Amersfoort",
        "subject_x": 955.0,
        "subject_span": (810.0, 1100.0),
    },
    # The Koepelkerk dome and the unfinished square tower, taken together,
    # measure about x 560–1380. That is wider than an 18% glide can hold.
    # This clip eases only across the slack that keeps the dome and the
    # tower inside every frame with a 12px pad. The default center sweep
    # is unchanged.
    {
        "entry_id": "NL-01-223",
        "folder": "Willemstad",
        "subject_x": 970.0,
        "subject_span": (560.0, 1380.0),
        "window_start": 528.0,
        "window_end": 548.0,
    },
    # The white church and its bell tower sit left of plate center. On this
    # daylight plate the tower, including its top, and the church wall run
    # about x 598–756. The same 18% glide, aimed at that mass, holds both for
    # every frame. The default center anchor is unchanged.
    {
        "entry_id": "NL-01-224",
        "folder": "Rincon",
        "subject_x": 677.0,
        "subject_span": (598.0, 756.0),
    },
    # The Waterloopbos wave basin sits on the plate center. The default 18%
    # glide holds the concrete basin. The center anchor is unchanged.
    {"entry_id": "NL-01-225", "folder": "Marknesse"},
    # The Marker Wadden timber pavilion, roof included, measures about
    # x 830–1220. An 18% glide is too long for that roof and walks past it.
    # This clip eases across a shorter window that keeps the whole pavilion
    # inside every frame. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-226",
        "folder": "Lelystad",
        "subject_x": 1025.0,
        "subject_span": (830.0, 1220.0),
        "window_start": 520.0,
        "window_end": 640.0,
    },
    # De Wachter's sails, cap to the lower right sail tip, measure
    # x 979–1496. That is wider than an 18% glide can hold. This clip
    # eases only across the slack that keeps every sail inside every
    # frame with a 12px pad. The trees beside the mill stay out. The
    # default center sweep is unchanged.
    {
        "entry_id": "NL-01-227",
        "folder": "Zuidlaren",
        "subject_x": 1237.5,
        "subject_span": (979.0, 1496.0),
        "window_start": 644.0,
        "window_end": 967.0,
    },
    # The Tweede Gesticht's brick front runs about x 265–1784, wider
    # than 864. The only tower is the clock turret over the gate
    # (x 947–998). This clip eases only across the slack that keeps
    # that turret and the central bays (x 572–1372) inside every frame
    # with a 12px pad. The outer ends of the front stay out. The
    # default center sweep is unchanged.
    {
        "entry_id": "NL-01-228",
        "folder": "Veenhuizen",
        "subject_x": 972.0,
        "subject_span": (572.0, 1372.0),
        "window_start": 520.0,
        "window_end": 560.0,
    },
    # The Noordpolderzijl sluice house's pale wall measures x 709–998.
    # Same glide, aimed at that wall on this daylight plate, so both
    # ends stay inside the 864 frame and clear of either edge. The
    # default center anchor is unchanged.
    {
        "entry_id": "NL-01-229",
        "folder": "Noordpolderzijl",
        "subject_x": 853.5,
        "subject_span": (709.0, 998.0),
    },
    # Borg Verhildersum's roof, chimneys included, measures about
    # x 739–1297. That is wider than an 18% glide can hold. This clip
    # eases only across the slack that keeps the roof and both chimney
    # stacks inside every frame with a 12px pad. The trees at the plate
    # edges stay out. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-230",
        "folder": "Leens",
        "subject_x": 1018.0,
        "subject_span": (739.0, 1297.0),
        "window_start": 445.0,
        "window_end": 727.0,
    },
    # The Campveerse Toren stands right of plate center. Same glide,
    # aimed at the shaft measured on this daylight plate (x 1053–1439),
    # so the spire stays inside the 864 frame. The default center
    # anchor is unchanged.
    {
        "entry_id": "NL-01-231",
        "folder": "Veere",
        "subject_x": 1246.0,
        "subject_span": (1053.0, 1439.0),
    },
    # The Sluis belfry stands right of plate center. Same glide, aimed
    # at the shaft measured on this daylight plate (x 1053–1348), so
    # the open lantern stays inside the 864 frame. The default center
    # anchor is unchanged.
    {
        "entry_id": "NL-01-232",
        "folder": "Sluis",
        "subject_x": 1200.5,
        "subject_span": (1053.0, 1348.0),
    },
    # NL-01-233 is not swept. The Spanjaardsgat's two pepperpot towers
    # run about x 500–1480, wider than 864, so a 4:5 frame cannot keep
    # both spires.
    #
    # NL-01-234 is not swept. Kasteel Heeswijk's towers run about
    # x 405–1530, wider than 864, so a 4:5 frame cannot keep every tower.
    #
    # The Heksenwaag's stepped gable (x 834–1009, tip at x 914) and the
    # long side together run x 713–1633, wider than 864. This clip eases
    # only across the slack that keeps the gable and the wall that still
    # fits (x 713–1529) inside every frame with a 12px pad. The far right
    # eave stays out. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-235",
        "folder": "Oudewater",
        "subject_x": 1121.0,
        "subject_span": (713.0, 1529.0),
        "window_start": 677.0,
        "window_end": 701.0,
    },
    # The Bergkerk's two spires, both of which already touch the top of
    # this daylight plate, measure about x 726–1258. That is wider than
    # an 18% glide can hold. This clip eases only across the slack that
    # keeps both spires inside every frame with a 12px pad. The sweep
    # does not crop them further at the top. The default center sweep
    # is unchanged.
    {
        "entry_id": "NL-01-236",
        "folder": "Deventer",
        "subject_x": 992.0,
        "subject_span": (726.0, 1258.0),
        "window_start": 406.0,
        "window_end": 714.0,
    },
    # NL-01-237 is not swept. The Ladder's stone steps run about
    # x 2–1462, wider than 864, so a 4:5 frame cannot keep the flight.
    #
    # NL-01-238 is not swept. Fort Amsterdam's headland runs from the
    # left edge of the plate past x 1383, wider than 864.
    #
    # NL-01-239 is not swept. The Makkum lock house meets the left edge
    # of the plate (non-sky from y 198 at x 0), so a lateral sweep would
    # crop that wall further.
    #
    # The Onze-Lieve-Vrouwebasiliek's two west towers measure about
    # x 474–1291. That is wider than an 18% glide can hold. This clip
    # eases only across the slack that keeps both towers inside every
    # frame with a 12px pad. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-240",
        "folder": "Maastricht",
        "subject_x": 882.5,
        "subject_span": (474.0, 1291.0),
        "window_start": 439.0,
        "window_end": 462.0,
    },
    # NL-01-241 is not swept. The Staphorst farm roofs run from the left
    # edge (x 0) to a second row at x 1680–1919, wider than 864.
    #
    # Kasteel Rechteren's round tower (tip x 463–515) stands on a wing
    # that continues past x 1500, wider than 864. This clip eases only
    # across the slack that keeps the tower and the wing that still fits
    # (x 400–1200) inside every frame with a 12px pad. The far wing stays
    # out. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-242",
        "folder": "Dalfsen",
        "subject_x": 800.0,
        "subject_span": (400.0, 1200.0),
        "window_start": 348.0,
        "window_end": 388.0,
    },
    # The Sint-Clemenskerk spire already touches the top of this daylight
    # plate. The shaft stands left of plate center (x 451–730). The same
    # 18% glide, aimed as close to the tower as the plate allows, keeps
    # the shaft inside the 864 frame. The sweep does not crop the spire
    # further. The default center anchor is unchanged.
    {
        "entry_id": "NL-01-243",
        "folder": "Steenwijk",
        "subject_x": 604.8,
        "subject_span": (451.0, 730.0),
    },
    # NL-01-244 is not swept. Slot Zuylen's roof runs about x 465–1827,
    # wider than 864, so a 4:5 frame cannot keep both ends.
    #
    # NL-01-245 is not swept. Kasteel Loenersloot's tower and the long
    # wing run about x 633–1919, wider than 864.
    #
    # NL-01-246 is not swept. Fort Honswijk's earthwork skyline runs the
    # full plate width, so a 4:5 frame cannot keep both ends.
    #
    # NL-01-247 is not swept. The Oostvaardersplassen horizon runs the
    # full plate width, with no bounded roof inside 864.
    #
    # NL-01-248 is not swept. The Zeewolde harbour roofs run from about
    # x 1263 to the right edge of the plate, wider than 864, and the
    # right-hand building already meets that edge.
    #
    # NL-01-249 is not swept. Bronkhorst's roofs run about x 0–1536,
    # wider than 864, and the left roof already meets the plate edge.
    #
    # Kasteel Ammersoyen's two round towers measure about x 621–1432
    # (tips near x 697 and x 1356). That is wider than an 18% glide can
    # hold. This clip eases only across the slack that keeps both towers
    # inside every frame with a 12px pad. The trees at the right edge
    # stay out. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-250",
        "folder": "Ammerzoden",
        "subject_x": 1026.5,
        "subject_span": (621.0, 1432.0),
        "window_start": 580.0,
        "window_end": 609.0,
    },
    # The Sint-Nicolaaskerk roof, onion spire included, measures about
    # x 570–1577, wider than 864. The only distinct tip is the onion
    # (x 735, y 10, under the top of the plate). This clip eases only
    # across the slack that keeps the spire and the nave that still fits
    # (x 570–1386) inside every frame with a 12px pad. The far end of the
    # nave stays out. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-251",
        "folder": "Dwingeloo",
        "subject_x": 978.0,
        "subject_span": (570.0, 1386.0),
        "window_start": 534.0,
        "window_end": 558.0,
    },
    # NL-01-252 is not swept. The Boog van Ziel parapet runs about
    # x 0–1742, wider than 864, and already meets the left edge.
    #
    # The Schierstins tower (x 436–977, crown y 30 at x 702) and the
    # neck-gable wing (peak x 1162, roof on toward x 1460) together run
    # wider than 864. This clip eases only across the slack that keeps
    # the tower crown and the neck gable (x 436–1252) inside every frame
    # with a 12px pad. The far eave of the wing stays out. The default
    # center sweep is unchanged.
    {
        "entry_id": "NL-01-253",
        "folder": "Feanwalden",
        "subject_x": 844.0,
        "subject_span": (436.0, 1252.0),
        "window_start": 400.0,
        "window_end": 424.0,
    },
    # NL-01-254 is not swept. The four caissons measure about
    # x 195–656, 671–1001, 1106–1395, and 1548–1792. Outer span
    # x 195–1792 is wider than 864, so a 4:5 frame cannot keep every caisson.
    #
    # Kasteel Arcen's gatehouse, octagonal spire (tip x 818, y 63), and
    # the manor roof's right hip measure about x 674–1505. That is wider
    # than an 18% glide can hold. This clip eases only across the slack
    # that keeps the spire and that hip inside every frame with a 12px
    # pad. The trees past the hip stay out. The default center sweep is
    # unchanged.
    {
        "entry_id": "NL-01-255",
        "folder": "Arcen",
        "subject_x": 1089.5,
        "subject_span": (674.0, 1505.0),
        "window_start": 653.0,
        "window_end": 662.0,
    },
    # The Sint-Petrusbasiliek, spire included, measures about x 528–1768,
    # wider than 864. The only distinct tip is the spire (x 671, y 29).
    # This clip eases only across the slack that keeps the spire and the
    # nave that still fits (x 528–1344) inside every frame with a 12px
    # pad. The far end of the nave stays out. The default center sweep
    # is unchanged.
    {
        "entry_id": "NL-01-256",
        "folder": "Oirschot",
        "subject_x": 936.0,
        "subject_span": (528.0, 1344.0),
        "window_start": 492.0,
        "window_end": 516.0,
    },
    # NL-01-257 is not swept. The cliff and the stair run from the left
    # edge (skyline about y 299 at x 0) to the cove drop near x 1440,
    # wider than 864.
    #
    # The Oranjestad ruin's tower (x 402–655) and the roofless nave,
    # which continues to about x 1600, together run wider than 864. This
    # clip eases only across the slack that keeps the tower and the nave
    # that still fits (x 402–1218) inside every frame with a 12px pad.
    # The far end of the nave stays out. The default center sweep is
    # unchanged.
    {
        "entry_id": "NL-01-258",
        "folder": "Oranjestad",
        "subject_x": 810.0,
        "subject_span": (402.0, 1218.0),
        "window_start": 366.0,
        "window_end": 390.0,
    },
    # NL-01-259 is not swept. Havezate De Havixhorst's hipped roof runs
    # about x 400–1480, wider than 864, so a 4:5 frame cannot keep both ends.
    #
    # The Sint-Margaretakerk, saddle-roof tower included, measures about
    # x 649–1297. That is wider than an 18% glide can hold. This clip
    # eases only across the slack that keeps the tower and the choir
    # inside every frame with a 12px pad. The trees past the choir stay
    # out. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-260",
        "folder": "Norg",
        "subject_x": 973.0,
        "subject_span": (649.0, 1297.0),
        "window_start": 445.0,
        "window_end": 637.0,
    },
    # NL-01-261 is not swept. The west gable (about x 426–794) and the
    # stair turret (about x 1666–1703) together run wider than 864.
    #
    # NL-01-262 is not swept. The 1708 gate (about x 123–464, crown at
    # y 3) and the villa (about x 624–1710) together run wider than 864.
    #
    # The Zuidertoren stands right of plate center. Same glide, aimed at
    # the shaft measured on this daylight plate (x 1203–1368), so the
    # copper dome and the monk finial stay inside the 864 frame. The
    # finial is at y 81, under the top of the plate. The default center
    # anchor is unchanged.
    {
        "entry_id": "NL-01-263",
        "folder": "Schiermonnikoog",
        "subject_x": 1285.5,
        "subject_span": (1203.0, 1368.0),
    },
    # NL-01-264 is not swept. The unfinished nave (about x 378–1004) and
    # the separate tower (about x 1261–1516) together run wider than 864.
    #
    # NL-01-265 is not swept. The foundation walls are separate low runs
    # from about x 84 to x 1034, wider than 864, with no tower to hold.
    #
    # The seven Houtribsluizen lift towers measure about x 622–1394.
    # That is wider than an 18% glide can hold. This clip eases only
    # across the slack that keeps every tower inside every frame with a
    # 12px pad. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-266",
        "folder": "Lelystad",
        "subject_x": 1008.0,
        "subject_span": (622.0, 1394.0),
        "window_start": 542.0,
        "window_end": 610.0,
    },
    # The Grote Kerk at Veere, low tower roof included, measures about
    # x 576–1522, wider than 864. The tower roof is x 707–1010 (peak
    # x 859, y 145). This clip eases only across the slack that keeps
    # that roof and the basilica that still fits (x 576–1392) inside
    # every frame with a 12px pad. The far end stays out. The default
    # center sweep is unchanged.
    {
        "entry_id": "NL-01-267",
        "folder": "Veere",
        "subject_x": 984.0,
        "subject_span": (576.0, 1392.0),
        "window_start": 540.0,
        "window_end": 564.0,
    },
    # NL-01-268 is not swept. The quay roofs meet the left edge (skyline
    # y 360 at x 0) and the row runs past x 989, wider than 864.
    #
    # NL-01-269 is not swept. Fort Sint Pieter's wall is a flat skyline
    # at about y 440 from x 0 to x 1919, so a 4:5 frame cannot keep both ends.
    #
    # The Meerssen basilica's roof, turret, and pinnacles measure about
    # x 686–1506 (turret x 962–997, a pinnacle near x 1275). That is
    # wider than an 18% glide can hold. This clip eases only across the
    # slack that keeps the turret and those pinnacles inside every frame
    # with a 12px pad. The trees outside that span stay out. The default
    # center sweep is unchanged.
    {
        "entry_id": "NL-01-270",
        "folder": "Meerssen",
        "subject_x": 1096.0,
        "subject_span": (686.0, 1506.0),
        "window_start": 654.0,
        "window_end": 674.0,
    },
    # NL-01-271 is not swept. The Begijnhof roofs run the full plate
    # width, and the right-hand roofs already meet the top edge.
    #
    # The Hampoort measures about x 491–1443, wider than 864. The pediment
    # is x 696–1258 (peak x 927, y 129). This clip eases only across the
    # slack that keeps the pediment and the gate that still fits
    # (x 491–1307) inside every frame with a 12px pad. The right flank
    # stays out. The default center sweep is unchanged.
    {
        "entry_id": "NL-01-272",
        "folder": "Grave",
        "subject_x": 899.0,
        "subject_span": (491.0, 1307.0),
        "window_start": 455.0,
        "window_end": 479.0,
    },
    # The Cellebroederspoort's two spires, taken together, measure about
    # x 727–1224 (tips near x 820 and x 1133, the right tip at y 97).
    # That is wider than an 18% glide can hold. This clip eases only
    # across the slack that keeps both spires inside every frame with a
    # 12px pad. The trees to the right stay out. The default center
    # sweep is unchanged.
    {
        "entry_id": "NL-01-273",
        "folder": "Kampen",
        "subject_x": 975.5,
        "subject_span": (727.0, 1224.0),
        "window_start": 372.0,
        "window_end": 715.0,
    },
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


def sweep_x(
    n: int,
    subject_x: float = SUBJECT_X,
    bounds: tuple[float, float] | None = None,
) -> float:
    """Origin of the 864-wide window. Left to right, ease in and out, no vertical.

    ``subject_x`` defaults to the plate center. Passing the same center leaves
    the glide identical. An off-center landmark passes its own center.

    ``bounds`` is an explicit (start, end) pair for one scene whose subject
    cannot be held by that centered 18% glide without leaving the plate.
    The default path does not use it.
    """
    u = n / (FRAMES - 1)
    ease = 0.5 - 0.5 * math.cos(math.pi * u)
    if bounds is not None:
        start, end = bounds
        return start + (end - start) * ease
    travel = PLATE_W * SWEEP_TRAVEL_FRAC
    # Mid-glide puts the subject on the center of the 864 frame.
    mid = subject_x - (PHOTO_W / 2.0)
    return (mid - travel / 2.0) + travel * ease


def assert_sweep_path(subject_x: float = SUBJECT_X) -> None:
    xs = [sweep_x(n, subject_x) for n in range(FRAMES)]
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
        subject_in_frame = subject_x - x
        if not (0.0 <= subject_in_frame <= PHOTO_W):
            raise SystemExit("subject left the frame")
        # Middle half of the frame. The glide is symmetric about the subject,
        # so the window never runs past it to the edge of the plate.
        if not (PHOTO_W * 0.25 <= subject_in_frame <= PHOTO_W * 0.75):
            raise SystemExit(f"subject left the middle half at window {x:.2f}")
        if abs((x + half) - subject_x) - (travel / 2.0) > 0.05:
            raise SystemExit("window traveled past the subject")


def assert_span_in_frame(
    subject_x: float,
    span: tuple[float, float],
    bounds: tuple[float, float] | None = None,
) -> None:
    """The whole subject, not only its center, stays inside every frame."""
    left, right = span
    if not (left < subject_x < right):
        raise SystemExit("subject center is outside its span")
    pad = 12.0
    for n in range(FRAMES):
        x = sweep_x(n, subject_x, bounds)
        if left < x + pad or right > x + PHOTO_W - pad:
            raise SystemExit(
                f"subject {left:.1f}-{right:.1f} leaves the frame at {n} window {x:.1f}"
            )


def assert_held_glide(bounds: tuple[float, float]) -> None:
    """A shorter left-to-right glide that stays on the plate.

    Used only when the centered 18% path cannot hold the subject. The default
    center sweep is not checked here.
    """
    start, end = bounds
    if not end > start:
        raise SystemExit("held glide does not move left to right")
    xs = [sweep_x(n, bounds=bounds) for n in range(FRAMES)]
    if abs(xs[0] - start) > 1e-6 or abs(xs[-1] - end) > 1e-6:
        raise SystemExit("held glide did not ease across its window")
    for i in range(1, FRAMES):
        if xs[i] + 1e-6 < xs[i - 1]:
            raise SystemExit("held glide reversed direction")
    for x in xs:
        if x < -1e-3 or x + PHOTO_W > PLATE_W + 1e-3:
            raise SystemExit(f"held glide window {x:.2f} leaves the plate")


def render_sweep_frame(
    plate: np.ndarray,
    n: int,
    subject_x: float = SUBJECT_X,
    bounds: tuple[float, float] | None = None,
) -> np.ndarray:
    x = np.float32(sweep_x(n, subject_x, bounds))
    map_x = np.broadcast_to(np.arange(PHOTO_W, dtype=np.float32) + x, (PHOTO_H, PHOTO_W)).copy()
    map_y = np.broadcast_to(np.arange(PHOTO_H, dtype=np.float32)[:, None], (PHOTO_H, PHOTO_W)).copy()
    # One source pixel per output pixel, and the row index never changes.
    # A window origin past 1024 is not an exact float32, so the first step
    # can be off by one ulp. That is not a scale change. The default glide
    # stays under that origin and still uses the tighter check. An aimed
    # origin below 1024 can miss the same way; one ulp there is still not
    # a scale change, and the default center math is untouched.
    step = float(map_x[0, 1] - map_x[0, 0])
    limit = 2e-4 if bounds is not None else 1e-5
    if bounds is None and subject_x != SUBJECT_X:
        limit = max(limit, 6.2e-5)
    if abs(step - 1.0) > limit:
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


def encode_sweep(
    plate: np.ndarray,
    dest: Path,
    subject_x: float = SUBJECT_X,
    bounds: tuple[float, float] | None = None,
) -> float:
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
            frame = render_sweep_frame(plate, n, subject_x, bounds)
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
        subject_x = float(scene.get("subject_x", SUBJECT_X))
        span = scene.get("subject_span")
        bounds = None
        if "window_start" in scene:
            bounds = (float(scene["window_start"]), float(scene["window_end"]))
            assert_held_glide(bounds)
        elif subject_x != SUBJECT_X or span is not None:
            assert_sweep_path(subject_x)
        if span is not None:
            assert_span_in_frame(subject_x, span, bounds)
        plate = load_sweep_plate(anchor)
        mae = encode_sweep(plate, dest, subject_x, bounds)
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
                    "travel_frac": (
                        round((bounds[1] - bounds[0]) / PLATE_W, 4)
                        if bounds is not None
                        else SWEEP_TRAVEL_FRAC
                    ),
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
