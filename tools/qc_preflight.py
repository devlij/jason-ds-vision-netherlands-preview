#!/usr/bin/env python3
"""QC pre-flight for the Netherlands starter. Exits non-zero on any failure."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from composite_masters import (
    COMMENT,
    COPYRIGHT,
    DESCRIPTION,
    SOFTWARE,
    TITLE,
    read_text_chunks,
)

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = [
    "real-time conditions",
    "photograph of",
    "captured on",
]


def main() -> None:
    errors: list[str] = []
    approvals = sorted((ROOT / "approvals").glob("NL-*.md"))
    manifests = sorted((ROOT / "manifests").glob("NL-*.json"))
    if len(approvals) != 288 or len(manifests) != 288:
        errors.append(f"expected 288 notes, found approvals={len(approvals)} manifests={len(manifests)}")
    stamps = []
    for path in approvals:
        text = path.read_text()
        if "approval_status: Candidate" not in text:
            errors.append(f"{path.name} not Candidate")
        if re.search(r"approval_status:\s*Approved", text):
            errors.append(f"{path.name} self-approved")
        low = text.lower()
        for phrase in FORBIDDEN:
            if phrase in low:
                errors.append(f"{path.name} contains {phrase!r}")
        if re.search(r"\bobserved\b", low):
            errors.append(f"{path.name} contains 'observed'")
        if "verified on-site" in low and "not a verified on-site observation" not in low:
            errors.append(f"{path.name} claims verified on-site")
        if "not a verified on-site observation" not in text:
            errors.append(f"{path.name} missing required model-data wording")
        if "Model data from Open-Meteo, retrieved" not in text:
            errors.append(f"{path.name} missing retrieval wording")
        m = re.search(
            r"Retrieval timestamp \(unique to the second\):\**\s*(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2})",
            text,
        )
        if not m:
            errors.append(f"{path.name} missing retrieval timestamp")
        else:
            stamps.append(m.group(1))
        sm = re.search(
            r"Scenario: (\d+ \w+ \d+) · (\d{2}):(\d{2}) (Europe/Amsterdam|America/Kralendijk)",
            text,
        )
        if not sm:
            errors.append(f"{path.name} scenario label missing")
        elif m:
            # retrieval 2026-09-25T18:26:37+02:00
            hour = m.group(1)[11:13]
            if sm.group(2) != hour:
                errors.append(f"{path.name} scenario hour {sm.group(2)} outside retrieval hour {hour}")
        for label, digest_line in (("16:9", "SHA-256 16:9"), ("4:5", "SHA-256 4:5")):
            dm = re.search(rf"{re.escape(digest_line)}: `([0-9a-f]{{64}})`", text)
            if not dm:
                errors.append(f"{path.name} missing {digest_line}")

    if len(stamps) != len(set(stamps)):
        errors.append("retrieval timestamps are not unique to the second")
    if any(len(s) < 19 for s in stamps):
        errors.append("a retrieval timestamp is missing seconds")

    for path in manifests:
        data = json.loads(path.read_text())
        for key in (
            "entry_id",
            "country",
            "region",
            "city",
            "caption",
            "scenario_label",
            "composition",
            "description",
            "alt_text",
            "file_16x9",
            "file_4x5",
            "license_badge",
            "license_anchor",
        ):
            if key not in data or not data[key]:
                errors.append(f"{path.name} missing {key}")
        if data.get("country") != "Netherlands":
            errors.append(f"{path.name} country")
        if "Scenario:" in data.get("scenario_label", ""):
            errors.append(f"{path.name} scenario_label should not repeat the Scenario prefix")
        label_bar = bool(data.get("file_9x16"))
        legacy = {"file_16x9": (1920, 1080), "file_4x5": (864, 1080)}
        labelled = {
            "file_16x9": (1920, 1270),
            "file_4x5": (864, 1270),
            "file_9x16": (1080, 2110),
        }
        photo_h = {"file_16x9": 1080, "file_4x5": 1080, "file_9x16": 1920}
        kinds = ["file_16x9", "file_4x5"] + (["file_9x16"] if label_bar else [])
        sizes = labelled if label_bar else legacy
        for kind in kinds:
            img_path = ROOT / "library" / "world" / data[kind]
            if not img_path.exists():
                errors.append(f"missing {img_path}")
                continue
            with Image.open(img_path) as im:
                if im.size != sizes[kind]:
                    errors.append(f"{img_path.name} size {im.size}")
                elif label_bar:
                    if im.getpixel((2, im.size[1] - 1))[:3] != (14, 14, 18):
                        errors.append(f"{img_path.name} label bar is not #0e0e12")
                    if im.getpixel((2, photo_h[kind]))[:3] != (228, 228, 234):
                        errors.append(f"{img_path.name} missing 2px hairline")
            chunks = read_text_chunks(img_path)
            expected = {
                "Title": ("iTXt", TITLE),
                "Description": ("tEXt", DESCRIPTION),
                "Copyright": ("iTXt", COPYRIGHT),
                "Software": ("tEXt", SOFTWARE),
                "Comment": ("tEXt", COMMENT),
            }
            for key, val in expected.items():
                if chunks.get(key) != val:
                    errors.append(f"{img_path.name} chunk {key} {chunks.get(key)!r}")
        # sha match
        note = (ROOT / "approvals" / f"{data['entry_id']}.md").read_text()
        import hashlib

        sha_rows = [("16:9", data["file_16x9"]), ("4:5", data["file_4x5"])]
        if label_bar:
            sha_rows.append(("9:16", data["file_9x16"]))
        for label, rel in sha_rows:
            digest = hashlib.sha256((ROOT / "library" / "world" / rel).read_bytes()).hexdigest()
            if digest not in note:
                errors.append(f"{data['entry_id']} sha {label} not in approval")

    index = (ROOT / "index.html").read_text()
    for needle in (
        "G-PDJ4WSS725",
        'rel="canonical"',
        "getAttribute(\"data-src-45\")",
        "getAttribute(\"data-src-16\")",
        "getAttribute('data-src-45')",
        "getAttribute('data-src-16')",
        "lbFormat",
        "flag-band",
        "#AE1C28",
        "#21468B",
        "#e8722a",
        "spain.jdvision.org",
        "jason-ds-vision-denmark-preview",
        "jason-ds-vision-norway-preview",
        "jason-ds-vision-switzerland-preview",
        "germany.jdvision.org",
        "italy.jdvision.org",
        "france.jdvision.org",
        "greece.jdvision.org",
        "application/ld+json",
        "twitter:card",
    ):
        if needle not in index:
            errors.append(f"index missing {needle}")
    if "dataset.src45" in index or "dataset.src16" in index:
        errors.append("index uses camelCase dataset")
    for n in range(1, 289):
        token = f"NL-01-{n:03d}"
        if token not in index:
            errors.append(f"index missing {token}")
    for n in range(1, 11):
        approved = json.loads((ROOT / "manifests" / f"NL-01-{n:03d}.json").read_text())
        if approved.get("approval_status") != "Approved":
            errors.append(f"NL-01-{n:03d} lost Cosmo approval_status")
        if f'"entry_id": "NL-01-{n:03d}"' not in index or '"approval_status": "Approved"' not in index:
            errors.append("index missing an Approved scene")
    if index.count('"file_16x9_day"') != 10:
        errors.append(f"expected 10 daylight masters in the gallery, found {index.count(chr(34)+'file_16x9_day'+chr(34))}")
    if "View image" in index:
        errors.append("index still has a View image control over the artwork")
    if "position: absolute; top: 1.05rem; left: 1.05rem" in index:
        errors.append("format tabs still overlay the artwork")
    for path in manifests:
        data = json.loads(path.read_text())
        rel = data.get("file_9x16")
        if rel and rel not in index:
            errors.append(f"index missing {rel}")

    if errors:
        print("QC FAIL")
        for err in errors:
            print(" -", err)
        raise SystemExit(1)
    print(f"QC PASS {len(manifests)} scenes, {len(set(stamps))} unique retrievals")


if __name__ == "__main__":
    main()
