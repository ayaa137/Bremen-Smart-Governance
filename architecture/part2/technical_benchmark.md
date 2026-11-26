# Bremen Smart Governance · Technical benchmark

**Use static Python-generated HTML for the student prototype.** It fits the verified 2024-v1 release, supports an offline presentation, and carries the evidence and its limitations in a reproducible bundle. Streamlit is a workable alternative for a more interactive demonstration. A custom API and database become relevant if a municipality confirms a need for authenticated workflows, cross-release queries, or programmatic clients.

## Requirements derived from the project

The benchmark uses the [Part 2 architecture](four_layer_architecture.md) and the [2024-v1 release manifest](releases/2024-v1/manifest.json) at source commit `fa2c6e2`. These are project acceptance criteria. Municipal service levels, operating arrangements, and access policies still need confirmation.

| Type | Requirement and acceptance check |
| --- | --- |
| Functional · neighborhood comparison | Make all 88 Ortsteile findable by code or name. Show the two saved ranks separately, use nominal K-means labels, and explain why nine areas lack scores. Preserve text identifiers, year, units, and blank values. |
| Functional · supporting evidence | Show the saved housing benchmark for the 79 covered areas, with the plot and a text equivalent. Present both Moran’s I settings as release-level results. Label all five fieldwork candidates as proposed and unvisited. |
| Functional · evidence and review | Expose the release ID, sources, methods, and coverage. The reviewed release CSVs are available in the repository. Dashboard download controls remain pending. People review any intervention choices. A future pilot would define a baseline, outcome, and review date before it starts. |
| Nonfunctional · reproducibility and interoperability | Pin the release and inputs by ID and hash. Recreate the same view from saved files, with no scoring runs. Keep CSV exports usable independently of the interface. |
| Nonfunctional · accessibility and transparency | Test keyboard navigation, labels, focus, zoom, contrast, and screen-reader table navigation. Provide a useful text alternative for the chart and convey missingness without color alone. WCAG 2.2 is a technical reference for these checks. [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/) |
| Nonfunctional · privacy and security | Serve reviewed aggregates only. Preserve source suppression, avoid unnecessary telemetry, and keep identifiable fieldwork outside the publication bundle. Apply least privilege to publishing and use HTTPS for a hosted version. |
| Nonfunctional · maintenance and growth | Document build, release review, rollback, and ownership. Measure deployment behavior against agreed needs before adding services or setting capacity targets. |

## Options and documented characteristics

