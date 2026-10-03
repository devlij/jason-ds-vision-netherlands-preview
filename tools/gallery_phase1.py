"""Phase-1 gallery metadata for the Netherlands page.

Spain (``app.js`` in jason-ds-vision-spain-preview) does not store moods on
catalogue records. Each scene is a five-field client tuple:

    [region, "day"|"night", "coastal,mountain,urban,historic", thumbPath, caption]

Filters and the four related-scene thumbnails read that tuple. Related order
is: same region first, then most shared mood tags, then entry id.

The Netherlands catalogue has no mood field. This module derives the same
four ids from catalogue / manifest text, and day/night from the scene's
Open-Meteo ``is_day`` flag. A thumbnail or format control is emitted only
when that master file exists under ``library/world/``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "library" / "world"
TEMPLATE = ROOT / "tools" / "gallery_template.html"
WOTD = ROOT / "tools" / "wotd.json"

MOOD_ORDER = ("coastal", "mountain", "urban", "historic")

# Phrase lists are matched against casefolded catalogue + manifest text.
# Short or ambiguous words use a letter boundary so "sea" does not hit
# "season" and "mill" does not hit "millimetre". Stems such as "kerk" and
# "haven" keep only a start boundary so "Kerkruïne" and "havens" still match.
_START = r"(?<![a-z0-9])"
_BOTH = r"(?<![a-z0-9-])(?:{p})(?![a-z0-9-])"

MOOD_PHRASES: dict[str, tuple[str, ...]] = {
    # Sea, harbour, beach, and coast. Inland canals and city grachten are not
    # coastal; those stay urban and/or historic.
    "coastal": (
        "harbour",
        "harbor",
        "haven",
        "quay",
        "waterfront",
        "beach",
        "strand",
        "lighthouse",
        "vuurtoren",
        "lichtwachter",
        "pier",
        "ferry",
        "salt pan",
        "salt pans",
        "kering",
        "wadden",
        "coast",
        "coastal",
        "bay",
        "sea",
        "shore",
        "lagoon",
        "marina",
        "boulevard",
        "sluis",
        "tidal",
        "kering",
        "afsluitdijk",
        "sea dike",
        "witte pan",
    ),
    # Upland or volcanic relief named in the text. A low inland hill
    # (Vaalserberg) is not mountain. Saba's ridge villages are.
    "mountain": (
        "mountain",
        "volcano",
        "volcanic",
        "crater",
        "summit",
        "mount scenery",
        "ridge village",
        "hell's gate",
        "zion's hill",
        "windwardside",
    ),
    "urban": (
        "square",
        "markt",
        "plein",
        "stadhuis",
        "city hall",
        "town hall",
        "street",
        "station",
        "gracht",
        "urban",
        "city centre",
        "city center",
        "old town",
        "skyline",
        "boulevard",
        "bridge",
        "brug",
        "forum",
    ),
    "historic": (
        "church",
        "kerk",
        "basilica",
        "basiliek",
        "cathedral",
        "kathedraal",
        "abbey",
        "abdij",
        "toren",
        "tower",
        "castle",
        "kasteel",
        "slot",
        "poort",
        "gate",
        "museum",
        "waag",
        "hunebed",
        "fort",
        "vesting",
        "paleis",
        "palace",
        "molen",
        "windmill",
        "mill",
        "monument",
        "burcht",
        "borg",
        "klooster",
        "kapel",
        "begijn",
        "belfort",
        "gothic",
        "medieval",
        "ruïne",
        "ruine",
        "ruin",
        "heritage",
        "havezate",
        "goudkantoor",
    ),
}

# These short tokens false-friend easily. Require a full token boundary.
_BOUNDED = {
    "bay",
    "sea",
    "mill",
    "gate",
    "slot",
    "fort",
    "ruin",
}

# Too broad in running description prose (a bridge pier, a moated island,
# "earlier than on the coast", an inland dike). They count only in the
# subject fields: caption, composition, alt text, and city.
_SUBJECT_ONLY = {
    "pier",
    "quay",
    "coast",
    "coastal",
    "island",
    "eiland",
}

# Distinctive stems that sit inside a longer name (Maeslantkering, Stadsbrug).
_CONTAINS = {"kering", "brug"}

FILE_KEYS = (
    "file_16x9",
    "file_4x5",
    "file_9x16",
    "file_16x9_day",
    "file_4x5_day",
    "file_9x16_day",
)


def _phrase_re(phrase: str) -> re.Pattern[str]:
    escaped = re.escape(phrase)
    if phrase in _CONTAINS:
        return re.compile(escaped)
    if phrase in _BOUNDED:
        return re.compile(_BOTH.format(p=escaped))
    return re.compile(_START + escaped)


_MOOD_RES: dict[str, tuple[re.Pattern[str], ...]] = {
    mood: tuple(_phrase_re(p) for p in phrases) for mood, phrases in MOOD_PHRASES.items()
}


def master_exists(rel: str | None) -> bool:
    if not rel or not isinstance(rel, str):
        return False
    # Reject absolute paths and parent segments; masters live under library/world.
    if rel.startswith("/") or ".." in Path(rel).parts:
        return False
    path = WORLD / rel
    try:
        path.resolve().relative_to(WORLD.resolve())
    except ValueError:
        return False
    return path.is_file()


def is_genuine_daylight(scene: dict) -> bool:
    """True only for a Netherlands genuine-daylight master that exists on disk.

    Derivative daylight (a relight of the night master, no ``provenance`` of
    ``genuine-daylight``) does not qualify. The flag is computed for the page
    payload and is not written back onto the manifest.
    """
    variant = scene.get("daylight_variant")
    if not isinstance(variant, dict) or variant.get("provenance") != "genuine-daylight":
        return False
    return master_exists(scene.get("file_16x9_day"))


def prepare_scene(scene: dict) -> dict | None:
    """Copy a manifest for the page, dropping any master that is not on disk.

    The card is omitted when the 16:9 master is missing. Daylight controls
    require the 16:9 daylight master; a missing daylight file removes the
    daylight keys so the template does not render that button.

    A genuine-daylight 16:9 master sets ``daylight_primary``. The card then
    shows that daylight file by default and keeps the original night master
    behind the nighttime toggle. Other daylight files stay on the sun toggle.
    """
    out = dict(scene)
    for key in FILE_KEYS:
        rel = out.get(key)
        if rel and not master_exists(rel):
            out.pop(key, None)
    if not out.get("file_16x9"):
        return None
    if not out.get("file_16x9_day"):
        out.pop("file_4x5_day", None)
        out.pop("file_9x16_day", None)
    if out.get("file_9x16") and not master_exists(out.get("file_9x16")):
        out.pop("file_9x16", None)
    # Never trust a stale flag from a manifest. Recompute from provenance + file.
    out.pop("daylight_primary", None)
    if is_genuine_daylight(out):
        out["daylight_primary"] = True
    return out


# A clause that denies a feature ("not a lighthouse", "no ferry", "without
# the pier", "are other places") must not donate that feature's mood.
_NEGATED = re.compile(
    r"\b(not|no|n't|without|outside|absent)\b"
    r"|other places|another scene|different scene|different street|than on the coast"
)


def _positive_prose(value: str) -> str:
    kept = []
    for clause in re.split(r"(?<=[,.;!?])\s+", value):
        if _NEGATED.search(clause.casefold()):
            continue
        kept.append(clause)
    return " ".join(kept)


def _normalize(value: str) -> str:
    return value.casefold().replace("\u2019", "'").replace("\u2018", "'")


def _gather(row: dict | None, scene: dict, keys: tuple[str, ...], prose: bool) -> str:
    parts: list[str] = []
    for src in (row or {}, scene):
        for key in keys:
            val = src.get(key)
            if not isinstance(val, str) or not val:
                continue
            parts.append(_positive_prose(val) if prose else val)
    return _normalize("\n".join(parts))


def subject_text(row: dict | None, scene: dict) -> str:
    """Caption, composition, alt text, and city: what the card is of."""
    return _gather(row, scene, ("caption", "city", "composition", "alt_text"), prose=True)


def scene_text(row: dict | None, scene: dict) -> str:
    """Subject text plus description clauses that are not negations.

    Viewpoint is omitted. A quay under the camera does not make the subject coastal.
    """
    subject = subject_text(row, scene)
    description = _gather(row, scene, ("description",), prose=True)
    return subject + "\n" + description


def derive_moods(row: dict | None, scene: dict) -> list[str]:
    """Return Spain's mood ids that the catalogue text supports, in stable order."""
    # An explicit catalogue list wins when a future entry sets one. Unknown
    # ids are dropped so the page cannot grow a fifth mood by accident.
    explicit = (row or {}).get("moods")
    if isinstance(explicit, list) and explicit:
        allowed = set(MOOD_ORDER)
        return [mood for mood in MOOD_ORDER if mood in explicit and mood in allowed]
    subject = subject_text(row, scene)
    prose = scene_text(row, scene)
    found = []
    for mood in MOOD_ORDER:
        phrases = MOOD_PHRASES[mood]
        patterns = _MOOD_RES[mood]
        matched = False
        for phrase, pattern in zip(phrases, patterns):
            haystack = subject if phrase in _SUBJECT_ONLY else prose
            if pattern.search(haystack):
                matched = True
                break
        if matched:
            found.append(mood)
    return found


