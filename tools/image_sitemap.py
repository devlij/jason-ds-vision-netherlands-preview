#!/usr/bin/env python3
"""Write image-sitemap.xml from live Netherlands scene manifests.

Approved scenes only. Each scene is one page URL (canonical gallery URL plus
the copy-link fragment). Each approved scene contributes the 16:9 and 4:5
masters only. 9:16 stays off this sitemap even when the file is on disk:
those frames are Candidate and gated in the gallery.

Regenerate after an approval change. A scene that is no longer Approved
drops out because this reads approval_status from the manifests, not from
a handwritten list.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "manifests"
WORLD = ROOT / "library" / "world"
OUT = ROOT / "image-sitemap.xml"
ROBOTS = ROOT / "robots.txt"
TEMPLATE = ROOT / "tools" / "gallery_template.html"

# Confirmed from robots.txt, the gallery canonical link, and tools/publish.py.
# This repo has no CNAME; the live host is the GitHub Pages project site.
SITE = "https://devlij.github.io/jason-ds-vision-netherlands-preview/"

# Aspect ratios that may be listed for an Approved scene, in sitemap order.
# 9:16 is intentionally absent.
FORMATS = (
    ("16:9", "file_16x9", "format_16x9_approval_status"),
    ("4:5", "file_4x5", "format_4x5_approval_status"),
)

# A path or URL that mentions a portrait master is a hard failure.
_FORBIDDEN = ("9x16", "9:16", "-9-16")


def site_name(caption: str, city: str) -> str:
    """Landmark portion of the caption. City stays in the title separately."""
    suffix = f", {city}" if city else ""
    if suffix and caption.endswith(suffix) and len(caption) > len(suffix):
        return caption[: -len(suffix)]
    return caption


def image_title(caption: str, city: str) -> str:
    """`site, City` — the landmark and the city field."""
    site = site_name(caption, city)
    if city:
        return f"{site}, {city}"
    return site


def image_alt(caption: str, city: str) -> str:
    """`{caption} — {site}, {City}` using an em dash, matching the gallery."""
    return f"{caption} — {image_title(caption, city)}"


def geo_location(city: str, country: str) -> str:
    return f"{city}, {country}"


def page_url(entry_id: str) -> str:
    """Canonical gallery URL plus the copy-link fragment (`#NL-01-001`)."""
    return f"{SITE}#{entry_id}"


def image_url(rel: str) -> str:
    """Absolute URL of a master under library/world. Spaces and non-ASCII are encoded."""
    return SITE + "library/world/" + quote(rel, safe="/")


def _master_on_disk(rel: str) -> bool:
    if not rel or rel.startswith("/") or ".." in Path(rel).parts:
        return False
    path = WORLD / rel
    try:
        path.resolve().relative_to(WORLD.resolve())
    except ValueError:
        return False
    return path.is_file()


def _format_allowed(scene: dict, status_key: str) -> bool:
    """Scene approval covers 16:9 and 4:5 unless a format status says otherwise."""
    status = scene.get(status_key)
    if status is None or status == "":
        return True
    return status == "Approved"


def _forbidden(value: str) -> bool:
    lowered = value.casefold()
    return any(token.casefold() in lowered for token in _FORBIDDEN)


def approved_entries() -> list[dict]:
    """Approved scenes in entry-id order, each with the formats to list."""
    rows = []
    for path in sorted(MANIFESTS.glob("NL-*.json")):
        scene = json.loads(path.read_text())
        if scene.get("approval_status") != "Approved":
            continue
        entry_id = scene.get("entry_id") or ""
        caption = scene.get("caption") or ""
        city = scene.get("city") or ""
        country = scene.get("country") or ""
        images = []
        for label, file_key, status_key in FORMATS:
            rel = scene.get(file_key) or ""
            if not rel or not _format_allowed(scene, status_key):
                continue
            if _forbidden(rel) or _forbidden(label):
                continue
            if not _master_on_disk(rel):
                continue
            images.append(
                {
                    "format": label,
                    "rel": rel,
                    "loc": image_url(rel),
                    "caption": caption,
                    "title": image_title(caption, city),
                    "geo_location": geo_location(city, country),
                }
            )
        if not images:
            continue
        rows.append(
            {
                "entry_id": entry_id,
                "loc": page_url(entry_id),
                "images": images,
            }
        )
    return rows


def render_xml(entries: list[dict]) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
        '        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">',
    ]
    for entry in entries:
        lines.append("  <url>")
        lines.append(f"    <loc>{escape(entry['loc'])}</loc>")
        for image in entry["images"]:
            lines.append("    <image:image>")
            lines.append(f"      <image:loc>{escape(image['loc'])}</image:loc>")
            lines.append(f"      <image:caption>{escape(image['caption'])}</image:caption>")
            lines.append(f"      <image:title>{escape(image['title'])}</image:title>")
            lines.append(
                f"      <image:geo_location>{escape(image['geo_location'])}</image:geo_location>"
            )
            lines.append("    </image:image>")
        lines.append("  </url>")
    lines.append("</urlset>")
    lines.append("")
    return "\n".join(lines)


def confirm_canonical() -> None:
    """Refuse to write if robots.txt and the gallery canonical disagree with SITE."""
    robots = ROBOTS.read_text()
    template = TEMPLATE.read_text()
    expected_page = SITE
    expected_sitemap = SITE + "sitemap.xml"
    if f'href="{expected_page}"' not in template and f"href='{expected_page}'" not in template:
        raise SystemExit(f"gallery canonical is not {expected_page}")
    if expected_sitemap not in robots:
        raise SystemExit(f"robots.txt does not list {expected_sitemap}")
    if (ROOT / "CNAME").exists():
        raise SystemExit("CNAME is present; confirm the live host before writing the image sitemap")


def validate_xml(text: str, entries: list[dict]) -> dict:
    """Parse the sitemap and return counts. Raise if a 9:16 URL or a bad entry got in."""
    import xml.etree.ElementTree as ET

    # Scan the whole document so a comment or a filename cannot hide a portrait master.
    if any(token in text for token in ("9x16", "9:16", "-9-16")):
        raise SystemExit("image sitemap lists a 9:16 image")
    root = ET.fromstring(text)
    ns = {
        "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
        "image": "http://www.google.com/schemas/sitemap-image/1.1",
    }
    urls = root.findall("sm:url", ns)
    formats = {"16:9": 0, "4:5": 0}
    image_total = 0
    for url in urls:
        loc = url.findtext("sm:loc", default="", namespaces=ns)
        if not loc.startswith(SITE) or "#" not in loc:
            raise SystemExit(f"page loc is not canonical plus fragment: {loc}")
        images = url.findall("image:image", ns)
        if not images:
            raise SystemExit(f"url has no images: {loc}")
        for image in images:
            image_loc = image.findtext("image:loc", default="", namespaces=ns)
            if not image_loc.startswith(SITE):
                raise SystemExit(f"image loc is not absolute: {image_loc}")
            if _forbidden(image_loc):
                raise SystemExit(f"forbidden format in image loc: {image_loc}")
            if "daylight" in image_loc:
                raise SystemExit(f"daylight variant listed: {image_loc}")
            caption = image.findtext("image:caption", default="", namespaces=ns)
            title = image.findtext("image:title", default="", namespaces=ns)
            geo = image.findtext("image:geo_location", default="", namespaces=ns)
            if not caption or not title or not geo:
                raise SystemExit(f"image missing caption, title, or geo: {image_loc}")
            if image_loc.endswith("-16x9.png"):
                formats["16:9"] += 1
            elif image_loc.endswith("-4x5.png"):
                formats["4:5"] += 1
            else:
                raise SystemExit(f"image is not a 16:9 or 4:5 master: {image_loc}")
            image_total += 1
    if len(urls) != len(entries):
        raise SystemExit("url count does not match approved entries")
    return {"scenes": len(urls), "images": image_total, "formats": formats}


def write_image_sitemap() -> dict:
    confirm_canonical()
    entries = approved_entries()
    text = render_xml(entries)
    stats = validate_xml(text, entries)
    OUT.write_text(text)
    return stats


def main() -> None:
    stats = write_image_sitemap()
    formats = stats["formats"]
    print(
        f"image-sitemap {stats['scenes']} scenes, "
        f"16:9 {formats['16:9']}, 4:5 {formats['4:5']}, 9:16 0, "
        f"images {stats['images']}"
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        print(f"image sitemap failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
