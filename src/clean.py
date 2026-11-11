"""Bereinigt die Rohdaten und prüft sie mit festen Datenqualitätsregeln.

Eingang:  data/raw/train.csv, store.csv, store_states.csv
Ausgang:  data/processed/sales_clean.csv    Tagesumsätze je Filiale (nur geöffnete Tage)
          data/processed/stores_clean.csv   Filialstammdaten
          data/processed/dq_report.csv      Ergebnis jeder Prüfregel (wird in Qlik angezeigt)

Grundsatz: Auffällige Werte werden nicht stillschweigend gelöscht, sondern markiert
und im Bericht ausgewiesen. Entfernt werden nur Zeilen, die fachlich nicht verwertbar sind.

Aufruf: uv run python src/clean.py
"""

import pandas as pd

from config import PROCESSED, RAW, STATES

DQ_REPORT = PROCESSED / "dq_report.csv"
# Wettbewerber-Eröffnungen davor sind Platzhalterwerte (z. B. 1900)
MIN_PLAUSIBLE_YEAR = 1950


class DQReport:
    """Sammelt die Ergebnisse der Prüfregeln."""

    def __init__(self) -> None:
        self.rows: list[dict] = []

    def add(self, rule_id: str, table: str, check: str, affected: int, action: str) -> None:
        self.rows.append(
            {
                "rule_id": rule_id,
                "table": table,
                "check": check,
                "affected_rows": int(affected),
                "status": "OK" if affected == 0 else "Auffällig",
                "action": action if affected else "-",
            }
        )

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)


def clean_stores(stores: pd.DataFrame, store_states: pd.DataFrame, dq: DQReport) -> pd.DataFrame:
    df = stores.merge(store_states, on="Store", how="left")
    df.columns = [
        "store_id", "store_type", "assortment", "competition_distance_m",
        "competition_open_month", "competition_open_year", "promo2",
        "promo2_since_week", "promo2_since_year", "promo_interval", "state_raw",
    ]

    dq.add("S01", "Filialen", "Filiale ohne Bundesland-Zuordnung",
           df["state_raw"].isna().sum(), "Abbruch der Pipeline")
    if df["state_raw"].isna().any():
        raise ValueError("Filialen ohne Bundesland gefunden")

    ambiguous = df["state_raw"] == "HB,NI"
    dq.add("S02", "Filialen", "Bundesland nicht eindeutig (HB,NI)",
           ambiguous.sum(), "Niedersachsen zugeordnet, Flag state_ambiguous")
    df["state_ambiguous"] = ambiguous.astype(int)
    df["state_code"] = df["state_raw"].replace({"HB,NI": "NI"})
    df = df.drop(columns="state_raw")

    unknown = ~df["state_code"].isin(STATES)
    dq.add("S03", "Filialen", "Unbekanntes Bundesland-Kürzel", unknown.sum(), "Abbruch der Pipeline")
    if unknown.any():
        raise ValueError(f"Unbekannte Bundesländer: {df.loc[unknown, 'state_code'].unique()}")

    dq.add("S04", "Filialen", "Wettbewerberentfernung fehlt",
           df["competition_distance_m"].isna().sum(), "bleibt leer (kein Schätzwert)")

    # Eröffnungsdatum des Wettbewerbers aus Monat + Jahr; fehlt bei ca. 1/3 der Filialen
    implausible = df["competition_open_year"] < MIN_PLAUSIBLE_YEAR
    dq.add("S05", "Filialen", f"Wettbewerber-Eröffnung vor {MIN_PLAUSIBLE_YEAR} (unplausibel)",
           implausible.sum(), "Datum geleert")
    df.loc[implausible, ["competition_open_year", "competition_open_month"]] = None

    has_date = df["competition_open_year"].notna()
    df["competition_open_date"] = pd.NaT
    df.loc[has_date, "competition_open_date"] = pd.to_datetime(
        dict(year=df.loc[has_date, "competition_open_year"],
             month=df.loc[has_date, "competition_open_month"], day=1)
    )
    df = df.drop(columns=["competition_open_month", "competition_open_year"])

    df["promo_interval"] = df["promo_interval"].fillna("")
    return df