- **A · Static Python-generated HTML.** Build semantic HTML from the CSVs, embed the saved PNG, and add modest client-side search and filtering. Generate the data view at build time for an offline bundle. The format can support downloadable files in a future version. Python supplies HTML escaping, and HTML table headers and captions can express information to assistive technologies. [Python HTML support](https://docs.python.org/3.13/library/html.html) · [W3C WAI tables](https://www.w3.org/WAI/tutorials/tables/)
- **B · Streamlit.** Use Python widgets and the same saved files for comparison and filtering. Streamlit uses a Python server with WebSocket sessions. Widget interaction can rerun the script, and caching can avoid repeated work. A hosted deployment needs compatible infrastructure, pinned dependencies, and widget accessibility checks. [Streamlit architecture](https://docs.streamlit.io/develop/concepts/architecture/architecture) · [Streamlit caching](https://docs.streamlit.io/develop/concepts/architecture/caching)
- **C · Custom API, browser frontend, and database.** A representative design uses FastAPI and PostgreSQL. FastAPI supports OpenAPI and JSON Schema. PostgreSQL provides database roles and backup mechanisms. The project would need to design and operate the public contract, imports, release versioning, migrations, authentication where required, and restore checks. [FastAPI features](https://fastapi.tiangolo.com/features/) · [PostgreSQL roles](https://www.postgresql.org/docs/current/user-manag.html) · [PostgreSQL backup and restore](https://www.postgresql.org/docs/current/backup.html)

## Matrix and sensitivity

The [comparison matrix](technical_benchmark_matrix.csv) defines all 12 criteria and records each rating, rationale, and weight. Scores are **qualitative engineering judgments** for the same read-only scope. Larger scores are more favorable, including lower initial effort, lower operational effort, and simpler hosting.

| Score | Meaning for the criterion |
| --- | --- |
| 1 | Poor fit. Major capability gaps or substantial redesign would be needed. |
| 2 | Weak fit. The capability is achievable with significant extra engineering or dependencies. |
| 3 | Adequate fit. It meets the basic need with material trade-offs. |
| 4 | Strong fit. It meets the need with manageable additional work. |
| 5 | Very strong fit. It meets the need directly under the stated scope. |

The prototype weights prioritize transparency and reproducibility (12% each), since the handoff must be explainable and repeatable from the saved release. Initial complexity and accessibility (10% each), maintenance (9%), and present-scope feasibility (8%) reflect a student deliverable that others should be able to use and maintain. Privacy and security carry 8% each because the evidence concerns small areas. Hosting and interactivity carry 7% each. Interoperability (5%) and scalability (4%) remain relevant with one local snapshot and no confirmed service demand. Initial build effort, ongoing maintenance, runtime infrastructure, and current feasibility are scored separately. Accessibility, disclosure, and publication checks should gate any release regardless of its weighted score.

Each overall score is the sum of criterion score × weight divided by the sum of weights. Equal weighting gives every criterion weight 1. The two stress cases deliberately emphasize a different priority while keeping ratings fixed. They are illustrative priorities, separate from municipal requirements.

| Weight profile | A · Static | B · Streamlit | C · API + database | Highest |
| --- | ---: | ---: | ---: | --- |
| Prototype | **4.55** | 3.73 | 3.28 | A |
| Equal weight | **4.42** | 3.67 | 3.42 | A |
| Interaction stress · 43% interactivity | 3.91 | **4.19** | 3.98 | B |
| API and scale stress · 21% interoperability, 22% scalability | 3.96 | 3.51 | **4.19** | C |

A leads when priorities are balanced or aligned with the student prototype. The reversals show which priorities would change the recommendation. They provide no estimate of future demand or service capacity.

## Local feasibility evidence

Run from the repository root. The probes read saved files and leave the release intact. With `--skip-streamlit`, the checks require only Python’s standard library. The full run used Windows 11, Python 3.13.7, and the already installed Streamlit 1.67.0.

```powershell
python -B architecture/part2/benchmark_checks.py
python -B architecture/part2/benchmark_checks.py --skip-streamlit
```

| Check | Measured result | Scope |
| --- | --- | --- |
| Shared inputs | Both release CSV hashes matched the manifest. Verified 88 unique neighborhood keys, 79 eligible rows with housing, nine exclusions, five unvisited candidates, and two spatial rows. Exact bytes were 21,382 for the neighborhood CSV, 2,502 for the spatial CSV, 1,318 for the manifest, and 312,017 for the housing PNG. | Saved artifact sizes on the test machine. |
| A · HTML fragment | An escaped 88-row table matched the saved records and produced identical 5,839-byte UTF-8 output on two builds. Header structure and the PNG header (3,300 × 2,100) were checked. | Table-fragment size and determinism. Browser and assistive-technology tests remain. |
| B · Streamlit AppTest | The selector loaded all 88 choices. Code `111` displayed its saved composite rank of 47 and excluded code `122` displayed “Missing”. | In-process widget test. Hosting and browser behavior remain untested. [Streamlit AppTest](https://docs.streamlit.io/develop/api-reference/app-testing) |
| C · SQL and JSON probe | SQLite 3.50.4 round-tripped 88 projected rows, rejected a duplicate key, and preserved the excluded area’s reason and JSON null rank. | In-memory stand-in for the data model. PostgreSQL, live API behavior, browser integration, and authentication remain untested. |

The probes exercise different capabilities. They provide no comparable end-to-end timing, concurrent-user capacity, operating cost estimate, or accessibility or security certification. The matrix uses one release and engineering judgment from one review. Hosting, staffing, source refresh, and municipal policies remain open.

## Implementation decision

- **Student prototype.** The [implemented option A](prototype/index.html) pins `2024-v1` and provides a read-only page with neighborhood search, filtering, and a text summary alongside the saved image. The repository holds the release CSVs. Downloadable CSV controls are not yet implemented. Offline delivery supports the demonstration. Use B if richer comparison and stateful exploration become explicit goals and a Python hosting runtime is available.
- **Municipal production.** A versioned static public view remains viable for approved aggregate releases. Evaluate C when stakeholders confirm requirements for programmatic access, frequent governed updates, multiple queryable releases, or role-based workflows. Confirm a service owner, hosting and identity arrangements, retention and audit needs, accessibility acceptance, monitoring, and restore drills before committing to that stack. Keep identifiable fieldwork in a separately controlled process.
