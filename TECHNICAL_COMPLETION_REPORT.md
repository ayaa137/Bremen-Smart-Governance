# Technical completion report

Data-Driven Smart Governance: A Comparative Evaluation of Methods for Identifying Socioeconomic Inequalities Across Bremen's Neighborhoods.

Scope: reproducible technical evidence and proposed architecture. No final university report sections, slides, interactive application or GitHub push. Course MSCM-CO-08; Track 4; Bremen Ortsteile. Exact confirmed questions appear in group_results/OVERVIEW.md.

## Completed and verified

All 24 original files reread. Statistical rows reconstructed and compared against existing Phase 1 outputs. In addition, 9152 selected indicator observations were checked directly against original BIFF cells independently of the preparation parser:

| source | records | missing | passed |
| --- | --- | --- | --- |
| excel_ortsteilatlas_long.csv | 316064 | 24355.000 | True |
| csv_district_statistics_long.csv | 15147 | 223.000 | True |
| bremen_data.json | 1515 |  | True |

Six candidates audited; three primary indicators selected: unemployment quotient (higher disadvantage), social-insurance employment share aged 15-under-65 (lower), and SGB II receipt under 65 (higher). Child SGB II receipt is a sensitivity extension; median taxpayer income is separate 2020 context; single parenthood is context only. Exact German names, units, denominators, years and coverage are in analysis/indicator_selection.csv.

Primary annual reporting year: 2024; 79 of 88 workbook Ortsteile (89.8%) included. Nine areas excluded for unavailable labour-market indicators. No imputation, aggregate leakage or mixed-year scores. Income is not carried forward from 2020.

Implemented: directed min-max equal-weight composite, vector-normalized equal-weight TOPSIS, standardized K-means with diagnostics and initialization/bootstrap stability; ranking comparison, declared weight/feature robustness and readable visualizations. Architecture documents mark implemented local pipeline versus proposed municipal deployment. Four section packages include evidence guides, tables, figures and readable PDFs. Eight notebooks execute from fresh kernels. Scripts run through the pipeline; persisted calculations, source hashes, score directions, inputs/coverage, figures and notebook execution are checked in analysis/output_verification.csv (46 passed checks).

## Verified findings

Highest composite score areas: Ohlenhof, Gröpelingen, Grohn, Blumenthal, Lindenhof. Highest TOPSIS disadvantage closeness: Ohlenhof, Gröpelingen, Blumenthal, Lindenhof, Tenever. Rank Spearman 0.9743, Kendall tau-b 0.8832; these are within-sample agreement metrics, not truth validation. K-means returns 2 nominal profiles; profile statistics and stability are exported. Actual descriptive ranges, score values, rank differences and sensitivity findings are in results/; no causal or policy-impact claims.

## Gates and remaining work

PASS: source reconstruction, unique Ortsteil IDs, geographic level, three defensible partial-disadvantage criteria, percentage ranges/units, complete-case annual scoring, coverage threshold, method directions and shared inputs. Primary gate passes for exploratory annual comparison only. BLOCKED: historical change claims. Conditional/unverified: source reference dates and full operational suitability.

Historical change estimates remain incomplete: time-stable boundaries and definitions are not verified. Historical tables and separate 2020 income context are review artifacts only. Exact within-year reference dates, revisions and denominator counts remain unavailable. Operational allocation suitability and full multidimensional disadvantage are not validated.

Group members must add real academic references and external benchmarks, verify municipal metadata/boundary history, discuss indicator/weight choices and coverage with stakeholders, supply broader indicators if needed, and independently write report/presentation sections. The architecture remains a blueprint. No economic, ecological or social intervention outcome has been measured.

## Files and reproduction

Start with group_results/OVERVIEW.md and your section's evidence_summary.pdf. Review docs/REPRODUCING.md; run notebooks 01-08 in order. Run python src/run_technical_pipeline.py, python src/create_notebooks.py, then python src/verify_outputs.py. Exact tested package versions are in docs/environment_versions.json. docs/deliverable_manifest.json lists deliverables, modified existing files and preserved sources; original sources and Phase 1 preparation/output files are retained. requirements.txt is the only existing dependency file modified.

This completes the defensible cross-sectional technical foundation and independent architecture/package work. It does not complete the blocked longitudinal validation or the group's final academic submission.