def clean_sales(
    sales: pd.DataFrame, store_ids: pd.Series, dq: DQReport
) -> tuple[pd.DataFrame, pd.Series]:
    df = sales.rename(
        columns={
            "Store": "store_id", "Date": "date", "Sales": "sales", "Customers": "customers",
            "Open": "is_open", "Promo": "promo", "StateHoliday": "state_holiday",
            "SchoolHoliday": "school_holiday",
        }
    ).drop(columns="DayOfWeek")  # wird in Qlik aus dem Datum abgeleitet
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d")

    dq.add("T01", "Umsätze", "Doppelte Kombination Filiale/Tag",
           df.duplicated(["store_id", "date"]).sum(), "Duplikate entfernt")
    df = df.drop_duplicates(["store_id", "date"])

    orphan = ~df["store_id"].isin(store_ids)
    dq.add("T02", "Umsätze", "Umsatz zu unbekannter Filiale (referentielle Integrität)",
           orphan.sum(), "Zeilen entfernt")
    df = df[~orphan]

    # Feiertagskennzeichen ist in der CSV gemischt als Zahl 0 und Text "0" gespeichert
    df["state_holiday"] = df["state_holiday"].astype(str).replace({"0": "kein"})
    df["state_holiday"] = df["state_holiday"].replace(
        {"a": "gesetzlich", "b": "Ostern", "c": "Weihnachten"}
    )

    closed_with_sales = (df["is_open"] == 0) & (df["sales"] > 0)
    dq.add("T03", "Umsätze", "Geschlossen, aber Umsatz > 0", closed_with_sales.sum(), "Zeilen entfernt")

    open_no_sales = (df["is_open"] == 1) & (df["sales"] == 0)
    dq.add("T04", "Umsätze", "Geöffnet, aber Umsatz = 0 (vermutl. Kassenausfall)",
           open_no_sales.sum(), "Zeilen entfernt, sonst wird der Tagesdurchschnitt verzerrt")

    no_customers = (df["sales"] > 0) & (df["customers"] == 0)
    dq.add("T05", "Umsätze", "Umsatz > 0 ohne Kunden", no_customers.sum(), "Zeilen entfernt")

    # Lücken: jede Filiale sollte für jeden Tag des Zeitraums eine Zeile haben (auch geschlossen)
    expected = df["date"].nunique()
    per_store = df.groupby("store_id")["date"].count()
    gap_days = (expected - per_store).rename("missing_days")
    dq.add("T06", "Umsätze", f"Filialen mit fehlenden Tagen (Soll: {expected} Tage)",
           (gap_days > 0).sum(),
           "Filialen markiert (has_data_gap); im Vorjahresvergleich nur vergleichbare Filialen")

    # Analysegrundlage sind die geöffneten Verkaufstage
    df = df[(df["is_open"] == 1) & ~open_no_sales & ~no_customers].drop(columns="is_open")

    # Ausreißer je Filiale (Interquartilsabstand): bleiben drin, werden nur markiert
    q1 = df.groupby("store_id")["sales"].transform("quantile", 0.25)
    q3 = df.groupby("store_id")["sales"].transform("quantile", 0.75)
    df["is_outlier"] = ((df["sales"] > q3 + 3 * (q3 - q1)) | (df["sales"] < q1 - 3 * (q3 - q1))).astype(int)
    dq.add("T07", "Umsätze", "Ausreißer-Tagesumsatz (> 3x Interquartilsabstand je Filiale)",
           df["is_outlier"].sum(), "markiert (is_outlier), nicht entfernt")

    df = df.sort_values(["store_id", "date"]).reset_index(drop=True)
    return df, gap_days


def main() -> None:
    dq = DQReport()
    stores = clean_stores(
        pd.read_csv(RAW / "store.csv"), pd.read_csv(RAW / "store_states.csv"), dq
    )
    sales, gap_days = clean_sales(
        pd.read_csv(RAW / "train.csv", dtype={"StateHoliday": str}), stores["store_id"], dq
    )

    stores["missing_days"] = stores["store_id"].map(gap_days).fillna(0).astype(int)
    stores["has_data_gap"] = (stores["missing_days"] > 0).astype(int)

    PROCESSED.mkdir(parents=True, exist_ok=True)
    sales.to_csv(PROCESSED / "sales_clean.csv", index=False)
    stores.to_csv(PROCESSED / "stores_clean.csv", index=False)
    report = dq.to_frame()
    report.to_csv(DQ_REPORT, index=False)

    print(f"{len(sales):,} Verkaufstage, {len(stores)} Filialen")
    print(report[["rule_id", "check", "affected_rows", "status"]].to_string(index=False))


if __name__ == "__main__":
    main()
