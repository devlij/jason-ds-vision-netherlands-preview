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
    ("NL-01-177", "Museum Nagele", "Nagele", 52.6439, 5.7233, "Europe/Amsterdam"),
    ("NL-01-178", "Stadhuis", "Almere", 52.3708, 5.2214, "Europe/Amsterdam"),
    ("NL-01-179", "Hunebed D53", "Havelte", 52.8072, 6.2167, "Europe/Amsterdam"),
    ("NL-01-180", "Koloniehuisjes", "Frederiksoord", 52.8462, 6.1875, "Europe/Amsterdam"),
    ("NL-01-181", "Meppeler Toren", "Meppel", 52.6956, 6.1944, "Europe/Amsterdam"),
    ("NL-01-182", "Havenkolk", "Blokzijl", 52.7264, 5.9618, "Europe/Amsterdam"),
    ("NL-01-183", "Oude Haven", "Vollenhove", 52.6808, 5.9518, "Europe/Amsterdam"),
    ("NL-01-184", "Plechelmusbasiliek", "Oldenzaal", 52.3128, 6.9286, "Europe/Amsterdam"),
    ("NL-01-185", "Fraeylemaborg", "Slochteren", 53.2154, 6.8096, "Europe/Amsterdam"),
    ("NL-01-186", "Klooster Ter Apel", "Ter Apel", 52.8762, 7.0749, "Europe/Amsterdam"),
    ("NL-01-187", "Lemsterpoort", "Sloten", 52.8922, 5.6458, "Europe/Amsterdam"),
    ("NL-01-188", "Stadhuis", "Dokkum", 53.3236, 5.9998, "Europe/Amsterdam"),
    ("NL-01-189", "Fort Bay", "Saba", 17.6164, -63.2514, "America/Kralendijk"),
    ("NL-01-190", "Lower Town", "Oranjestad", 17.4802, -62.9872, "America/Kralendijk"),
    ("NL-01-191", "Slave huts", "Bonaire", 12.0985, -68.2835, "America/Kralendijk"),
    ("NL-01-192", "Ferry terminal", "Lauwersoog", 53.4098, 6.2016, "Europe/Amsterdam"),
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
