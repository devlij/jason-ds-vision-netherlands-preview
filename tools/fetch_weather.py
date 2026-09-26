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
    ("NL-01-193", "Vuurtoren", "Urk", 52.6611215, 5.5920149, "Europe/Amsterdam"),
    ("NL-01-194", "Buitencentrum", "Lelystad", 52.4573335, 5.4171408, "Europe/Amsterdam"),
    ("NL-01-195", "The Wave", "Almere", 52.3668826, 5.2158702, "Europe/Amsterdam"),
    ("NL-01-196", "Lichtwachterswoning", "Schokland", 52.6560313, 5.7794917, "Europe/Amsterdam"),
    ("NL-01-197", "Papeloze Kerk", "Schoonoord", 52.8225144, 6.7761768, "Europe/Amsterdam"),
    ("NL-01-198", "Havezate Mensinge", "Roden", 53.1352526, 6.4356766, "Europe/Amsterdam"),
    ("NL-01-199", "Veenpark", "Barger-Compascuum", 52.7563806, 7.0268358, "Europe/Amsterdam"),
    ("NL-01-200", "Peperbus", "Zwolle", 52.5121828, 6.0897359, "Europe/Amsterdam"),
    ("NL-01-201", "Waag", "Deventer", 52.2515098, 6.1600370, "Europe/Amsterdam"),
    ("NL-01-202", "Koornmarktspoort", "Kampen", 52.5554269, 5.9215500, "Europe/Amsterdam"),
    ("NL-01-203", "Aa-kerk", "Groningen", 53.21638889, 6.56222222, "Europe/Amsterdam"),
    ("NL-01-204", "Jacobuskerk", "Zeerijp", 53.34598889, 6.75678333, "Europe/Amsterdam"),
    ("NL-01-205", "Plompe Toren", "Burgh-Haamstede", 51.6816, 3.77245, "Europe/Amsterdam"),
    ("NL-01-206", "Sint-Lievensmonstertoren", "Zierikzee", 51.6502809, 3.9147517, "Europe/Amsterdam"),
    ("NL-01-207", "Fort de Windt", "Sint Eustatius", 17.465678, -62.9639628, "America/Kralendijk"),
    ("NL-01-208", "Hell's Gate", "Saba", 17.639036, -63.2290788, "America/Kralendijk"),
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
