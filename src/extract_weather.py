"""Lädt Tageswetter je Bundesland über die Open-Meteo-Archiv-API (kostenlos, ohne Schlüssel).

Ergebnis: data/raw/weather_api.csv (state_code, date, temp_mean_c, precipitation_mm)

Die Datei dient als Cache: Ist sie vorhanden, wird die API nicht erneut abgefragt.
Mit --refresh werden die Daten neu geladen.

Aufruf: uv run python src/extract_weather.py [--refresh]
"""

import json
import sys
import time
import urllib.parse
import urllib.request

import pandas as pd

from config import RAW, WEATHER_LOCATIONS

OUT = RAW / "weather_api.csv"
API_URL = "https://archive-api.open-meteo.com/v1/archive"
START, END = "2013-01-01", "2015-07-31"  # Zeitraum der Umsatzdaten
RETRIES = 3


def fetch_state(state: str, lat: float, lon: float) -> pd.DataFrame:
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": START,
        "end_date": END,
        "daily": "temperature_2m_mean,precipitation_sum",
        "timezone": "Europe/Berlin",
    }
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"

    # Netzwerkfehler sind bei APIs normal -> mehrere Versuche mit wachsender Wartezeit
    for attempt in range(1, RETRIES + 1):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                payload = json.load(resp)
            break
        except OSError:
            if attempt == RETRIES:
                raise
            time.sleep(2**attempt)

    daily = payload["daily"]
    df = pd.DataFrame(
        {
            "state_code": state,
            "date": daily["time"],
            "temp_mean_c": daily["temperature_2m_mean"],
            "precipitation_mm": daily["precipitation_sum"],
        }
    )

    # Plausibilitätsprüfung der API-Antwort: lückenloser Zeitraum erwartet
    expected_days = len(pd.date_range(START, END))
    if len(df) != expected_days:
        raise ValueError(f"{state}: {len(df)} statt {expected_days} Tage von der API erhalten")
    return df


def main(refresh: bool = False) -> None:
    if OUT.exists() and not refresh:
        print(f"Wetterdaten bereits vorhanden ({OUT.name}), API-Abruf übersprungen")
        return

    frames = []
    for state, (lat, lon) in WEATHER_LOCATIONS.items():
        frames.append(fetch_state(state, lat, lon))
        print(f"  {state}: geladen")
        time.sleep(0.5)  # API schonen

    weather = pd.concat(frames, ignore_index=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    weather.to_csv(OUT, index=False)
    print(f"{len(weather):,} Zeilen -> {OUT.name}")


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv)
