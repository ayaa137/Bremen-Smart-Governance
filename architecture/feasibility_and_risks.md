# Feasibility and risks

The current 79-by-3 analytical matrix is small enough for an ordinary laptop. Local batch Python is adequate; cloud scale, edge computing, 5G and LoRaWAN are not necessary to calculate these methods. Hosting choices should follow municipal operating, accessibility, procurement and data-governance requirements rather than infrastructure novelty.

| Risk | Evidence / consequence | Proposed control |
| --- | --- | --- |
| Release freshness | Statistics end in 2024 for baseline; not 2026 observations | Display reporting year and retrieval date separately; check each publisher release schedule |
| Boundary and definition changes | Full crosswalk absent; 2009 code change documented; SGB II policy reform | Version definitions and boundaries; block longitudinal outputs until verified |
| Coverage bias | Nine workbook Ortsteile excluded from primary scoring | Display excluded areas; investigate missing values and small denominators before allocation |
| Correlated indicators | Labour-market indicators overlap | Domain-balanced weights, omission checks, visible correlations; review wider deprivation dimensions |
| Small-area privacy | Aggregate source data; denominator counts absent | Retain suppression, assess small-cell disclosure, prohibit individual inference; do not infer missing counts |
| Stigmatization | Neighborhood labels could be misread as resident attributes | Nominal cluster labels, careful language, local consultation, no identity-based scoring |
| Explainability | Index is compensatory; TOPSIS distance choices affect ranks | Publish formulas, weights, trace tables, scenarios, provenance and caveats |
| Security | Proposed network/database/application enlarge exposure | HTTPS/TLS, least privilege, secret management, patches, access logs and backups |
| Maintenance | XLS layout or labels can change | Schema tests, hashes, dependency records, validation gates, change review, named municipal maintainer |
| Unsupported impact | No intervention outcomes or emissions/cost data | Evaluate impacts only in a future controlled operational study; no fabricated savings or fairness gains |

Proposed refresh process: check releases on a configurable schedule (frequency not yet known); acquire immutable copy; log licence/version and hash; run automated gates; review schema/boundary changes; rerun methods and robustness; compare release outputs; obtain human publication review; retain prior releases; rollback by selecting an earlier validated release. Operating costs and staffing cannot be quantified without deployment requirements.

This repository provides exploratory evidence and a blueprint, not an operational allocation system. Denominator and sampling uncertainty, within-year reference dates, income timeliness, and broader dimensions of deprivation require further work. Public aggregate data still warrants disclosure and fairness review in its intended deployment context.
