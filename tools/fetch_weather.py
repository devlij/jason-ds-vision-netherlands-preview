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
    ("NL-01-065", "Fort Oranje", "Oranjestad", 17.4829, -62.9865, "America/Kralendijk"),
    ("NL-01-066", "The Bottom", "The Bottom", 17.6262, -63.2490, "America/Kralendijk"),
    ("NL-01-067", "Salt pans", "Bonaire", 12.0930, -68.2800, "America/Kralendijk"),
    ("NL-01-068", "Harbour", "Heusden", 51.7336, 5.1378, "Europe/Amsterdam"),
    ("NL-01-069", "Van Gogh Church", "Nuenen", 51.4777, 5.5532, "Europe/Amsterdam"),
    ("NL-01-070", "Sassenpoort", "Zwolle", 52.5098, 6.0907, "Europe/Amsterdam"),
    ("NL-01-071", "Stadsbrug", "Kampen", 52.5578, 5.9145, "Europe/Amsterdam"),
    ("NL-01-072", "Harbour", "Elburg", 52.4492, 5.8432, "Europe/Amsterdam"),
    ("NL-01-073", "Berkelpoort", "Zutphen", 52.1424, 6.2012, "Europe/Amsterdam"),
    ("NL-01-074", "Sonsbeek Park", "Arnhem", 51.9833, 5.9000, "Europe/Amsterdam"),
    ("NL-01-075", "Valkhof", "Nijmegen", 51.8472, 5.8710, "Europe/Amsterdam"),
    ("NL-01-076", "Vesting", "Naarden", 52.2953, 5.1622, "Europe/Amsterdam"),
    ("NL-01-077", "Muiderslot", "Muiden", 52.3361, 5.0703, "Europe/Amsterdam"),
    ("NL-01-078", "Kasteel de Haar", "Haarzuilens", 52.1214, 4.9868, "Europe/Amsterdam"),
    ("NL-01-079", "Kurhaus", "The Hague", 52.1135, 4.2817, "Europe/Amsterdam"),
    ("NL-01-080", "Oude Kerk", "Delft", 52.0125, 4.3557, "Europe/Amsterdam"),
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
