"""Reichert die bereinigten Daten für das Vertriebscontrolling an.

1. Filialen: Bundesland, Vertriebsregion und Außendienst-Bezirk
2. Umsätze: Flags für den flächenbereinigten Vorjahresvergleich (Like-for-Like)
3. Planung: Umsatz- und Kundenplan 2015 je Filiale und Monat (simuliert)

Ausgang:  data/processed/stores.csv, sales.csv, plan.csv

Aufruf: uv run python src/transform.py
"""

import math

import pandas as pd

from config import ASSORTMENTS, PROCESSED, REGIONS, STATES, STORE_TYPES

# Ein Bezirksleiter (Außendienst) betreut rund 20 Filialen. Die Bezirke sind simuliert:
# Filialen werden je Bundesland in Nummernreihenfolge auf gleich große Bezirke verteilt.
STORES_PER_DISTRICT = 20

PLAN_YEAR = 2015
# Zielwachstum ggü. Vorjahr, je Region unterschiedlich ambitioniert (simulierte Vorgabe)
GROWTH_TARGET = {"Nord": 0.04, "Ost": 0.035, "West": 0.03, "Mitte": 0.04, "Süd": 0.05}


def build_stores(stores: pd.DataFrame) -> pd.DataFrame:
    df = stores.copy()
    df["state_name"] = df["state_code"].map(STATES)
    df["region"] = df["state_code"].map(REGIONS)
    df["store_type"] = df["store_type"].map(STORE_TYPES)
    df["assortment"] = df["assortment"].map(ASSORTMENTS)

    df = df.sort_values(["state_code", "store_id"])
    rank = df.groupby("state_code").cumcount()
    size = df.groupby("state_code")["store_id"].transform("size")
    n_districts = size.map(lambda n: math.ceil(n / STORES_PER_DISTRICT))
    # gleichmäßig verteilen statt "20, 20, ..., Rest 3"
    district_no = (rank * n_districts // size + 1).astype(int)
    df["district"] = df["state_code"] + "-" + district_no.astype(str).str.zfill(2)

    df["store_name"] = "Filiale " + df["store_id"].astype(str).str.zfill(4)
    return df.sort_values("store_id").reset_index(drop=True)


def add_lfl_flags(sales: pd.DataFrame) -> pd.DataFrame:
    """Markiert Umsätze, die in einen fairen Vorjahresvergleich eingehen dürfen.

    Eine Filiale ist in einem Monat vergleichbar, wenn sie im selben Monat des Vor- bzw.
    Folgejahres ebenfalls Umsatz hatte. Ohne diese Bereinigung erzeugt die Datenlücke der
    bayerischen Filialen (Jul-Dez 2014) einen scheinbaren Umsatzeinbruch 2014 und ein
    scheinbares Wachstum 2015.

    lfl_prev_year = 1: Zeile zählt im aktuellen Jahr eines VJ-Vergleichs
    lfl_next_year = 1: Zeile zählt als Vorjahreswert im Vergleich mit dem Folgejahr
    """
    df = sales.copy()
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month

    active = df[["store_id", "year", "month"]].drop_duplicates()
    prev = active.assign(year=active["year"] + 1, lfl_prev_year=1)  # "hatte im Vorjahr Umsatz"
    nxt = active.assign(year=active["year"] - 1, lfl_next_year=1)   # "hat im Folgejahr Umsatz"

    df = df.merge(prev, on=["store_id", "year", "month"], how="left")
    df = df.merge(nxt, on=["store_id", "year", "month"], how="left")
    df[["lfl_prev_year", "lfl_next_year"]] = df[["lfl_prev_year", "lfl_next_year"]].fillna(0).astype(int)
    return df.drop(columns=["year", "month"])


def build_plan(sales: pd.DataFrame, stores: pd.DataFrame) -> pd.DataFrame:
    """Simulierter Monatsplan 2015: Vorjahresmonat x (1 + Zielwachstum der Region).

    Fehlt der Vorjahresmonat (Bayern Jul-Dez 2014), dient derselbe Monat 2013 als Basis,
    hochgerechnet mit dem flächenbereinigten Wachstum 2014 der Region.
    """
    monthly = (
        sales.assign(year=sales["date"].dt.year, month=sales["date"].dt.month)
        .groupby(["store_id", "year", "month"], as_index=False)[["sales", "customers"]]
        .sum()
    )
    monthly = monthly.merge(stores[["store_id", "region"]], on="store_id")

    base = monthly[monthly["year"] == PLAN_YEAR - 1].set_index(["store_id", "month"])
    fallback = monthly[monthly["year"] == PLAN_YEAR - 2].set_index(["store_id", "month"])

    # flächenbereinigtes Wachstum 2014 vs. 2013 je Region (nur Monate mit Daten in beiden Jahren)
    prev_sales = fallback[["sales"]].rename(columns={"sales": "sales_prev"})
    both = base[["sales", "region"]].join(prev_sales, how="inner")
    lfl_growth = both.groupby("region")["sales"].sum() / both.groupby("region")["sales_prev"].sum()

    idx = pd.MultiIndex.from_product(
        [stores["store_id"], range(1, 13)], names=["store_id", "month"]
    )
    plan = pd.DataFrame(index=idx).join(base[["sales", "customers"]]).reset_index()
    plan["plan_basis"] = "Vorjahr"

    missing = plan["sales"].isna()
    fb = fallback.loc[plan.loc[missing].set_index(["store_id", "month"]).index]
    factor = fb["region"].map(lfl_growth).to_numpy()
    plan.loc[missing, "sales"] = fb["sales"].to_numpy() * factor
    plan.loc[missing, "customers"] = fb["customers"].to_numpy() * factor
    plan.loc[missing, "plan_basis"] = "Vor-Vorjahr hochgerechnet"

    plan = plan.merge(stores[["store_id", "region"]], on="store_id")
    target = plan["region"].map(GROWTH_TARGET)
    plan["plan_sales"] = (plan["sales"] * (1 + target)).round(0)
    plan["plan_customers"] = (plan["customers"] * (1 + target)).round(0)
    plan["month_start"] = pd.to_datetime(dict(year=PLAN_YEAR, month=plan["month"], day=1))
    return plan[["store_id", "month_start", "plan_sales", "plan_customers", "plan_basis"]]


def main() -> None:
    stores = build_stores(pd.read_csv(PROCESSED / "stores_clean.csv"))
    sales = add_lfl_flags(pd.read_csv(PROCESSED / "sales_clean.csv", parse_dates=["date"]))
    plan = build_plan(sales, stores)

    stores.to_csv(PROCESSED / "stores.csv", index=False)
    sales.to_csv(PROCESSED / "sales.csv", index=False)
    plan.to_csv(PROCESSED / "plan.csv", index=False)

    print(f"{stores['region'].nunique()} Regionen, {stores['district'].nunique()} Bezirke")
    print(f"Plan {PLAN_YEAR}: {len(plan):,} Zeilen, {plan['plan_sales'].sum() / 1e6:,.1f} Mio. € Umsatz")
    print(plan["plan_basis"].value_counts().to_string())


if __name__ == "__main__":
    main()
