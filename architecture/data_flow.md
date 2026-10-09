# Data flow and publication gates

```mermaid
flowchart TD
  A[Supplied original municipal CSV / XLS] --> B[Existing preparation and retained raw values]
  J[JSON metadata catalogue] --> M[Separate source-discovery metadata]
  B --> C[Independent raw reconstruction and source hashes]
  C --> D[Ortsteil / unit / year / range / coverage gates]
  D --> E[2024 complete-case analytical matrix]
  D --> H[Historical records: change gate blocked]
  E --> I[Composite index and TOPSIS rankings]
  E --> K[K-means nominal profiles]
  I --> R[Weight and feature sensitivity]
  K --> S[Initialization and bootstrap stability]
  R --> O[Tables / figures / executed notebooks / evidence PDFs]
  S --> O
  O -. proposed reviewed publishing .-> P[Planner decision-support dashboard]
```

The current pipeline reads local originals and verifies Phase 1 outputs without overwriting them. Selected observations retain source file/sheet, original indicator, block, geographic code, year, unit and raw value. A separate analytical matrix explicitly records exclusions. Normalization and TOPSIS trace tables allow score reconstruction. Publication is a proposed additional stage, requiring reference-date, licence, privacy and release approval checks.

Reproduction: python src/run_technical_pipeline.py runs audit, construction, descriptive analysis, scoring, clustering, robustness and packaging. python src/create_notebooks.py creates and executes eight notebooks from fresh kernels. python src/verify_outputs.py checks persisted results and immutable-source hashes. Source metadata cannot be filled in from guesswork.
