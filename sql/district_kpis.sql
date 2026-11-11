-- Kennzahlen je Außendienst-Bezirk für das laufende Jahr bis zum letzten Datenmonat (YTD).
-- Grundlage für die automatische Kommentierung (src/commentary.py).
--
-- Parameter :year = Berichtsjahr, :max_month = letzter Monat mit Ist-Daten
-- Vorjahresvergleich flächenbereinigt (Like-for-Like): nur Filialmonate mit Daten in beiden Jahren.

WITH ist AS (
    SELECT s.district, s.region,
           SUM(f.sales)                                                      AS sales,
           SUM(CASE WHEN f.lfl_prev_year = 1 THEN f.sales END)               AS sales_lfl,
           SUM(CASE WHEN f.lfl_prev_year = 1 THEN f.customers END)           AS customers_lfl,
           SUM(CASE WHEN f.promo = 1 THEN f.sales END) * 1.0 / SUM(f.sales)  AS promo_share
    FROM fact_sales f
    JOIN dim_store s USING (store_id)
    JOIN dim_date d USING (date)
    WHERE d.year = :year AND d.month <= :max_month
    GROUP BY s.district, s.region
),
vorjahr AS (
    SELECT s.district,
           SUM(f.sales)     AS sales_lfl_py,
           SUM(f.customers) AS customers_lfl_py
    FROM fact_sales f
    JOIN dim_store s USING (store_id)
    JOIN dim_date d USING (date)
    WHERE d.year = :year - 1 AND d.month <= :max_month AND f.lfl_next_year = 1
    GROUP BY s.district
),
plan AS (
    SELECT s.district, SUM(p.plan_sales) AS plan_sales
    FROM fact_plan p
    JOIN dim_store s USING (store_id)
    WHERE CAST(strftime('%Y', p.month_start) AS INTEGER) = :year
      AND CAST(strftime('%m', p.month_start) AS INTEGER) <= :max_month
    GROUP BY s.district
),
filialen AS (
    -- Plan-Abweichung je Filiale, um auffällige Filialen im Bezirk zu benennen
    SELECT s.district, s.store_name,
           SUM(f.sales) * 1.0 / MAX(p.plan_sales) - 1 AS plan_dev
    FROM fact_sales f
    JOIN dim_store s USING (store_id)
    JOIN dim_date d USING (date)
    JOIN (SELECT store_id, SUM(plan_sales) AS plan_sales
          FROM fact_plan
          WHERE CAST(strftime('%m', month_start) AS INTEGER) <= :max_month
            AND CAST(strftime('%Y', month_start) AS INTEGER) = :year
          GROUP BY store_id) p USING (store_id)
    WHERE d.year = :year AND d.month <= :max_month
    GROUP BY s.district, s.store_name
),
rangfolge AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY district ORDER BY plan_dev ASC)  AS rang_schwach,
           ROW_NUMBER() OVER (PARTITION BY district ORDER BY plan_dev DESC) AS rang_stark,
           COUNT(*)     OVER (PARTITION BY district)                        AS n_stores
    FROM filialen
)
SELECT i.district,
       i.region,
       r_schwach.n_stores,
       i.sales,
       p.plan_sales,
       i.sales * 1.0 / p.plan_sales - 1                              AS plan_dev,
       i.sales_lfl * 1.0 / v.sales_lfl_py - 1                        AS sales_lfl_yoy,
       i.customers_lfl * 1.0 / v.customers_lfl_py - 1                AS customers_lfl_yoy,
       (i.sales_lfl * 1.0 / i.customers_lfl)
         / (v.sales_lfl_py * 1.0 / v.customers_lfl_py) - 1           AS avg_basket_lfl_yoy,
       i.promo_share,
       r_schwach.store_name                                          AS weakest_store,
       r_schwach.plan_dev                                            AS weakest_store_plan_dev,
       r_stark.store_name                                            AS strongest_store,
       r_stark.plan_dev                                              AS strongest_store_plan_dev
FROM ist i
JOIN vorjahr v USING (district)
JOIN plan p USING (district)
JOIN rangfolge r_schwach ON r_schwach.district = i.district AND r_schwach.rang_schwach = 1
JOIN rangfolge r_stark   ON r_stark.district   = i.district AND r_stark.rang_stark = 1
ORDER BY plan_dev;
