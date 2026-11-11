"""Gemeinsame Pfade und Stammdaten-Zuordnungen für alle Pipeline-Schritte."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
QLIK_EXPORT = PROCESSED / "qlik"
DB_PATH = PROCESSED / "sales.db"

# Bundesländer, in denen der Datensatz Filialen hat. "HB,NI" ist in den Rohdaten nicht
# eindeutig (Bremen oder Niedersachsen) -> wird Niedersachsen zugeordnet und im
# Datenqualitätsbericht ausgewiesen.
STATES = {
    "BE": "Berlin",
    "BW": "Baden-Württemberg",
    "BY": "Bayern",
    "HE": "Hessen",
    "HH": "Hamburg",
    "NI": "Niedersachsen",
    "NW": "Nordrhein-Westfalen",
    "RP": "Rheinland-Pfalz",
    "SH": "Schleswig-Holstein",
    "SN": "Sachsen",
    "ST": "Sachsen-Anhalt",
    "TH": "Thüringen",
}

# Vertriebsregionen (eigene Gruppierung der Bundesländer, nicht aus den Rohdaten)
REGIONS = {
    "SH": "Nord", "HH": "Nord", "NI": "Nord",
    "BE": "Ost", "SN": "Ost", "ST": "Ost", "TH": "Ost",
    "NW": "West",
    "HE": "Mitte", "RP": "Mitte",
    "BY": "Süd", "BW": "Süd",
}

# Wetterstation je Bundesland: Landeshauptstadt als Näherung (Breite, Länge)
WEATHER_LOCATIONS = {
    "BE": (52.52, 13.40),  # Berlin
    "BW": (48.78, 9.18),   # Stuttgart
    "BY": (48.14, 11.58),  # München
    "HE": (50.08, 8.24),   # Wiesbaden
    "HH": (53.55, 10.00),  # Hamburg
    "NI": (52.37, 9.73),   # Hannover
    "NW": (51.23, 6.78),   # Düsseldorf
    "RP": (50.00, 8.27),   # Mainz
    "SH": (54.32, 10.13),  # Kiel
    "SN": (51.05, 13.74),  # Dresden
    "ST": (52.13, 11.63),  # Magdeburg
    "TH": (50.98, 11.03),  # Erfurt
}

# Filialtypen und Sortimente sind im Datensatz anonymisiert (a-d)
STORE_TYPES = {"a": "Typ A", "b": "Typ B", "c": "Typ C", "d": "Typ D"}
ASSORTMENTS = {"a": "Basis", "b": "Extra", "c": "Erweitert"}
