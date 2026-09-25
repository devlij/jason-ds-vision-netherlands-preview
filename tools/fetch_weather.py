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
    ("NL-01-129", "Teylers Museum", "Haarlem", 52.3804, 4.6402, "Europe/Amsterdam"),
    ("NL-01-130", "Centraal Station", "Amsterdam", 52.3799, 4.9003, "Europe/Amsterdam"),
    ("NL-01-131", "Overhoeks tower", "Amsterdam", 52.3841, 4.9022, "Europe/Amsterdam"),
    ("NL-01-132", "Scheepvaartmuseum", "Amsterdam", 52.3716, 4.9148, "Europe/Amsterdam"),
    ("NL-01-133", "Hotel New York", "Rotterdam", 51.9042, 4.4847, "Europe/Amsterdam"),
    ("NL-01-134", "De Rotterdam", "Rotterdam", 51.9066, 4.4873, "Europe/Amsterdam"),
    ("NL-01-135", "Kunstmuseum", "The Hague", 52.0880, 4.2806, "Europe/Amsterdam"),
    ("NL-01-136", "Paleis Noordeinde", "The Hague", 52.0804, 4.3069, "Europe/Amsterdam"),
    ("NL-01-137", "Burcht", "Leiden", 52.1588, 4.4925, "Europe/Amsterdam"),
    ("NL-01-138", "Oostpoort", "Delft", 52.0111, 4.3681, "Europe/Amsterdam"),
    ("NL-01-139", "Huis Van Gijn", "Dordrecht", 51.8156, 4.6672, "Europe/Amsterdam"),
    ("NL-01-140", "Domplein", "Utrecht", 52.0908, 5.1216, "Europe/Amsterdam"),
    ("NL-01-141", "Mastbos", "Breda", 51.5455, 4.7760, "Europe/Amsterdam"),
    ("NL-01-142", "Lichttoren", "Eindhoven", 51.4406, 5.4788, "Europe/Amsterdam"),
    ("NL-01-143", "Helpoort", "Maastricht", 50.8436, 5.6922, "Europe/Amsterdam"),
    ("NL-01-144", "Forum", "Groningen", 53.2192, 6.5680, "Europe/Amsterdam"),
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
