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
    ("NL-01-161", "Waterpoort", "Sneek", 53.0292, 5.6592, "Europe/Amsterdam"),
    ("NL-01-162", "Woudagemaal", "Lemmer", 52.8456, 5.6788, "Europe/Amsterdam"),
    ("NL-01-163", "Menkemaborg", "Uithuizen", 53.4058, 6.6728, "Europe/Amsterdam"),
    ("NL-01-164", "Groninger Museum", "Groningen", 53.2123, 6.5660, "Europe/Amsterdam"),
    ("NL-01-165", "Brink", "Orvelte", 52.8433, 6.6594, "Europe/Amsterdam"),
    ("NL-01-166", "Grote Kerk", "Enschede", 52.2204, 6.8958, "Europe/Amsterdam"),
    ("NL-01-167", "Cuneratoren", "Rhenen", 51.9570, 5.5643, "Europe/Amsterdam"),
    ("NL-01-168", "Grote Kerk", "Breda", 51.5886, 4.7753, "Europe/Amsterdam"),
    ("NL-01-169", "Laurenskerk", "Rotterdam", 51.9216, 4.4856, "Europe/Amsterdam"),
    ("NL-01-170", "Delfshaven", "Rotterdam", 51.9082, 4.4478, "Europe/Amsterdam"),
    ("NL-01-171", "Stadhuis", "Middelburg", 51.4983, 3.6105, "Europe/Amsterdam"),
    ("NL-01-172", "Slot Haamstede", "Haamstede", 51.6979, 3.7422, "Europe/Amsterdam"),
    ("NL-01-173", "Lighthouse", "Egmond aan Zee", 52.6191, 4.6217, "Europe/Amsterdam"),
    ("NL-01-174", "Kasteel Hoensbroek", "Hoensbroek", 50.9202, 5.9258, "Europe/Amsterdam"),
    ("NL-01-175", "Huis Bergh", "'s-Heerenberg", 51.8744, 6.2458, "Europe/Amsterdam"),
    ("NL-01-176", "Willemstoren", "Bonaire", 12.0333, -68.2333, "America/Kralendijk"),
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
    body = None
    last_err: Exception | None = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                body = resp.read()
            break
        except Exception as err:
            last_err = err
            time.sleep(2.0)
    if body is None:
        raise SystemExit(f"{entry_id} Open-Meteo failed: {last_err}")
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
