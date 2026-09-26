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
    ("NL-01-145", "The Quill", "Oranjestad", 17.4830, -62.9860, "America/Kralendijk"),
    ("NL-01-146", "Lac Bay", "Bonaire", 12.1005, -68.2250, "America/Kralendijk"),
    ("NL-01-147", "Windwardside", "Windwardside", 17.6290, -63.2318, "America/Kralendijk"),
    ("NL-01-148", "Poldertoren", "Emmeloord", 52.7100, 5.7480, "Europe/Amsterdam"),
    ("NL-01-149", "Coevorden Castle", "Coevorden", 52.6623, 6.7422, "Europe/Amsterdam"),
    ("NL-01-150", "Dwingeloo telescope", "Dwingeloo", 52.8122, 6.3964, "Europe/Amsterdam"),
    ("NL-01-151", "Hanging kitchens", "Appingedam", 53.3217, 6.8583, "Europe/Amsterdam"),
    ("NL-01-152", "Markt", "Ootmarsum", 52.4078, 6.9012, "Europe/Amsterdam"),
    ("NL-01-153", "Windmills", "Schiedam", 51.9165, 4.3988, "Europe/Amsterdam"),
    ("NL-01-154", "Maeslantkering", "Hoek van Holland", 51.9550, 4.1640, "Europe/Amsterdam"),
    ("NL-01-155", "Magere Brug", "Amsterdam", 52.3637, 4.9024, "Europe/Amsterdam"),
    ("NL-01-156", "De Adriaan", "Haarlem", 52.3818, 4.6415, "Europe/Amsterdam"),
    ("NL-01-157", "Eusebiuskerk", "Arnhem", 51.9790, 5.9100, "Europe/Amsterdam"),
    ("NL-01-158", "Basilica", "Hulst", 51.2830, 4.0500, "Europe/Amsterdam"),
    ("NL-01-159", "Sint Servaasbrug", "Maastricht", 50.8492, 5.6958, "Europe/Amsterdam"),
    ("NL-01-160", "Basilica", "Oudenbosch", 51.5894, 4.5286, "Europe/Amsterdam"),
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
