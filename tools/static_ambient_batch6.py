#!/usr/bin/env python3
"""Static-camera ambient clips for NL 360 rebuild batch 6.

Camera stays locked on the genuine daylight 4:5 master. The 190px label
bar (including its 2px hairline) is cropped off before any frame is made.
Only sky, still water, and foliage already in the plate are displaced, and
only inside their own masks, so stone cannot drift.

This is not an orbit, a sweep, or an interpolation between generated views.
Night masters are not read. A failed prompt is not re-rolled.
"""

from __future__ import annotations

import hashlib
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
BAR_PX = 190
DEAD_LIFE = 0.04

SCENES = (
    {
        "entry_id": "NL-01-075",
        "caption": "Valkhof, Nijmegen",
        "anchor": "library/world/Netherlands/Nijmegen/nl-01-075-daylight-4x5.png",
        "out": "library/world/Netherlands/Nijmegen/nl-01-075-motion-10s-4x5.mp4",
        "poster": "library/world/Netherlands/Nijmegen/nl-01-075-motion-10s-4x5-poster.jpg",
        "life": "Cloud drift and tree and lawn sway. The chapel, the Barbarossa ruin, and the path stay locked.",
        "pedestrians": "People on the path stay on the locked plate. A synthetic walk would invent limbs.",
        "flags": "No flag separated from the plate.",
        "water_note": "The distant Waal did not form a still-water sheet apart from the sky, so it is not given its own ripple.",
    },
    {
        "entry_id": "NL-01-076",
        "caption": "Vesting, Naarden",
        "anchor": "library/world/Netherlands/Naarden/nl-01-076-daylight-4x5.png",
        "out": "library/world/Netherlands/Naarden/nl-01-076-motion-10s-4x5.mp4",
        "poster": "library/world/Netherlands/Naarden/nl-01-076-motion-10s-4x5-poster.jpg",
        "life": "Moat ripple, bastion-grass sway, and cloud drift. The brick ramparts stay locked.",
        "pedestrians": "No pedestrians in the plate.",
        "flags": "No flag in the plate.",
        "water_note": "The moat is the smooth grey-green sheet in the lower frame, plus the dark still channels between the bastions.",
    },
    {
        "entry_id": "NL-01-078",
        "caption": "Kasteel de Haar, Haarzuilens",
        "anchor": "library/world/Netherlands/Haarzuilens/nl-01-078-daylight-4x5.png",
        "out": "library/world/Netherlands/Haarzuilens/nl-01-078-motion-10s-4x5.mp4",
        "poster": "library/world/Netherlands/Haarzuilens/nl-01-078-motion-10s-4x5-poster.jpg",
        "life": "Cloud drift and tree sway. The castle stays locked.",
        "pedestrians": "No pedestrians in the plate.",
        "flags": "Flags sit on the turrets. A red mask also caught brick, so the flags stay with the locked castle.",
        "water_note": "The moat did not separate from bank foliage as a smooth water sheet, so it is not given its own ripple.",
    },
)


def crop_plate(path: Path) -> np.ndarray:
    im = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if im is None:
        raise SystemExit(f"missing anchor {path}")
    if im.shape[1] != PHOTO_W or im.shape[0] != PHOTO_H + BAR_PX:
        raise SystemExit(f"{path} is {im.shape[1]}x{im.shape[0]}, expected {PHOTO_W}x{PHOTO_H + BAR_PX}")
    plate = im[:PHOTO_H].copy()
    bar = im[PHOTO_H:]
    # The label bar is a flat dark strip. A flat bottom row on the photo would mean the crop slipped.
    if float(bar[:2].std()) > 8:
        raise SystemExit(f"{path} rows under y={PHOTO_H} are not a flat label bar")
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


def _local_std(gray: np.ndarray, radius: int) -> np.ndarray:
    g = gray.astype(np.float32)
    k = 2 * radius + 1
    mu = cv2.blur(g, (k, k))
    mu2 = cv2.blur(g * g, (k, k))
    return np.sqrt(np.maximum(mu2 - mu * mu, 0))


