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
    ("NL-01-081", "Ferry terminal", "Holwerd", 53.3948, 5.8800, "Europe/Amsterdam"),
    ("NL-01-082", "Harbour", "Zoutkamp", 53.3402, 6.3030, "Europe/Amsterdam"),
    ("NL-01-083", "Drents Museum", "Assen", 52.9932, 6.5647, "Europe/Amsterdam"),
    ("NL-01-084", "Amerongen Castle", "Amerongen", 51.9953, 5.4583, "Europe/Amsterdam"),
    ("NL-01-085", "Slot Loevestein", "Poederoijen", 51.8164, 5.0214, "Europe/Amsterdam"),
    ("NL-01-086", "Linge harbour", "Gorinchem", 51.8290, 4.9755, "Europe/Amsterdam"),
    ("NL-01-087", "Harbour", "Brielle", 51.9040, 4.1655, "Europe/Amsterdam"),
    ("NL-01-088", "Beach", "Hoek van Holland", 51.9890, 4.1160, "Europe/Amsterdam"),
    ("NL-01-089", "Lighthouse", "Katwijk", 52.2068, 4.3962, "Europe/Amsterdam"),
    ("NL-01-090", "Lighthouse", "Noordwijk", 52.2482, 4.4338, "Europe/Amsterdam"),
    ("NL-01-091", "Speeltoren", "Edam", 52.5124, 5.0492, "Europe/Amsterdam"),
    ("NL-01-092", "Harbour", "Monnickendam", 52.4592, 5.0360, "Europe/Amsterdam"),
    ("NL-01-093", "Botter harbour", "Spakenburg", 52.2512, 5.3750, "Europe/Amsterdam"),
    ("NL-01-094", "Vischpoort", "Harderwijk", 52.3510, 5.6170, "Europe/Amsterdam"),
    ("NL-01-095", "Harbour", "Doesburg", 52.0162, 6.1295, "Europe/Amsterdam"),
    ("NL-01-096", "Munsterkerk", "Roermond", 51.1936, 5.9886, "Europe/Amsterdam"),
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