def time_of_day(entry_id: str, row: dict | None) -> str:
    """``day`` when Open-Meteo ``is_day`` is 1, otherwise ``night``.

    Dusk after sunset (``is_day`` 0, including NL-01-065 and NL-01-066) is
    night. The one-off index patch labeled those two dusk scenes day; the
    generator follows the weather record. If the weather file is missing,
    catalogue ``solar`` text is the fallback.
    """
    path = ROOT / "evidence" / "weather" / f"{entry_id}.json"
    if path.is_file():
        is_day = json.loads(path.read_text()).get("is_day")
        if is_day == 1:
            return "day"
        if is_day == 0:
            return "night"
    solar = ((row or {}).get("solar") or "").casefold()
    if any(phrase in solar for phrase in ("sun still up", "late afternoon", "late day")):
        return "day"
    return "night"


def load_catalogue() -> dict[str, dict]:
    rows = json.loads((ROOT / "tools" / "catalogue.json").read_text())
    return {row["entry_id"]: row for row in rows}


def build_meta(scenes: list[dict], catalogue: dict[str, dict]) -> dict[str, list]:
    """Spain-shaped meta for scenes whose 16:9 master exists.

    Value layout matches Spain: ``[region, day|night, moods, thumb, caption]``.
    ``thumb`` is a site-relative path and is included only after ``master_exists``.
    """
    meta: dict[str, list] = {}
    for scene in scenes:
        entry_id = scene.get("entry_id")
        if not entry_id:
            continue
        prepared = prepare_scene(scene)
        if prepared is None:
            continue
        row = catalogue.get(entry_id)
        moods = derive_moods(row, prepared)
        # Related thumbnails follow the card default. Genuine daylight uses the
        # daylight 16:9; every other card keeps the original master.
        thumb_rel = (
            prepared["file_16x9_day"]
            if prepared.get("daylight_primary") and prepared.get("file_16x9_day")
            else prepared["file_16x9"]
        )
        thumb = f"library/world/{thumb_rel}"
        if not master_exists(thumb_rel):
            continue
        meta[entry_id] = [
            prepared.get("region") or (row or {}).get("region") or "",
            time_of_day(entry_id, row),
            ",".join(moods),
            thumb,
            prepared.get("caption") or (row or {}).get("caption") or entry_id,
        ]
    return meta