def build_masks(plate: np.ndarray) -> dict[str, np.ndarray]:
    hsv = cv2.cvtColor(plate, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    height, width = h.shape
    yy = np.arange(height)[:, None]
    gray = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY)
    std = _local_std(gray, 3)

    overcast = (s < 70) & (v > 145)
    blue_sky = (h >= 90) & (h <= 125) & (s >= 15) & (s < 210) & (v > 145)
    sky_cand = (overcast | blue_sky).astype(np.uint8)
    sky_cand[(h >= 32) & (h <= 88) & (s > 48)] = 0
    sky_cand[((h < 12) | (h > 168)) & (s > 55)] = 0
    sky = _components(sky_cand, lambda x, y, w, hh, area: y <= 8 and area > 400)

    # Stop the sky at the first hard edge in each column so a pale tower
    # face cannot inherit the cloud drift. The cut is smoothed so one noisy
    # pixel does not saw the cloud field.
    edge = std > 28
    edge[:40] = False
    has = edge.any(axis=0)
    first = np.where(has, np.argmax(edge, axis=0), height).astype(np.float32)
    first = cv2.GaussianBlur(first.reshape(1, -1), (31, 1), 0).ravel()
    sky[yy >= (first[None, :] - 4)] = 0
    sky = cv2.erode(sky, np.ones((3, 3), np.uint8), iterations=1)

    # Still water: a smooth sheet, darker than stone, not a textured lawn.
    # Grey-green moats in this batch are low-saturation. Dark channels between
    # bastions are smooth and saturated but not leafy (local contrast stays low).
    grey = (yy > 760) & (std < 8.0) & (s < 50) & (v > 45) & (v < 155) & (sky == 0)
    inner = (yy > 690) & (yy < 870) & (std < 5.0) & (s >= 80) & (s <= 180) & (v >= 30) & (v < 78) & (sky == 0)
    water = _components(
        (grey | inner).astype(np.uint8),
        lambda x, y, w, hh, area: area > 1800 and w > 36,
    )
    water = cv2.erode(water, np.ones((3, 3), np.uint8), iterations=1)
    water[sky > 0] = 0

    fol_cand = (
        (h >= 18) & (h <= 95) & (s >= 35) & (v >= 25) & (v <= 200) & (sky == 0) & (water == 0)
    ).astype(np.uint8)
    foliage = _components(fol_cand, lambda x, y, w, hh, area: area > 180)
    foliage = cv2.erode(foliage, np.ones((3, 3), np.uint8), iterations=1)
    foliage[water > 0] = 0
    foliage[sky > 0] = 0

    # Flags are not segmented. On these plates a saturated-red mask also
    # caught sky rim and brick. Leaving flags on the locked plate is safer
    # than wobbling stone.
    flags = np.zeros((height, width), np.uint8)
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
    # Every displacement is a sine that is 0 at frame 0 and at frame FRAMES, so the loop closes.
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

    if np.any(masks["sky"]):
        dx = (18.0 * s1 * factors["sky"]).astype(np.float32)
        dy = (1.6 * s1 * factors["sky"]).astype(np.float32)
        _apply(out, plate, masks["sky"], dx, dy)
        breath = (8.0 * s1 * np.sin(xs * 0.03 + ys * 0.012) * factors["sky"]).astype(np.float32)
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
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{PHOTO_W}x{PHOTO_H}",
        "-r", str(FPS), "-i", "-",
        "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "18", "-preset", "medium", "-movflags", "+faststart",
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


def coverage(masks: dict[str, np.ndarray]) -> dict[str, float]:
    total = float(PHOTO_H * PHOTO_W)
    return {name: round(float(np.count_nonzero(mask)) / total, 4) for name, mask in masks.items()}


def probe(path: Path) -> dict:
    raw = subprocess.check_output(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,nb_frames,duration,codec_name,avg_frame_rate,pix_fmt",
            "-show_entries", "format=duration",
            "-of", "json", str(path),
        ]
    )
    return json.loads(raw)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(scene: dict, row: dict) -> None:
    path = ROOT / "manifests" / f"{scene['entry_id']}.json"
    original = path.read_text()
    data = json.loads(original)
    if data.get("approval_status") != "Approved" or "Night" not in data.get("qc_status", ""):
        raise SystemExit(f"{scene['entry_id']} manifest is not an approved night card; refusing to rewrite it")
    if "file_motion_10s_4x5" in data:
        return
    rel_out = scene["out"].split("library/world/", 1)[1]
    rel_poster = scene["poster"].split("library/world/", 1)[1]
    # Splice the new keys onto the original text so approved-card escaping stays put.
    clip = {
        "status": "Candidate",
        "work_order": "wo-nl-360-rebuild-2026-10-02",
        "batch": 6,
        "method": "static-ambient",
        "duration_s": 10.0,
        "width": PHOTO_W,
        "height": PHOTO_H,
        "fps": FPS,
        "format": "4:5",
        "camera": "locked",
        "anchor": scene["anchor"].split("library/world/", 1)[1],
        "anchor_kind": "genuine-daylight 4:5 master; night master not used; label bar cropped",
        "label_bar_px_cropped": BAR_PX,
        "life": scene["life"],
        "pedestrians": scene["pedestrians"],
        "flags": scene["flags"],
        "water_note": scene["water_note"],
        "life_coverage": row["life_coverage"],
        "forbidden_method_not_used": "orbit, sweep, viewpoint interpolation, optical-flow blend between generated views, subject-pinned pan",
        "qc": "Candidate only. Not Cosmo QC. Not approved. Do not merge.",
        "cosmo_qc_required": True,
        "do_not_merge": True,
    }
    addition = (
        ',\n  "file_motion_10s_4x5": '
        + json.dumps(rel_out)
        + ',\n  "file_motion_poster": '
        + json.dumps(rel_poster)
        + ',\n  "motion_clip": '
        + json.dumps(clip, indent=2).replace("\n", "\n  ")
    )
    stripped = original.rstrip()
    if not stripped.endswith("}"):
        raise SystemExit(f"{path} does not end with an object")
    # The file ends with the daylight_variant close, then the root close.
    head, _, _tail = stripped.rpartition("}")
    if not head.rstrip().endswith("}"):
        raise SystemExit(f"{path} root object is not where a splice expects it")
    path.write_text(head.rstrip() + addition + "\n  }\n}\n")
    check = json.loads(path.read_text())
    if check.get("approval_status") != "Approved" or check["motion_clip"]["method"] != "static-ambient":
        raise SystemExit(f"{scene['entry_id']} manifest splice failed")


