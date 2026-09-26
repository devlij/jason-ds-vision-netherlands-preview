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
    ("NL-01-225", "Waterloopbos", "Marknesse", 52.67619, 5.91683, "Europe/Amsterdam"),
    ("NL-01-226", "Marker Wadden", "Lelystad", 52.58940, 5.37640, "Europe/Amsterdam"),
    ("NL-01-227", "De Wachter", "Zuidlaren", 53.09917, 6.69556, "Europe/Amsterdam"),
    ("NL-01-228", "Tweede Gesticht", "Veenhuizen", 53.03180, 6.39620, "Europe/Amsterdam"),
    ("NL-01-229", "Harbour", "Noordpolderzijl", 53.43222, 6.58306, "Europe/Amsterdam"),
    ("NL-01-230", "Borg Verhildersum", "Leens", 53.35970, 6.37580, "Europe/Amsterdam"),
    ("NL-01-231", "Campveerse Toren", "Veere", 51.54905, 3.66780, "Europe/Amsterdam"),
    ("NL-01-232", "Belfort", "Sluis", 51.30830, 3.38650, "Europe/Amsterdam"),
    ("NL-01-233", "Spanjaardsgat", "Breda", 51.59020, 4.77580, "Europe/Amsterdam"),
    ("NL-01-234", "Kasteel Heeswijk", "Heeswijk-Dinther", 51.65583, 5.44056, "Europe/Amsterdam"),
    ("NL-01-235", "Heksenwaag", "Oudewater", 52.02460, 4.86720, "Europe/Amsterdam"),
    ("NL-01-236", "Bergkerk", "Deventer", 52.25150, 6.16350, "Europe/Amsterdam"),
    ("NL-01-237", "The Ladder", "Saba", 17.62680, -63.25480, "America/Kralendijk"),
    ("NL-01-238", "Fort Amsterdam", "Sint Eustatius", 17.48000, -62.99000, "America/Kralendijk"),
    ("NL-01-239", "Sluis", "Makkum", 53.05430, 5.40280, "Europe/Amsterdam"),
    ("NL-01-240", "Onze-Lieve-Vrouwebasiliek", "Maastricht", 50.84770, 5.69320, "Europe/Amsterdam"),
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
