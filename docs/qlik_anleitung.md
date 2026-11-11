# Anleitung: Dashboard in Qlik Sense aufbauen

Diese Anleitung führt vom leeren Qlik-Konto bis zum fertigen Dashboard mit vier Arbeitsblättern.
Vorkenntnisse in Qlik sind nicht nötig. Dauer: ca. 6–8 Stunden, verteilt auf 2–3 Tage.

**Begriffe für Power-BI-Umsteiger**

| Power BI | Qlik Sense |
|---|---|
| Power Query / Datenmodell | Datenladeeditor (Ladeskript) + Datenmodellanzeige |
| DAX-Measure | Kennzahl (Formel), wiederverwendbar als *Master-Kennzahl* |
| `CALCULATE(..., Filter)` | **Set Analysis**: `Sum({<Jahr={2015}>} Umsatz)` |
| Berichtsseite | Arbeitsblatt (Sheet) |
| Slicer | Filterfenster |
| Hierarchie | Drilldown-Dimension |

Der wichtigste Unterschied: In Qlik **filtert jede Auswahl automatisch das gesamte Datenmodell**
(assoziatives Modell). Ausgewählte Werte sind grün, verbundene weiß, ausgeschlossene grau.

---

## 1. Testversion anlegen (15 min)

1. Auf [qlik.com](https://www.qlik.com/de-de) auf **„Kostenlos testen“** klicken und die Testversion
   von **Qlik Cloud Analytics** wählen (in der Regel 30 Tage, ohne Kreditkarte).
2. Konto mit E-Mail bestätigen und den Mandanten (Tenant) anlegen lassen, Region z. B. *Europe*.
3. Nach dem Login landest du im **Analytics-Hub** (Startseite).

## 2. Daten erzeugen und hochladen (15 min)

1. Im Projektordner die Pipeline laufen lassen: `uv run python src/run_pipeline.py`
2. In Qlik: **Hinzufügen (+) → Datensatz → Datendatei hochladen** und diese sechs Dateien aus
   `data/processed/qlik/` in den persönlichen Bereich hochladen:
   `stores.csv`, `sales.csv`, `plan.csv`, `weather.csv`, `district_commentary.csv`, `dq_report.csv`

   Alternativ geht das später auch direkt im Datenladeeditor (rechte Seitenleiste → *DataFiles* → Hochladen).

## 3. App anlegen und Daten laden (30 min)

1. **Hinzufügen (+) → Analytics-App** → Name: `Vertriebscontrolling Filialen` → *Erstellen*.
2. In der App oben **„Daten vorbereiten“ → „Datenladeeditor“** öffnen.
3. Den gesamten Inhalt aus [`qlik/load_script.qvs`](../qlik/load_script.qvs) in den Abschnitt
   *Main* einfügen (vorhandenen Inhalt ersetzen).
   Die Zeilen `///$tab ...` sind nur Kommentare. Wer möchte, legt für jeden `$tab`-Block einen eigenen
   Abschnitt an (links **+**), das macht das Skript übersichtlicher.
4. **„Daten laden“** (oben rechts) klicken. Nach ca. 30 Sekunden erscheint *„Datenladen
   erfolgreich abgeschlossen“* mit rund 858.000 Zeilen in der Faktentabelle.
5. **Prüfen:** Menü *Daten vorbereiten* → **„Datenmodellanzeige“**. Erwartet werden 6 Tabellen
   (Filialen, Fakten, Kalender, Wetter, Bezirkskommentare, Datenqualitaet) und
   **keine synthetischen Schlüssel** (das wären Tabellen namens `$Syn`).

> **Fehler beim Laden?** Häufigste Ursache: falscher Pfad. Steht im Datenladeeditor rechts unter
> *Datenverbindungen* eine andere Verbindung als `DataFiles`, oben im Skript `vPfad` anpassen.

## 4. Master-Elemente anlegen (60 min)

Master-Elemente sind zentral definierte Dimensionen und Kennzahlen, die jeder im Team gleich
verwendet. Das ist die Grundlage für ein **standardisiertes Berichtswesen**.

Öffnen: Arbeitsblatt bearbeiten → linke Leiste → **Master-Elemente**.

### Dimensionen

| Name | Typ | Felder |
|---|---|---|
| Vertriebsstruktur | **Drilldown** | Region → Bundesland → Bezirk → Filiale |
| Zeit | **Drilldown** | Jahr → Jahresmonat → Datum |
| Filialtyp | Einzeln | Filialtyp |

### Kennzahlen

Die Formeln nutzen Variablen aus dem Ladeskript (Abschnitt *Variablen*). Beispiel:
`$(vUmsatzAJ)` wird beim Rechnen ersetzt durch
`Sum({<Jahr={2015}, MonatNr={"<=7"}, Monat=, Quartal=, Jahresmonat=, Datum=, KW=>} Umsatz)`,
also durch „Umsatz im aktuellen Jahr von Januar bis zum letzten Ist-Monat“.

| Name | Formel | Zahlenformat |
|---|---|---|
| Umsatz YTD | `$(vUmsatzAJ)` | Geld, `#.##0 €` |
| Plan YTD | `$(vPlanAJ)` | Geld, `#.##0 €` |
| Abw. Plan % | `$(vUmsatzAJ) / $(vPlanAJ) - 1` | Benutzerdefiniert `+0,0%;-0,0%` |
| Umsatz VJ % (LfL) | `$(vUmsatzLfLAJ) / $(vUmsatzLfLVJ) - 1` | `+0,0%;-0,0%` |
| Kunden VJ % (LfL) | `$(vKundenLfLAJ) / $(vKundenLfLVJ) - 1` | `+0,0%;-0,0%` |
| Ø-Bon YTD | `$(vUmsatzAJ) / $(vKundenAJ)` | Geld, `#.##0,00 €` |
| Ø-Bon VJ % (LfL) | `($(vUmsatzLfLAJ) / $(vKundenLfLAJ)) / ($(vUmsatzLfLVJ) / $(vKundenLfLVJ)) - 1` | `+0,0%;-0,0%` |
| Umsatz VJ % (naiv) | `$(vUmsatzAJ) / $(vUmsatzVJ) - 1` | `+0,0%;-0,0%` |
| Umsatz je Filialtag | `Sum(Umsatz) / Sum(Filialtag)` | `#.##0 €` |
| Promo-Uplift % | `(Sum({<PromoFlag={1}>} Umsatz) / Sum({<PromoFlag={1}>} Filialtag)) / (Sum({<PromoFlag={0}>} Umsatz) / Sum({<PromoFlag={0}>} Filialtag)) - 1` | `+0,0%;-0,0%` |

**Ampelfarbe** (für Tabellen und Balken: *Darstellung → Farben → Nach Ausdruck*):

```
If($(vUmsatzAJ) / $(vPlanAJ) - 1 >= 0, $(vFarbeGruen),
If($(vUmsatzAJ) / $(vPlanAJ) - 1 >= -0.02, $(vFarbeGelb), $(vFarbeRot)))
```

### Kontrollwerte

Ohne Auswahl müssen die Kennzahlen diese Werte zeigen (berechnet mit SQL aus derselben Datenbank).
Weicht etwas ab, ist eine Formel falsch:

| Kennzahl | Sollwert |
|---|---|
| Umsatz YTD | 1.389.499.643 € |
| Plan YTD | 1.398.497.084 € |
| Abw. Plan % | −0,6 % |
| Umsatz VJ % (LfL) | +3,3 % |
| Kunden VJ % (LfL) | −0,4 % |
| Ø-Bon VJ % (LfL) | +3,7 % |
| Ø-Bon YTD | 9,42 € |
| Umsatz VJ % (naiv) | +5,8 % |
| Promo-Uplift % | +38,8 % |

## 5. Arbeitsblätter (3–4 Stunden)

Allgemein: Arbeitsblatt anlegen → **Arbeitsblatt bearbeiten** → Objekte aus der linken Leiste ins
Raster ziehen → Dimension/Kennzahl aus den Master-Elementen zuweisen.
Oben auf jedes Blatt ein **Filterfenster** mit *Region, Bundesland, Bezirk, Filialtyp*.

### Blatt 1 – Vertriebsleitung: „Wo stehen wir?“

| Objekt | Inhalt |
|---|---|
| 5 × **KPI** | Umsatz YTD (zweite Kennzahl: Abw. Plan %), Umsatz VJ % (LfL), Kunden VJ % (LfL), Ø-Bon VJ % (LfL), Ø-Bon YTD |
| **Kombidiagramm** | Dimension *Monat*; Balken: `Sum({<Jahr={$(vAktJahr)}, Datenart={'Ist'}>} Umsatz)` (Ist), Linie: `Sum({<Jahr={$(vAktJahr)}>} Planumsatz)` (Plan), Linie: `Sum({<Jahr={$(vVorJahr)}, LfL_FJ={1}>} Umsatz)` (Vorjahr) |
| **Balkendiagramm** | Dimension *Vertriebsstruktur* (Drilldown), Kennzahl *Abw. Plan %*, Farbe = Ampelausdruck, sortiert aufsteigend |
| **Text & Bild** | Kernaussage als Text: *„Wachstum kommt nur aus dem Bon (+3,7 %), die Kundenfrequenz sinkt (−0,4 %).“* |

### Blatt 2 – Außendienst: „Welche Filialen besuche ich zuerst?“

| Objekt | Inhalt |
|---|---|
| **Tabelle** Bezirke | Dimension *Bezirk*; Kennzahlen Umsatz YTD, Abw. Plan % (Hintergrundfarbe = Ampel), Umsatz/Kunden/Ø-Bon VJ % (LfL) |
| **Tabelle** Filialen | Dimension *Filiale*, *Filialtyp*; Kennzahlen Umsatz YTD, Abw. Plan %, Kunden VJ % (LfL); sortiert nach Abw. Plan % aufsteigend |
| **Tabelle** Kommentar | Dimension *Bezirkskommentar*, *Kommentar Quelle* (erscheint sinnvoll, sobald ein Bezirk ausgewählt ist) |

Tipp: Bei der Kommentartabelle unter *Add-ons → Datenverarbeitung* die **Berechnungsbedingung**
`GetSelectedCount(Bezirk) = 1` setzen und als Meldung „Bitte einen Bezirk auswählen“ eintragen.

### Blatt 3 – Promotion & Einflussfaktoren: „Was treibt den Umsatz?“

| Objekt | Inhalt |
|---|---|
| **Balkendiagramm** | Dimension *Filialtyp*, Kennzahl *Promo-Uplift %* |
| **Balkendiagramm** | Dimension *Wochentag*, Kennzahl *Umsatz je Filialtag* |
| **Balkendiagramm** | Dimension *Wettbewerber Nähe*, Kennzahlen *Umsatz je Filialtag* und `Sum(Umsatz)/Sum(Kunden)` (Ø-Bon) |
| **Balkendiagramm** | Dimension *Wetterlage*, Kennzahl *Umsatz je Filialtag* |
| **Text & Bild** | Handlungsempfehlungen (siehe README, Abschnitt Ergebnisse) |

### Blatt 4 – Datenqualität: „Können wir den Zahlen trauen?“

| Objekt | Inhalt |
|---|---|
| **KPI** | `Count({<[DQ Status]={'Auffällig'}>} [DQ Regel])` → Anzahl auffälliger Prüfregeln |
| **Tabelle** | alle Felder *DQ ...* |
| **Balkendiagramm** | Dimension *Bundesland*, Kennzahlen *Umsatz VJ % (naiv)* und *Umsatz VJ % (LfL)* → zeigt, warum Bayern ohne Bereinigung falsch aussieht |

## 6. Abschluss (30 min)

1. Jedes Blatt im Ansichtsmodus aufrufen und einen **Screenshot** machen
   (`docs/screenshots/01_vertriebsleitung.png`, `02_aussendienst.png`, `03_einflussfaktoren.png`, `04_datenqualitaet.png`).
2. Optional: **Storytelling** (oben „Story“) mit drei Folien als Präsentation fürs Vorstellungsgespräch.
3. Die App exportieren (App-Übersicht → ⋯ → *Herunterladen*, ohne Daten) und als
   `qlik/Vertriebscontrolling_Filialen.qvf` ins Repo legen.

---

## Spickzettel fürs Gespräch

- **Warum verkettete Faktentabelle?** Ist (Tag) und Plan (Monat) haben verschiedene Granularität.
  Zwei Faktentabellen mit gemeinsamen Feldern (Filiale, Datum) würden einen synthetischen Schlüssel
  erzeugen. Verkettet gibt es eine Tabelle, ein Feld *Datenart* und einen Kalender.
- **Warum ApplyMap statt Join?** Mapping ist schneller, verändert die Zeilenzahl nie und lässt einen
  Standardwert für fehlende Treffer zu (`'?'`).
- **Warum Masterkalender?** Lückenlose Datumsreihe auch für Tage ohne Umsatz, einheitliche
  Zeitfelder (Jahr, Monat, KW) für alle Fakten.
- **Set Analysis:** `{<Jahr={2015}, Monat=>}` = „rechne für 2015, ignoriere eine Monatsauswahl“.
  Entspricht `CALCULATE` mit `REMOVEFILTERS` in DAX.
- **Like-for-Like:** Vorjahresvergleich nur über Filialmonate, die in beiden Jahren Daten haben.
  Ohne das sieht Bayern 2015 nach +22,9 % aus, tatsächlich sind es +4,0 %.
