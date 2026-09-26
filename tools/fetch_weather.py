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
    ("NL-01-209", "De Meerpaal", "Dronten", 52.52363, 5.71976, "Europe/Amsterdam"),
    ("NL-01-210", "Blocq van Kuffeler", "Almere", 52.41750, 5.22483, "Europe/Amsterdam"),
    ("NL-01-211", "Kerkje aan de Zee", "Urk", 52.66232, 5.59342, "Europe/Amsterdam"),
    ("NL-01-212", "Magnuskerk", "Anloo", 53.04310, 6.69794, "Europe/Amsterdam"),
    ("NL-01-213", "Hunebedden", "Rolde", 52.98955, 6.64918, "Europe/Amsterdam"),
    ("NL-01-214", "Kerk", "Niehove", 53.29103, 6.36787, "Europe/Amsterdam"),
    ("NL-01-215", "Sint-Jozefkathedraal", "Groningen", 53.21490, 6.57278, "Europe/Amsterdam"),
    ("NL-01-216", "Museum de Fundatie", "Zwolle", 52.51024, 6.09150, "Europe/Amsterdam"),
    ("NL-01-217", "Bovenkerk", "Kampen", 52.55496, 5.92027, "Europe/Amsterdam"),
    ("NL-01-218", "Stadhuis", "Bolsward", 53.06211, 5.52327, "Europe/Amsterdam"),
    ("NL-01-219", "Vuurtoren", "Hollum", 53.44922, 5.62571, "Europe/Amsterdam"),
    ("NL-01-220", "Bonnefantenmuseum", "Maastricht", 50.84248, 5.70134, "Europe/Amsterdam"),
    ("NL-01-221", "Kasteel Eijsden", "Eijsden", 50.77374, 5.69959, "Europe/Amsterdam"),
    ("NL-01-222", "Onze Lieve Vrouwetoren", "Amersfoort", 52.15517, 5.38721, "Europe/Amsterdam"),
    ("NL-01-223", "Koepelkerk", "Willemstad", 51.69194, 4.43792, "Europe/Amsterdam"),
    ("NL-01-224", "Sint-Ludovicuskerk", "Rincon", 12.23867, -68.32982, "America/Kralendijk"),
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
