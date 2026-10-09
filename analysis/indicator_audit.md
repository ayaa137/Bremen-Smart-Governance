# Indicator audit and selection decisions

Six candidates are audited in indicator_selection.csv; per-year counts and missingness appear in coverage_summary.csv. Three enter the 2024 baseline: unemployment quotient (higher), social-insurance employment participation (lower), and SGB II receipt under 65 (higher). These measure related but distinct labour-market and material-support conditions. They are correlated; equal weights assign two-thirds of baseline weight to labour-market measures. Domain-balanced weights and indicator-removal scenarios test that decision.

Child benefit receipt is an optional sensitivity variable, not independent baseline evidence. Median taxable income is useful for 2020 context only. Single parenthood describes service needs but is not a defensible intrinsic disadvantage score. Age composition, nationality, migration status, car ownership, housing tenure and rent are not scored: their disadvantage direction is ambiguous or their populations/years are incompatible. School transition indicators need residence/denominator and reference-period checks before inclusion. No demographic identity is treated as deprivation.

Income unit inference in Phase 1 missed the parenthesized unit because the title ends with ': Median'; this analysis explicitly uses 1000 EUR from the original heading. Other six candidate units are verified against headings. Source headings establish denominators; exact observation dates and revisions remain unavailable.

All 24 sources were independently reread; source_audit.csv records equality against the existing cleaned statistical files. The JSON catalogue is separate. Historical CSVs are not joined to Excel measurements. Überseestadt / Ueberseestadt is a name alias for code 437, documented in geographic_alias_audit.csv; this does not establish historical compatibility. The official 2011 yearbook documents conversion of Handelshäfen to code 437 in 2009. Full boundary history remains unverified.

Sources and checked external context: see docs/source_notes.md. The latest municipal atlas web page could not be opened (403), so current detailed definitions were not silently assumed verified.
