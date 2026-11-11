"""Führt die komplette Datenpipeline (ETL) mit einem Befehl aus.

    1. extract_weather.py  Wetter je Bundesland aus der Open-Meteo-API  -> data/raw/weather_api.csv
    2. clean.py            Bereinigung + Datenqualitätsprüfung          -> sales_clean, stores_clean, dq_report
    3. transform.py        Region/Bezirk, Like-for-Like-Flags, Plan     -> stores, sales, plan
    4. load_to_db.py       Star-Schema in SQLite + Exporte für Qlik     -> sales.db, qlik/*.csv
    5. commentary.py       Bezirkskommentare (KI oder regelbasiert)     -> qlik/district_commentary.csv

Schlägt ein Schritt fehl, laufen die folgenden nicht weiter. Jeder Lauf wird mit
Zeitstempel und Dauer je Schritt in logs/pipeline.log protokolliert.

Aufruf (im Projektordner): uv run python src/run_pipeline.py
"""

import logging
import sys
import time

import clean
import commentary
import extract_weather
import load_to_db
import transform
from config import RAW, ROOT

RAW_INPUTS = [RAW / "train.csv", RAW / "store.csv", RAW / "store_states.csv"]
LOG_FILE = ROOT / "logs" / "pipeline.log"

STEPS = [
    ("1/5 Wetterdaten (extract_weather.py)", extract_weather.main),
    ("2/5 Bereinigung + Datenqualität (clean.py)", clean.main),
    ("3/5 Anreicherung + Planung (transform.py)", transform.main),
    ("4/5 Laden in Datenbank (load_to_db.py)", load_to_db.main),
    ("5/5 Bezirkskommentare (commentary.py)", commentary.main),
]

log = logging.getLogger("pipeline")


def setup_logging() -> None:
    """Schreibt Meldungen gleichzeitig in die Konsole und in logs/pipeline.log."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    console_handler = logging.StreamHandler(sys.stdout)
    for handler in (file_handler, console_handler):
        handler.setFormatter(fmt)
        log.addHandler(handler)
    log.setLevel(logging.INFO)


def main() -> int:
    setup_logging()
    missing = [p.name for p in RAW_INPUTS if not p.exists()]
    if missing:
        log.error("Rohdaten fehlen in data/raw/: %s (Download siehe README)", ", ".join(missing))
        return 1

    log.info("Pipeline gestartet")
    start = time.perf_counter()
    for name, step in STEPS:
        t0 = time.perf_counter()
        log.info("Start  %s", name)
        try:
            step()
        except Exception:
            log.exception("FEHLER in %s - Pipeline abgebrochen", name)
            return 1
        log.info("Fertig %s (%.1f s)", name, time.perf_counter() - t0)
    log.info("Pipeline erfolgreich beendet (%.1f s)", time.perf_counter() - start)
    return 0


if __name__ == "__main__":
    sys.exit(main())
