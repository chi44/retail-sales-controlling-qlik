# Store Sales Controlling Cockpit (Qlik Sense)

*[Deutsche Version](README.md)*

Portfolio project: a steering cockpit for sales management and area managers of a drugstore
chain, built on real daily sales data from **1,115 Rossmann stores (2013–2015)**. It covers the
full chain from data preparation, data quality checks and data modelling to a Qlik Sense
dashboard with recommendations for action, plus AI-generated district commentary.

**Tools:** Qlik Sense (load script, set analysis, master items) · Python (pandas) ·
SQL (SQLite, CTEs, window functions) · REST API (Open-Meteo) · Claude API · uv · Git

## Key findings (Jan–Jul 2015 vs. Jan–Jul 2014)

1. **Growth comes from basket size only, footfall is declining.** Like-for-like sales +3.3 %,
   driven entirely by average basket (+3.7 %). Customer count −0.4 %.
   → Focus measures on footfall and prioritise districts with the steepest customer decline.
2. **Slightly below plan (−0.6 %).** Only region North is ahead of plan. 41 of 60 districts are behind.
3. **Promotions drive footfall.** Promo days generate +38.8 % sales per store, most of all in
   store type A (+43 % sales, +26 % customers). This makes promotions the most direct lever for finding 1.
4. **Continuous promotion ("Promo2") shows no measurable benefit.** Participating stores sell 11 % less
   per day. This is likely a selection effect, so test it with a control group before scaling up.
5. **Stores close to a competitor are city-centre stores:** highest sales, smallest basket
   (€8.05 vs. €10.38). Lift basket size with secondary placements and checkout zones.
6. **Weather has hardly any effect** (−0.9 % on rainy days, weather data from an API), so it is
   not a relevant planning factor.

## Data quality highlight

All 180 Bavarian stores have **no data for Jul–Dec 2014**. Without a like-for-like comparison,
2014 looks like a −5.3 % decline (actual: +2.8 %), and Bavaria in 2015 looks like +22.9 %
(actual: +4.0 %). Twelve data quality rules run on every pipeline execution, and their results are
shown in the dashboard.

## Data model in Qlik

Star schema with a **concatenated fact table** (daily actuals + monthly plan, field `Datenart`),
a master calendar, a weather table linked by a composite key built with `ApplyMap`, and
KPI definitions stored as variables and master measures. The variables and master measures are the
foundation for standardised reporting across countries.

## AI commentary

For each district, `src/commentary.py` produces a three-sentence comment covering position,
driver and recommended action. All figures are computed in SQL. The language model only phrases
them, following a prompt with explicit rules, so it cannot invent numbers. Without an API key,
a rule-based fallback is used, and the dashboard shows which source produced each comment.

## Note

The area-manager districts and the 2015 plan figures are **simulated**. Data sources, setup
and details are in the [German README](README.md). The step-by-step Qlik guide is in
[`docs/qlik_anleitung.md`](docs/qlik_anleitung.md).
