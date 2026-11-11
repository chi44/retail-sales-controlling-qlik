-- Analysen für die Kernaussagen im README und im Dashboard.
-- Ausführen: sqlite3 -header -column data/processed/sales.db < sql/analysen.sql

-- 1. Warum ein flächenbereinigter Vorjahresvergleich nötig ist:
--    naiver Jahresvergleich vs. Like-for-Like (nur Filialmonate mit Daten in beiden Jahren)
SELECT 'naiv 2014 vs 2013' AS vergleich,
       ROUND(100.0 * SUM(CASE WHEN d.year = 2014 THEN f.sales END)
                   / SUM(CASE WHEN d.year = 2013 THEN f.sales END) - 100, 1) AS wachstum_pct
FROM fact_sales f JOIN dim_date d USING (date)
UNION ALL
SELECT 'Like-for-Like 2014 vs 2013',
       ROUND(100.0 * SUM(CASE WHEN d.year = 2014 AND f.lfl_prev_year = 1 THEN f.sales END)
                   / SUM(CASE WHEN d.year = 2013 AND f.lfl_next_year = 1 THEN f.sales END) - 100, 1)
FROM fact_sales f JOIN dim_date d USING (date);

-- 2. Promo-Uplift: Umsatz je Filialtag mit vs. ohne Aktion, nach Filialtyp
SELECT s.store_type                                                AS filialtyp,
       ROUND(AVG(CASE WHEN f.promo = 1 THEN f.sales END))          AS umsatz_tag_promo,
       ROUND(AVG(CASE WHEN f.promo = 0 THEN f.sales END))          AS umsatz_tag_ohne,
       ROUND(100.0 * AVG(CASE WHEN f.promo = 1 THEN f.sales END)
                   / AVG(CASE WHEN f.promo = 0 THEN f.sales END) - 100, 1) AS uplift_pct,
       ROUND(100.0 * AVG(CASE WHEN f.promo = 1 THEN f.customers END)
                   / AVG(CASE WHEN f.promo = 0 THEN f.customers END) - 100, 1) AS uplift_kunden_pct
FROM fact_sales f JOIN dim_store s USING (store_id)
GROUP BY s.store_type
ORDER BY uplift_pct DESC;

-- 3. Dauerpromotion (Promo2): bringt die Teilnahme mehr Umsatz je Filialtag?
SELECT CASE s.promo2 WHEN 1 THEN 'mit Dauerpromo' ELSE 'ohne Dauerpromo' END AS gruppe,
       COUNT(DISTINCT s.store_id)    AS filialen,
       ROUND(AVG(f.sales))           AS umsatz_je_tag,
       ROUND(AVG(f.customers))       AS kunden_je_tag
FROM fact_sales f JOIN dim_store s USING (store_id)
GROUP BY s.promo2;

-- 4. Wetter (API-Daten): Umsatz je Filialtag an Regentagen vs. trockenen Tagen, Mo-Sa
SELECT CASE WHEN w.precipitation_mm >= 5 THEN 'Regen (>= 5 mm)'
            WHEN w.precipitation_mm >= 1 THEN 'leichter Regen'
            ELSE 'trocken' END       AS wetterlage,
       COUNT(*)                      AS filialtage,
       ROUND(AVG(f.sales))           AS umsatz_je_tag,
       ROUND(AVG(f.customers))       AS kunden_je_tag
FROM fact_sales f
JOIN dim_store s USING (store_id)
JOIN dim_date d USING (date)
JOIN fact_weather w ON w.state_code = s.state_code AND w.date = f.date
WHERE d.weekday_no <= 6
GROUP BY wetterlage
ORDER BY umsatz_je_tag DESC;

-- 5. Wettbewerbsnähe: Umsatz je Filialtag nach Entfernung zum nächsten Wettbewerber
SELECT CASE WHEN s.competition_distance_m IS NULL THEN 'unbekannt'
            WHEN s.competition_distance_m <= 500   THEN '1) bis 500 m'
            WHEN s.competition_distance_m <= 2000  THEN '2) 500 m - 2 km'
            WHEN s.competition_distance_m <= 10000 THEN '3) 2 - 10 km'
            ELSE '4) über 10 km' END AS entfernung,
       COUNT(DISTINCT s.store_id)    AS filialen,
       ROUND(AVG(f.sales))           AS umsatz_je_tag,
       ROUND(AVG(f.sales * 1.0 / f.customers), 2) AS durchschnittsbon
FROM fact_sales f JOIN dim_store s USING (store_id)
GROUP BY entfernung
ORDER BY entfernung;

-- 6. Wochentagsprofil (Index: Durchschnitt Mo-Sa = 100)
WITH tag AS (
    SELECT d.weekday_no, d.weekday, AVG(f.sales) AS umsatz
    FROM fact_sales f JOIN dim_date d USING (date)
    GROUP BY d.weekday_no, d.weekday
)
SELECT weekday AS wochentag,
       ROUND(100 * umsatz / (SELECT AVG(umsatz) FROM tag WHERE weekday_no <= 6)) AS index_umsatz
FROM tag
ORDER BY weekday_no;
