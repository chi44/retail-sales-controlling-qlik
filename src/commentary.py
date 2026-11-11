"""Erzeugt je Außendienst-Bezirk einen kurzen Kommentar mit Handlungsempfehlung.

Ablauf:
1. Kennzahlen je Bezirk per SQL aus der Datenbank (sql/district_kpis.sql)
2. Kommentar formulieren:
   - mit Claude (Anthropic API), wenn ein API-Schlüssel vorhanden ist (ANTHROPIC_API_KEY)
   - sonst regelbasiert, damit das Dashboard immer einen Kommentar hat
3. Ergebnis: data/processed/qlik/district_commentary.csv

Die Zahlen berechnet immer der Code, nie das Sprachmodell. Das Modell bekommt nur die
fertigen Kennzahlen und formuliert daraus Text. So kann es keine Zahlen "erfinden".

Aufruf: uv run python src/commentary.py
"""

import json
import os
import sqlite3

import pandas as pd

from config import DB_PATH, QLIK_EXPORT, ROOT

KPI_SQL = ROOT / "sql" / "district_kpis.sql"
OUT = QLIK_EXPORT / "district_commentary.csv"
MODEL = "claude-opus-5-5"

SYSTEM_PROMPT = """\
Du bist Analyst im Vertriebscontrolling einer Drogeriemarktkette. Du schreibst
Kommentare für Bezirksleiter im Außendienst, die sie vor dem nächsten Filialbesuch lesen.

Regeln:
- Genau drei Sätze, Deutsch, sachlich, keine Floskeln, keine Aufzählungszeichen.
- Satz 1: Lage des Bezirks (Abweichung zum Plan und Vorjahr).
- Satz 2: Ursache. Zerlege die Umsatzentwicklung in Kundenfrequenz und Durchschnittsbon und
  sage, welcher Treiber dominiert.
- Satz 3: eine konkrete Handlungsempfehlung, die sich auf eine benannte Filiale bezieht.
- Verwende ausschließlich die gelieferten Zahlen. Runde Prozentwerte auf eine Nachkommastelle.
  Erfinde keine Ursachen, die nicht aus den Daten folgen (z. B. Baustellen, Personal);
  formuliere solche Vermutungen höchstens als zu prüfende Frage.
"""


def load_kpis(year: int) -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as con:
        max_month = con.execute(
            "SELECT MAX(month) FROM fact_sales JOIN dim_date USING (date) WHERE year = ?", (year,)
        ).fetchone()[0]
        kpis = pd.read_sql(
            KPI_SQL.read_text(encoding="utf-8"), con, params={"year": year, "max_month": max_month}
        )
    kpis["period"] = f"{year} Jan-{max_month:02d}"
    return kpis


def pct(x: float, signed: bool = True) -> str:
    """0.0123 -> '+1,2 %' (signed=False: '1,2 %', Richtung steht dann im Text)."""
    text = f"{x * 100:+.1f} %" if signed else f"{abs(x) * 100:.1f} %"
    return text.replace(".", ",")


def rule_based_comment(k: pd.Series) -> str:
    """Fallback ohne KI: feste Textbausteine nach einfachen Entscheidungsregeln."""
    lage = "über" if k.plan_dev >= 0 else "unter"
    s1 = (f"Bezirk {k.district} liegt {pct(k.plan_dev, signed=False)} {lage} Plan, "
          f"flächenbereinigt {pct(k.sales_lfl_yoy)} zum Vorjahr.")

    if abs(k.customers_lfl_yoy) >= abs(k.avg_basket_lfl_yoy):
        treiber = "die Kundenfrequenz"
    else:
        treiber = "der Durchschnittsbon"
    s2 = (f"Treiber ist {treiber} (Kunden {pct(k.customers_lfl_yoy)}, "
          f"Ø-Bon {pct(k.avg_basket_lfl_yoy)}).")

    if k.weakest_store_plan_dev < -0.03:
        s3 = (f"Priorität beim nächsten Besuch: {k.weakest_store} ({pct(k.weakest_store_plan_dev)} "
              f"zum Plan) – Frequenz und Promo-Umsetzung prüfen.")
    else:
        s3 = (f"Keine Filiale fällt deutlich ab; Erfolgsfaktoren von {k.strongest_store} "
              f"({pct(k.strongest_store_plan_dev)} zum Plan) im Bezirk teilen.")
    return " ".join([s1, s2, s3])


def llm_comment(client, k: pd.Series) -> str:
    facts = {
        "bezirk": k.district,
        "region": k.region,
        "zeitraum": k.period,
        "anzahl_filialen": int(k.n_stores),
        "umsatz_ist_eur": round(k.sales),
        "umsatz_plan_eur": round(k.plan_sales),
        "abweichung_plan": round(k.plan_dev, 4),
        "umsatz_vorjahr_lfl": round(k.sales_lfl_yoy, 4),
        "kunden_vorjahr_lfl": round(k.customers_lfl_yoy, 4),
        "durchschnittsbon_vorjahr_lfl": round(k.avg_basket_lfl_yoy, 4),
        "promo_anteil_umsatz": round(k.promo_share, 4),
        "schwaechste_filiale": {"name": k.weakest_store, "abweichung_plan": round(k.weakest_store_plan_dev, 4)},
        "staerkste_filiale": {"name": k.strongest_store, "abweichung_plan": round(k.strongest_store_plan_dev, 4)},
    }
    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": "Kennzahlen (Anteile als Dezimalzahl, 0.012 = 1,2 %):\n"
                       + json.dumps(facts, ensure_ascii=False, indent=2),
        }],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Anfrage abgelehnt")
    return next(b.text for b in response.content if b.type == "text").strip()


def main(year: int = 2015) -> None:
    kpis = load_kpis(year)

    client = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic
        client = anthropic.Anthropic()
        print(f"Kommentare mit {MODEL} ...")
    else:
        print("Kein ANTHROPIC_API_KEY gesetzt -> regelbasierte Kommentare")

    comments, sources = [], []
    for _, k in kpis.iterrows():
        text, source = None, "regelbasiert"
        if client is not None:
            try:
                text, source = llm_comment(client, k), f"KI ({MODEL})"
            except Exception as e:  # ein Fehler bei einem Bezirk soll den Lauf nicht abbrechen
                print(f"  {k.district}: KI fehlgeschlagen ({type(e).__name__}), Fallback auf Regeln")
        comments.append(text or rule_based_comment(k))
        sources.append(source)

    kpis["comment"] = comments
    kpis["comment_source"] = sources
    OUT.parent.mkdir(parents=True, exist_ok=True)
    kpis.to_csv(OUT, index=False)
    print(f"{len(kpis)} Bezirkskommentare -> {OUT.relative_to(ROOT)}")
    print("Beispiel:", kpis.iloc[0]["comment"])


if __name__ == "__main__":
    main()
