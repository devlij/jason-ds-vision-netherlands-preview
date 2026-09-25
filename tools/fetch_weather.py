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
    ("NL-01-097", "Markiezenhof", "Bergen op Zoom", 51.4948, 4.2876, "Europe/Amsterdam"),
    ("NL-01-098", "Bossche Broek", "'s-Hertogenbosch", 51.6820, 5.3040, "Europe/Amsterdam"),
    ("NL-01-099", "LocHal", "Tilburg", 51.5617, 5.0832, "Europe/Amsterdam"),
    ("NL-01-100", "Helmond Castle", "Helmond", 51.4785, 5.6556, "Europe/Amsterdam"),
    ("NL-01-101", "St. Martinuskerk", "Venlo", 51.3701, 6.1685, "Europe/Amsterdam"),
    ("NL-01-102", "St. Peter's Basilica", "Sittard", 51.0015, 5.8690, "Europe/Amsterdam"),
    ("NL-01-103", "Pancratiuskerk", "Heerlen", 50.8876, 5.9792, "Europe/Amsterdam"),
    ("NL-01-104", "Rolduc Abbey", "Kerkrade", 50.8686, 6.0825, "Europe/Amsterdam"),
    ("NL-01-105", "Boulevard", "Vlissingen", 51.4426, 3.5735, "Europe/Amsterdam"),
    ("NL-01-106", "Lighthouse", "Westkapelle", 51.5292, 3.4473, "Europe/Amsterdam"),
    ("NL-01-107", "Oyster harbour", "Yerseke", 51.4930, 4.0550, "Europe/Amsterdam"),
    ("NL-01-108", "Harbour", "Goes", 51.5088, 3.8885, "Europe/Amsterdam"),
    ("NL-01-109", "Lek bridge", "Culemborg", 51.9606, 5.2133, "Europe/Amsterdam"),
    ("NL-01-110", "Waterfront", "Tiel", 51.8888, 5.4295, "Europe/Amsterdam"),
    ("NL-01-111", "Hotel De Wereld", "Wageningen", 51.9675, 5.6678, "Europe/Amsterdam"),
    ("NL-01-112", "Radio Kootwijk", "Radio Kootwijk", 52.1667, 5.8167, "Europe/Amsterdam"),
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