# Packs 11 and 27 are not on main. Their 9:16 rework is still in flight.
# The gallery must not invent daylight primaries for these twenty scenes.
HELD_SCENE_IDS = {f"NL-01-{n:03d}" for n in list(range(119, 129)) + list(range(279, 289))}


def collect_page(scenes: list[dict]) -> tuple[list[dict], dict[str, list]]:
    catalogue = load_catalogue()
    page_scenes: list[dict] = []
    for scene in scenes:
        prepared = prepare_scene(scene)
        if prepared is None:
            print("skip gallery card, missing 16:9 master", scene.get("entry_id"))
            continue
        page_scenes.append(prepared)
    meta = build_meta(page_scenes, catalogue)
    _check_meta(meta)
    return page_scenes, meta


def gallery_documents(scenes: list[dict]) -> tuple[str, dict]:
    """Return the gallery HTML and the ``data.json`` document from one payload."""
    page_scenes, meta = collect_page(scenes)
    template = TEMPLATE.read_text()
    wotd = json.loads(WOTD.read_text())
    payload = json.dumps(page_scenes, ensure_ascii=False).replace("<", "\\u003c")
    meta_payload = json.dumps(meta, ensure_ascii=False).replace("<", "\\u003c")
    wotd_payload = json.dumps(wotd, ensure_ascii=False).replace("<", "\\u003c")
    html = (
        template.replace("__SCENES__", payload)
        .replace("__NL_META__", meta_payload)
        .replace("__WOTD_JSON__", wotd_payload)
    )
    assert_phase1(html, meta)
    _assert_daylight_law(page_scenes, html)
    genuine = [s for s in page_scenes if s.get("daylight_primary") is True]
    derivative = [s for s in page_scenes if s.get("file_16x9_day") and s.get("daylight_primary") is not True]
    night_only = [s for s in page_scenes if not s.get("file_16x9_day")]
    document = {
        "country": "Netherlands",
        "scene_count": len(page_scenes),
        "daylight_primary_count": len(genuine),
        "night_toggle_count": len(genuine),
        "derivative_daylight_count": len(derivative),
        "night_only_count": len(night_only),
        "scenes": page_scenes,
    }
    return html, document


