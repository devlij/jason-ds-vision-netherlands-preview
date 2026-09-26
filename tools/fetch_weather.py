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
    ("NL-01-257", "1000 Steps", "Bonaire", 12.21086, -68.32180, "America/Kralendijk"),
    ("NL-01-258", "Dutch Reformed Church", "Oranjestad", 17.48125, -62.98589, "America/Kralendijk"),
    ("NL-01-259", "Havezate De Havixhorst", "De Wijk", 52.67339, 6.27301, "Europe/Amsterdam"),
    ("NL-01-260", "Sint-Margaretakerk", "Norg", 53.06631, 6.46127, "Europe/Amsterdam"),
    ("NL-01-261", "Abdijkerk", "Aduard", 53.25644, 6.46020, "Europe/Amsterdam"),
    ("NL-01-262", "Borg Nienoord", "Leek", 53.16796, 6.39452, "Europe/Amsterdam"),
    ("NL-01-263", "Zuidertoren", "Schiermonnikoog", 53.48147, 6.15862, "Europe/Amsterdam"),
    ("NL-01-264", "Sint-Gertrudiskerk", "Workum", 52.97899, 5.44299, "Europe/Amsterdam"),
    ("NL-01-265", "Kerkruïne", "Schokland", 52.62028, 5.77350, "Europe/Amsterdam"),
    ("NL-01-266", "Houtribsluizen", "Lelystad", 52.52700, 5.43432, "Europe/Amsterdam"),
    ("NL-01-267", "Grote Kerk", "Veere", 51.54716, 3.66749, "Europe/Amsterdam"),
    ("NL-01-268", "Haven", "Brouwershaven", 51.72426, 3.91671, "Europe/Amsterdam"),
    ("NL-01-269", "Fort Sint Pieter", "Maastricht", 50.83600, 5.68402, "Europe/Amsterdam"),
    ("NL-01-270", "Basiliek", "Meerssen", 50.88372, 5.75505, "Europe/Amsterdam"),
    ("NL-01-271", "Begijnhof", "Breda", 51.59007, 4.77833, "Europe/Amsterdam"),
    ("NL-01-272", "Hampoort", "Grave", 51.75730, 5.73872, "Europe/Amsterdam"),
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
