# Four-layer technical blueprint

Project: Data-Driven Smart Governance: A Comparative Evaluation of Methods for Identifying Socioeconomic Inequalities Across Bremen's Neighborhoods.

The architecture is a proposal around the implemented local analytical pipeline. Open architecture_diagram.png for the four layers. The diagram marks local implemented components and proposed deployment components separately.

| Layer | Implemented in repository | Proposed deployment / future extension |
| --- | --- | --- |
| 1. Sensing / Data Acquisition | Supplied municipal XLS and historical CSV files; JSON dataset catalogue; source hashes | Versioned retrieval of municipal releases; catalogue used for discovery. Actual update frequency is unverified and indicator-specific. No live sensors. Future environmental IoT is a separate data domain, not a poverty sensor. |
| 2. Transmission / Network | Local filesystem handoff; original downloads not implemented | HTTPS downloads or authenticated API/file transfer if offered; TLS, timeouts, retries, checksum verification and release manifests. SFTP only if publisher supports it. 5G/LoRaWAN only for a separately justified future sensor deployment. |
| 3. Processing / Cloud or Edge | Python validation, CSV storage, scripts, executed notebooks; composite, TOPSIS, K-means and sensitivity outputs | Scheduled versioned jobs, PostgreSQL for validated tables, object storage for immutable releases, containerized cloud or municipal hosting. Batch processing needs no edge device. Failed validations block publication. |
| 4. Application / AI and Decision Support | Static figures, CSV results, readable PDFs and evidence packages | Proposed planner dashboard for indicators, comparisons, scores, nominal cluster profiles, weights, provenance, exclusions and exports. K-means is unsupervised analysis; no predictive model is implemented. |

A dashboard has not been developed. Proposed workflow: select a validated release and year; inspect coverage first; compare neighborhoods and denominator definitions; inspect index/TOPSIS assumptions; view nominal cluster profiles; run versioned weight scenarios; export evidence with provenance and exclusions. Historical changes remain disabled until their validation gate passes. Scenarios cannot quietly mix releases, years or populations.

Method integration contract: one release ID and 2024 complete-case row set, stable geographic keys, versioned feature definitions, explicit units/directions/weights, deterministic configuration, and method output metadata. Cluster display order must not imply a numerical rank. Proposed allocation decisions require planner review and additional contextual evidence.
