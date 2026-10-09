# Components and interfaces

| Component | Current implementation | Proposed production responsibility |
| --- | --- | --- |
| Source inventory | Original files; analysis/source_manifest.csv | Read-only release snapshots with acquisition time, publisher, licence, checksum and original reference dates |
| Preparation | src/prepare_data.py | Parse source formats; retain raw values and missing markers; append releases instead of overwriting history |
| Audit and analytical dataset | src/build_analysis_dataset.py | Enforce units, ranges, coverage, uniqueness, geographic level and common reporting year; produce gated dataset |
| Scoring | src/composite_index.py, src/topsis.py | Immutable run configuration and release-specific scores; never score incomplete rows |
| Profiling | src/clustering.py | Standardization, selected k, diagnostics, nominal profiles, seed and stability metadata |
| Robustness | src/sensitivity_analysis.py | Store weight/feature scenarios alongside baseline; expose rank movement |
| Presentation | notebooks, results figures, group PDFs | Proposed read-only dashboard and audited exports; no automated individual eligibility decisions |
| Storage | Local CSV/JSON/PNG/PDF | PostgreSQL plus immutable object store; backups, access controls and tested restore |

Proposed database entities: source_release(release_id, sha256, source_url, licence, acquired_at); geography(geo_code, level, name, valid_from, valid_to); indicator_definition(indicator_id, version, unit, numerator, denominator, direction); observation(release_id, geo_code, indicator_id, reporting_period, value, status); analysis_run(run_id, release_id, method, configuration, software_versions, gate_status); result(run_id, geo_code, score_or_profile). Exact schema and hosting require municipal requirements review. Reject duplicate observations; maintain versioned boundary crosswalks separately.

Proposed API responses include release_id, reporting_period, geo_level, covered_n, excluded_n, method_version, weight vector and limitations. Server-side scenario calculation must use the validated matrix and consistent row set. Public read access can be separate from authenticated publishing/admin access. No cloud, database, network acquisition, API or dashboard is currently deployed.