def render_gallery(scenes: list[dict]) -> str:
    html, _document = gallery_documents(scenes)
    return html


def _assert_daylight_law(page_scenes: list[dict], html: str) -> None:
    """Netherlands daylight-primary law. Does not approve anything."""
    genuine = [s for s in page_scenes if s.get("daylight_primary") is True]
    if html.count('"daylight_primary": true') != len(genuine):
        raise SystemExit("daylight_primary flags in the page do not match the payload")
    for scene in genuine:
        entry_id = scene.get("entry_id")
        variant = scene.get("daylight_variant") or {}
        if variant.get("provenance") != "genuine-daylight":
            raise SystemExit(f"{entry_id} is daylight-primary without genuine-daylight provenance")
        if entry_id in HELD_SCENE_IDS:
            raise SystemExit(f"held scene {entry_id} must stay on its existing card")
        if not master_exists(scene.get("file_16x9_day")):
            raise SystemExit(f"{entry_id} daylight primary points at a missing master")
    for scene in page_scenes:
        entry_id = scene.get("entry_id")
        if entry_id not in HELD_SCENE_IDS:
            continue
        if scene.get("daylight_primary") or scene.get("file_16x9_day"):
            raise SystemExit(f"held scene {entry_id} gained a daylight card")
    if "night-tab" not in html or "nl-gallery-format" not in html:
        raise SystemExit("gallery page is missing the nighttime toggle or format persistence")


def _check_meta(meta: dict[str, list]) -> None:
    for entry_id, row in meta.items():
        if len(row) != 5:
            raise SystemExit(f"phase-1 meta for {entry_id} is not a 5-field tuple")
        if row[1] not in ("day", "night"):
            raise SystemExit(f"phase-1 time of day for {entry_id} is {row[1]!r}")
        moods = [part for part in row[2].split(",") if part]
        if any(mood not in MOOD_ORDER for mood in moods):
            raise SystemExit(f"phase-1 mood outside Spain's set for {entry_id}: {row[2]!r}")
        if not master_exists(row[3].removeprefix("library/world/")):
            raise SystemExit(f"phase-1 thumbnail missing on disk for {entry_id}: {row[3]}")


