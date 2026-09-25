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
    ("NL-01-049", "Basilica of Saint Servatius", "Maastricht", 50.8481, 5.6876, "Europe/Amsterdam"),
    ("NL-01-050", "Valkenburg Castle", "Valkenburg", 50.8628, 5.8308, "Europe/Amsterdam"),
    ("NL-01-051", "Abbey square", "Thorn", 51.1617, 5.8419, "Europe/Amsterdam"),
    ("NL-01-052", "Vaalserberg", "Vaals", 50.7545, 6.0208, "Europe/Amsterdam"),
    ("NL-01-053", "Bataviawerf", "Lelystad", 52.5215, 5.4358, "Europe/Amsterdam"),
    ("NL-01-054", "Harbour", "Urk", 52.6616, 5.5928, "Europe/Amsterdam"),
    ("NL-01-055", "Schokland Museum", "Schokland", 52.6406, 5.7759, "Europe/Amsterdam"),
    ("NL-01-056", "Oldehove", "Leeuwarden", 53.2030, 5.7894, "Europe/Amsterdam"),
    ("NL-01-057", "Harbour", "Harlingen", 53.1748, 5.4098, "Europe/Amsterdam"),
    ("NL-01-058", "Eise Eisinga Planetarium", "Franeker", 53.1865, 5.5412, "Europe/Amsterdam"),
    ("NL-01-059", "Waterfront", "Hindeloopen", 52.9428, 5.4015, "Europe/Amsterdam"),
    ("NL-01-060", "Martinitoren", "Groningen", 53.2194, 6.5682, "Europe/Amsterdam"),
    ("NL-01-061", "Vesting Bourtange", "Bourtange", 53.0068, 7.1918, "Europe/Amsterdam"),
    ("NL-01-062", "Hunebed D27", "Borger", 52.9302, 6.7974, "Europe/Amsterdam"),
    ("NL-01-063", "Dwingelderveld", "Dwingeloo", 52.8240, 6.3780, "Europe/Amsterdam"),
    ("NL-01-064", "Waterfront", "Kralendijk", 12.1504, -68.2772, "America/Kralendijk"),
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
