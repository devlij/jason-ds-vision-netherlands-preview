#!/usr/bin/env python3
"""One fresh Open-Meteo retrieval per scene. Never batch-share a timestamp."""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence" / "weather"
MONTHS = [
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]

SCENES = [
    ("NL-01-113", "Waddenhaven", "Nes", 53.4374921, 5.7755243, "Europe/Amsterdam"),
    ("NL-01-114", "Brandaris", "West-Terschelling", 53.3603213, 5.2142392, "Europe/Amsterdam"),
    ("NL-01-115", "Veerdam", "Oost-Vlieland", 53.2963601, 5.0753435, "Europe/Amsterdam"),
    ("NL-01-116", "Noordertoren", "Schiermonnikoog", 53.4868377, 6.1465305, "Europe/Amsterdam"),
    ("NL-01-117", "Harbour", "Den Oever", 52.9297180, 5.0296561, "Europe/Amsterdam"),
    ("NL-01-118", "Vlietermonument", "Afsluitdijk", 52.9689621, 5.1089810, "Europe/Amsterdam"),
    ("NL-01-119", "Drommedaris", "Enkhuizen", 52.7007438, 5.2929862, "Europe/Amsterdam"),
    ("NL-01-120", "Radboud Castle", "Medemblik", 52.7724319, 5.1131257, "Europe/Amsterdam"),
    ("NL-01-121", "Kaasmarkt", "Purmerend", 52.5097279, 4.9459736, "Europe/Amsterdam"),
    ("NL-01-122", "Lange Vechtbrug", "Weesp", 52.3071340, 5.0450156, "Europe/Amsterdam"),
    ("NL-01-123", "Nijenrode Castle", "Breukelen", 52.1639837, 5.0093589, "Europe/Amsterdam"),
    ("NL-01-124", "Woerden Castle", "Woerden", 52.0851688, 4.8878214, "Europe/Amsterdam"),
    ("NL-01-125", "Waag", "Gouda", 52.0123264, 4.7108844, "Europe/Amsterdam"),
    ("NL-01-126", "Hoge Molen", "Nieuw-Lekkerland", 51.8858428, 4.6490561, "Europe/Amsterdam"),
    ("NL-01-127", "Waag", "Schoonhoven", 51.9467115, 4.8516204, "Europe/Amsterdam"),
    ("NL-01-128", "Grote Kerk", "Vianen", 51.9924001, 5.0934907, "Europe/Amsterdam"),
]


def existing_stamps() -> set[str]:
    stamps = set()
    for path in OUT.glob("NL-*.json"):
        data = json.loads(path.read_text())
        stamps.add(data["retrieval_timestamp"])
    return stamps


def fetch_one(
    entry_id: str,
    site: str,
    city: str,
    lat: float,
    lon: float,
    tz_name: str,
    stamps: set[str],
) -> dict:
    tz = ZoneInfo(tz_name)
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,weather_code,cloud_cover,wind_speed_10m,is_day,precipitation",
        "daily": "sunrise,sunset",
        "timezone": tz_name,
        "forecast_days": 1,
    }
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
    # Gap so this response second cannot collide with the previous scene.
    time.sleep(2.0)
    request_started = datetime.now(tz)
    req = urllib.request.Request(url, headers={"User-Agent": "jasons-vision-netherlands/1.3"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        body = resp.read()
    retrieval = datetime.now(tz)
    stamp = retrieval.isoformat(timespec="seconds")
    if stamp in stamps:
        raise SystemExit(f"{entry_id} retrieval second collided: {stamp}")
    payload = json.loads(body)
    current = payload["current"]
    daily = payload["daily"]
    record = {
        "entry_id": entry_id,
        "site": site,
        "city": city,
        "latitude": lat,
        "longitude": lon,
        "provider": "Open-Meteo",
        "retrieval_timestamp": stamp,
        "retrieval_display": (
            f"{retrieval.day} {MONTHS[retrieval.month]} {retrieval.year} "
            f"{retrieval.strftime('%H:%M:%S')} {tz_name}"
        ),
        "request_started": request_started.isoformat(timespec="seconds"),
        "model_time": current["time"],
        "model_interval_seconds": current.get("interval", 900),
        "timezone": payload.get("timezone", tz_name),
        "temperature_2m": current["temperature_2m"],
        "weather_code": current["weather_code"],
        "cloud_cover": current["cloud_cover"],
        "wind_speed_10m": current["wind_speed_10m"],
        "is_day": current["is_day"],
        "precipitation": current["precipitation"],
        "sunrise": daily["sunrise"][0],
        "sunset": daily["sunset"][0],
        "model_valid_hour_start": retrieval.strftime("%Y-%m-%dT%H:00"),
        "scenario_label": (
            f"{retrieval.day} {MONTHS[retrieval.month]} {retrieval.year} · "
            f"{retrieval.strftime('%H:%M')} {tz_name}"
        ),
    }
    (OUT / f"{entry_id}.json").write_text(json.dumps(record, indent=2) + "\n")
    stamps.add(stamp)
    print(
        entry_id,
        stamp,
        "code",
        record["weather_code"],
        "cloud",
        record["cloud_cover"],
        "temp",
        record["temperature_2m"],
        "day",
        record["is_day"],
        "precip",
        record["precipitation"],
        "wind",
        record["wind_speed_10m"],
        "scenario",
        record["scenario_label"],
    )
    return record


def main() -> None:
    stamps = existing_stamps()
    for row in SCENES:
        if (OUT / f"{row[0]}.json").exists():
            print(f"keep {row[0]}")
            continue
        fetch_one(*row, stamps)


if __name__ == "__main__":
    main()
