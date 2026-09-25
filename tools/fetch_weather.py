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
TZ = ZoneInfo("Europe/Amsterdam")
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
    ("NL-01-017", "Van Gogh Museum", "Amsterdam", 52.3580, 4.8811),
    ("NL-01-018", "Dam Square", "Amsterdam", 52.3731, 4.8922),
    ("NL-01-019", "Anne Frank House", "Amsterdam", 52.3752, 4.8840),
    ("NL-01-020", "Vondelpark", "Amsterdam", 52.3579, 4.8686),
    ("NL-01-021", "NEMO", "Amsterdam", 52.3740, 4.9122),
    ("NL-01-022", "Harbour", "Volendam", 52.4950, 5.0714),
    ("NL-01-023", "Harbour", "Marken", 52.4597, 5.1056),
    ("NL-01-024", "Waag", "Alkmaar", 52.6317, 4.7486),
    ("NL-01-025", "Hoofdtoren", "Hoorn", 52.6383, 5.0594),
    ("NL-01-026", "Zuiderzeemuseum", "Enkhuizen", 52.7075, 5.2980),
    ("NL-01-027", "Markthal", "Rotterdam", 51.9200, 4.4867),
    ("NL-01-028", "Euromast", "Rotterdam", 51.9054, 4.4668),
    ("NL-01-029", "Peace Palace", "The Hague", 52.0865, 4.2958),
    ("NL-01-030", "Scheveningen pier", "The Hague", 52.1155, 4.2785),
    ("NL-01-031", "Markt", "Gouda", 52.0115, 4.7104),
    ("NL-01-032", "Grote Kerk", "Dordrecht", 51.8142, 4.6901),
]


def existing_stamps() -> set[str]:
    stamps = set()
    for path in OUT.glob("NL-*.json"):
        data = json.loads(path.read_text())
        stamps.add(data["retrieval_timestamp"])
    return stamps


def fetch_one(entry_id: str, site: str, city: str, lat: float, lon: float, stamps: set[str]) -> dict:
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,weather_code,cloud_cover,wind_speed_10m,is_day,precipitation",
        "daily": "sunrise,sunset",
        "timezone": "Europe/Amsterdam",
        "forecast_days": 1,
    }
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
    # Gap so this response second cannot collide with the previous scene.
    time.sleep(2.0)
    request_started = datetime.now(TZ)
    req = urllib.request.Request(url, headers={"User-Agent": "jasons-vision-netherlands/1.3"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        body = resp.read()
    retrieval = datetime.now(TZ)
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
            f"{retrieval.strftime('%H:%M:%S')} Europe/Amsterdam"
        ),
        "request_started": request_started.isoformat(timespec="seconds"),
        "model_time": current["time"],
        "model_interval_seconds": current.get("interval", 900),
        "timezone": payload.get("timezone", "Europe/Amsterdam"),
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
            f"{retrieval.strftime('%H:%M')} Europe/Amsterdam"
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
