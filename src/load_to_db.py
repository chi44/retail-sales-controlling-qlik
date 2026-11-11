"""Lädt Ist, Plan, Wetter und Datenqualitätsbericht in das SQLite-Star-Schema
und exportiert die Tabellen als CSV für Qlik Sense.

Ausgang:  data/processed/sales.db       (Schema: sql/schema.sql)
          data/processed/qlik/*.csv     (Upload-Dateien für Qlik Cloud)

Aufruf: uv run python src/load_to_db.py
"""

import sqlite3

import pandas as pd

from config import DB_PATH, PROCESSED, QLIK_EXPORT, RAW, ROOT

SCHEMA = ROOT / "sql" / "schema.sql"
WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


def build_dim_date(start: str, end: str) -> pd.DataFrame:
    dates = pd.date_range(start, end, freq="D")
    return pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "year": dates.year,
            "month": dates.month,
            "year_month": dates.strftime("%Y-%m"),
            "iso_week": dates.isocalendar().week.to_numpy(),
            "weekday_no": dates.day_of_week + 1,
            "weekday": [WEEKDAYS[d] for d in dates.day_of_week],
        }
    )


def check_integrity(con: sqlite3.Connection) -> None:
    """Prüft nach dem Laden, ob jeder Faktenschlüssel in den Dimensionen existiert."""
    checks = {
        "Umsatz ohne Filiale": "SELECT COUNT(*) FROM fact_sales f LEFT JOIN dim_store s USING (store_id) WHERE s.store_id IS NULL",
        "Umsatz ohne Datum": "SELECT COUNT(*) FROM fact_sales f LEFT JOIN dim_date d USING (date) WHERE d.date IS NULL",
        "Plan ohne Filiale": "SELECT COUNT(*) FROM fact_plan f LEFT JOIN dim_store s USING (store_id) WHERE s.store_id IS NULL",
        "Wetter fehlt für Filialtag": """
            SELECT COUNT(*) FROM fact_sales f
            JOIN dim_store s USING (store_id)
            LEFT JOIN fact_weather w ON w.state_code = s.state_code AND w.date = f.date
            WHERE w.date IS NULL""",
    }
    for name, sql in checks.items():
        n = con.execute(sql).fetchone()[0]
        if n:
            raise ValueError(f"Integritätsprüfung fehlgeschlagen: {name} ({n} Zeilen)")


def main() -> None:
    sales = pd.read_csv(PROCESSED / "sales.csv")
    stores = pd.read_csv(PROCESSED / "stores.csv")
    plan = pd.read_csv(PROCESSED / "plan.csv")
    weather = pd.read_csv(RAW / "weather_api.csv")
    dq = pd.read_csv(PROCESSED / "dq_report.csv")
    dim_date = build_dim_date(sales["date"].min(), plan["month_start"].max()[:4] + "-12-31")

    dim_store = stores[
        ["store_id", "store_name", "store_type", "assortment", "state_code", "state_name",
         "region", "district", "competition_distance_m", "competition_open_date", "promo2",
         "promo2_since_week", "promo2_since_year", "promo_interval", "state_ambiguous",
         "missing_days", "has_data_gap"]
    ]

    DB_PATH.unlink(missing_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        con.executescript(SCHEMA.read_text(encoding="utf-8"))
        # append statt replace: Tabellen und Schlüssel kommen aus schema.sql, nicht von pandas
        for name, df in [
            ("dim_store", dim_store), ("dim_date", dim_date), ("fact_sales", sales),
            ("fact_plan", plan), ("fact_weather", weather), ("dq_report", dq),
        ]:
            df.to_sql(name, con, if_exists="append", index=False)
            print(f"  {name:<13} {len(df):>9,} Zeilen")
        check_integrity(con)

    # Exporte für Qlik: ein Ordner, Datum im ISO-Format. Ganzzahlige Werte ohne ".0",
    # damit Qlik sie unabhängig vom eingestellten Dezimaltrennzeichen als Zahl erkennt.
    QLIK_EXPORT.mkdir(parents=True, exist_ok=True)
    int_cols = ["competition_distance_m", "promo2_since_week", "promo2_since_year"]
    dim_store.astype({c: "Int64" for c in int_cols}).to_csv(QLIK_EXPORT / "stores.csv", index=False)
    sales.to_csv(QLIK_EXPORT / "sales.csv", index=False)
    plan.astype({"plan_sales": "int64", "plan_customers": "int64"}).to_csv(
        QLIK_EXPORT / "plan.csv", index=False
    )
    weather.to_csv(QLIK_EXPORT / "weather.csv", index=False)
    dq.to_csv(QLIK_EXPORT / "dq_report.csv", index=False)
    print(f"Datenbank: {DB_PATH.relative_to(ROOT)}, Qlik-Exporte: {QLIK_EXPORT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
