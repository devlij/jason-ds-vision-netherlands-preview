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
    ("NL-01-273", "Cellebroederspoort", "Kampen", 52.55427, 5.91545, "Europe/Amsterdam"),
    ("NL-01-274", "Sint-Stephanuskerk", "Hasselt", 52.59049, 6.08958, "Europe/Amsterdam"),
    ("NL-01-275", "Kasteel Het Nijenhuis", "Heino", 52.42143, 6.21716, "Europe/Amsterdam"),
    ("NL-01-276", "Slot Zeist", "Zeist", 52.07899, 5.23420, "Europe/Amsterdam"),
    ("NL-01-277", "Sint-Nicolaasbasiliek", "IJsselstein", 52.01897, 5.04054, "Europe/Amsterdam"),
    ("NL-01-278", "Kasteel Groeneveld", "Baarn", 52.21862, 5.25487, "Europe/Amsterdam"),
    ("NL-01-279", "Blue obelisk", "Bonaire", 12.08420, -68.28140, "America/Kralendijk"),
    ("NL-01-280", "Honen Dalim", "Oranjestad", 17.48186, -62.98535, "America/Kralendijk"),
    ("NL-01-281", "Basiliek", "Sint Odiliënberg", 51.14849, 5.99823, "Europe/Amsterdam"),
    ("NL-01-282", "Drogenapstoren", "Zutphen", 52.13910, 6.19765, "Europe/Amsterdam"),
    ("NL-01-283", "Gevangenpoort", "Woudrichem", 51.81827, 5.00390, "Europe/Amsterdam"),
    ("NL-01-284", "Stadhuis", "Zierikzee", 51.65037, 3.91885, "Europe/Amsterdam"),
    ("NL-01-285", "Gemaal Wortman", "Lelystad", 52.50322, 5.42050, "Europe/Amsterdam"),
    ("NL-01-286", "Stadhuis", "Sneek", 53.03250, 5.65904, "Europe/Amsterdam"),
    ("NL-01-287", "Goudkantoor", "Groningen", 53.21849, 6.56628, "Europe/Amsterdam"),
    ("NL-01-288", "Sint-Pancratiuskerk", "Diever", 52.85568, 6.31698, "Europe/Amsterdam"),
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