def assert_phase1(html: str, meta: dict[str, list]) -> None:
    """Fail the publish if a rebuild would drop Phase-1 or the live chrome."""
    required = (
        'id="f-daynight"',
        'id="f-mood"',
        "Coastal",
        "Mountain",
        "Urban",
        "Historic",
        'id="result-count"',
        'id="clear"',
        "f-daynight').value = ''",
        "f-mood').value = ''",
        "card.id = s.entry_id",
        "function relatedFor",
        "Copy link",
        "Copied",
        "G-PDJ4WSS725",
        "https://spain.jdvision.org/",
        'id="wotd"',
        "lb-play",
        "Play slideshow",
        "approval_status",
        "flag-band",
        "format_9x16_approval_status",
        "phase1Enhance",
    )
    missing = [token for token in required if token not in html]
    if missing:
        raise SystemExit("gallery page is missing Phase-1 or chrome: " + ", ".join(missing))
    if "__SCENES__" in html or "__NL_META__" in html or "__WOTD_JSON__" in html:
        raise SystemExit("gallery template placeholders were not filled")
    nav_start = html.find('<nav class="country-switch"')
    nav_end = html.find("</nav>", nav_start)
    nav = html[nav_start:nav_end] if nav_start >= 0 else ""
    if nav.count(">Netherlands<") != 1 or nav.count('aria-current="page"') != 1:
        raise SystemExit("country switcher must mark Netherlands once as the current page")
    if "jason-ds-vision-netherlands-preview" in nav or "https://netherlands.jdvision.org/" in nav:
        raise SystemExit("country switcher must not link this page to itself")
    order = (
        "Germany",
        "Italy",
        "France",
        "Spain",
        "Greece",
        "Norway",
        "Denmark",
        "Netherlands",
        "Finland",
        "Sweden",
        "Ireland",
        "United Kingdom",
        "Switzerland",
    )
    positions = [nav.find(f">{name}<") for name in order]
    if any(pos < 0 for pos in positions) or positions != sorted(positions):
        raise SystemExit("country switcher is missing the shared gallery order")
    if "Belgium" in nav or "Austria" in nav:
        raise SystemExit("country switcher includes a gallery that is not live")
    if "home-link" not in nav or "https://jdvision.org/" not in nav:
        raise SystemExit("country switcher is missing Home")
    current = nav[nav.find('aria-current="page"') : nav.find('aria-current="page"') + 500]
    if ">Netherlands<" not in current or "<a " in current.split(">Netherlands<", 1)[0]:
        raise SystemExit("Netherlands must be the current page, not a link")
    for url in (
        "https://norway.jdvision.org/",
        "https://denmark.jdvision.org/",
        "https://devlij.github.io/jason-ds-vision-finland-preview/",
        "https://sweden.jdvision.org/",
        "https://ireland.jdvision.org/",
        "https://uk.jdvision.org/",
        "https://devlij.github.io/jason-ds-vision-switzerland-preview/",
    ):
        if url not in nav:
            raise SystemExit(f"country switcher missing {url}")
    if "linear-gradient(#fff,#fff) center/45% 22%" not in html:
        raise SystemExit("Swiss flag chip is missing the white cross")
    if not meta:
        raise SystemExit("phase-1 meta is empty")
    # Every meta thumbnail must be a real master. Controls for other formats
    # are gated in the template by the file fields prepare_scene left in place.
    for entry_id, row in meta.items():
        if entry_id not in html:
            raise SystemExit(f"{entry_id} missing from generated page")
        if row[3] not in html:
            raise SystemExit(f"thumbnail for {entry_id} missing from generated page")
