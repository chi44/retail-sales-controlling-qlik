-- Star-Schema Vertriebscontrolling (SQLite)
--
--            dim_date ──┐
--                       ├──< fact_sales     (Tag x Filiale, Ist)
--  dim_store ───────────┤
--   (Region, Bezirk)    ├──< fact_plan      (Monat x Filiale, Plan 2015)
--                       │
--  dim_store.state_code ┴──< fact_weather   (Tag x Bundesland, aus Open-Meteo-API)
--
--  dq_report: Ergebnis der Datenqualitätsprüfungen des letzten Pipeline-Laufs

DROP TABLE IF EXISTS fact_sales;
DROP TABLE IF EXISTS fact_plan;
DROP TABLE IF EXISTS fact_weather;
DROP TABLE IF EXISTS dim_store;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dq_report;

CREATE TABLE dim_store (
    store_id               INTEGER PRIMARY KEY,
    store_name             TEXT    NOT NULL,
    store_type             TEXT    NOT NULL,
    assortment             TEXT    NOT NULL,
    state_code             TEXT    NOT NULL,
    state_name             TEXT    NOT NULL,
    region                 TEXT    NOT NULL,
    district               TEXT    NOT NULL,
    competition_distance_m REAL,
    competition_open_date  TEXT,
    promo2                 INTEGER NOT NULL,
    promo2_since_week      INTEGER,
    promo2_since_year      INTEGER,
    promo_interval         TEXT,
    state_ambiguous        INTEGER NOT NULL,
    missing_days           INTEGER NOT NULL,
    has_data_gap           INTEGER NOT NULL
);

CREATE TABLE dim_date (
    date        TEXT    PRIMARY KEY,   -- ISO-Format YYYY-MM-DD
    year        INTEGER NOT NULL,
    month       INTEGER NOT NULL,
    year_month  TEXT    NOT NULL,      -- YYYY-MM
    iso_week    INTEGER NOT NULL,
    weekday_no  INTEGER NOT NULL,      -- 1 = Montag
    weekday     TEXT    NOT NULL
);

CREATE TABLE fact_sales (
    store_id       INTEGER NOT NULL REFERENCES dim_store (store_id),
    date           TEXT    NOT NULL REFERENCES dim_date (date),
    sales          INTEGER NOT NULL,
    customers      INTEGER NOT NULL,
    promo          INTEGER NOT NULL,
    state_holiday  TEXT    NOT NULL,
    school_holiday INTEGER NOT NULL,
    is_outlier     INTEGER NOT NULL,
    lfl_prev_year  INTEGER NOT NULL,
    lfl_next_year  INTEGER NOT NULL,
    PRIMARY KEY (store_id, date)
);

CREATE TABLE fact_plan (
    store_id       INTEGER NOT NULL REFERENCES dim_store (store_id),
    month_start    TEXT    NOT NULL,   -- erster Tag des Planmonats
    plan_sales     REAL    NOT NULL,
    plan_customers REAL    NOT NULL,
    plan_basis     TEXT    NOT NULL,
    PRIMARY KEY (store_id, month_start)
);

CREATE TABLE fact_weather (
    state_code       TEXT NOT NULL,
    date             TEXT NOT NULL REFERENCES dim_date (date),
    temp_mean_c      REAL,
    precipitation_mm REAL,
    PRIMARY KEY (state_code, date)
);

CREATE TABLE dq_report (
    rule_id       TEXT    PRIMARY KEY,
    "table"       TEXT    NOT NULL,
    "check"       TEXT    NOT NULL,
    affected_rows INTEGER NOT NULL,
    status        TEXT    NOT NULL,
    action        TEXT    NOT NULL
);

CREATE INDEX idx_sales_date ON fact_sales (date);