def main() -> None:
    rows = []
    for scene in SCENES:
        plate = crop_plate(ROOT / scene["anchor"])
        masks = build_masks(plate)
        cov = coverage(masks)
        life = round(sum(cov.values()), 4)
        if life < DEAD_LIFE:
            raise SystemExit(
                f"{scene['entry_id']} life coverage {life} is below {DEAD_LIFE}. "
                "Static ambient would feel dead. Inspect before any subject-pinned pan."
            )
        # Peak frame must actually move the life masks, and must not move stone.
        factors = {
            "sky": _factor(masks["sky"], 32.0),
            "water": _factor(masks["water"], 14.0),
            "foliage": _factor(masks["foliage"], 16.0),
            "flags": _factor(masks["flags"], 6.0),
        }
        peak = render_frame(plate, masks, factors, FRAMES // 4)
        life_px = (masks["sky"] | masks["water"] | masks["foliage"]) > 0
        locked = ~life_px
        locked_mae = float(np.abs(peak.astype(np.int16) - plate.astype(np.int16))[locked].mean()) if locked.any() else 0.0
        moving_mae = float(np.abs(peak.astype(np.int16) - plate.astype(np.int16))[life_px].mean()) if life_px.any() else 0.0
        if locked_mae != 0.0:
            raise SystemExit(f"{scene['entry_id']} locked MAE {locked_mae}")
        if moving_mae < 0.45:
            raise SystemExit(f"{scene['entry_id']} moving MAE {moving_mae} — ambient life is dead")
        encode(plate, masks, ROOT / scene["out"])
        poster = ROOT / scene["poster"]
        ok = cv2.imwrite(str(poster), plate, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if not ok:
            raise SystemExit(f"poster write failed {poster}")
        info = probe(ROOT / scene["out"])
        stream = info["streams"][0]
        duration = float(info["format"]["duration"])
        if stream["width"] != PHOTO_W or stream["height"] != PHOTO_H:
            raise SystemExit(f"{scene['entry_id']} encoded {stream['width']}x{stream['height']}")
        if int(stream["nb_frames"]) != FRAMES or abs(duration - 10.0) > 0.001:
            raise SystemExit(f"{scene['entry_id']} duration {duration} frames {stream.get('nb_frames')}")
        if stream["avg_frame_rate"] != "24/1":
            raise SystemExit(f"{scene['entry_id']} fps {stream['avg_frame_rate']}")
        row = {
            "entry_id": scene["entry_id"],
            "caption": scene["caption"],
            "method": "static-ambient",
            "camera": "locked",
            "life": scene["life"],
            "pedestrians": scene["pedestrians"],
            "flags": scene["flags"],
            "water_note": scene["water_note"],
            "life_coverage": life,
            "coverage": cov,
            "locked_mae_peak": locked_mae,
            "moving_mae_peak": round(moving_mae, 3),
            "duration_s": duration,
            "width": PHOTO_W,
            "height": PHOTO_H,
            "frames": FRAMES,
            "fps": FPS,
            "anchor": scene["anchor"],
            "anchor_sha256": sha256(ROOT / scene["anchor"]),
            "anchor_crop": f"top {PHOTO_W}x{PHOTO_H} of the genuine daylight 4:5 master (label bar and hairline removed)",
            "path": scene["out"],
            "poster": scene["poster"],
            "sha256": sha256(ROOT / scene["out"]),
            "subject_pinned_pan": False,
        }
        write_manifest(scene, row)
        rows.append(row)
        print(
            f"{scene['entry_id']} static-ambient life={life:.3f} "
            f"lockMAE={locked_mae:.2f} moveMAE={moving_mae:.2f} "
            f"{stream['width']}x{stream['height']} {duration}s"
        )
    evidence = {
        "work_order": "wo-nl-360-rebuild-2026-10-02",
        "batch": 6,
        "status": "Candidate",
        "cosmo_qc_required": True,
        "do_not_merge": True,
        "qc": "Not Cosmo QC. Not approved. Do not merge.",
        "method_default": "static-ambient",
        "camera": "locked",
        "not_used": [
            "orbit",
            "sweep",
            "viewpoint interpolation",
            "optical-flow blend between generated views",
            "subject-pinned pan",
            "night master",
            "finished master with the label bar left on",
            "verbatim re-roll of a failed prompt",
        ],
        "spec": {
            "duration_s": 10.0,
            "width": PHOTO_W,
            "height": PHOTO_H,
            "fps": FPS,
            "frames": FRAMES,
            "format": "4:5",
            "label_bar_px_cropped": BAR_PX,
        },
        "scenes": rows,
    }
    out = ROOT / "evidence/motion/NL-360-rebuild-batch6-2026-10-02.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2) + "\n")
    print("wrote", out)


if __name__ == "__main__":
    main()
