# Bremen decision support · Technical benchmark

**Choose static HTML for the student prototype.** It fits the validated 2024-v1 snapshot and can run offline from saved CSV and PNG files.

| Option | Prototype score / 5 | Best fit |
| --- | ---: | --- |
| **A · Python-generated static HTML** | **4.55** | Reproducible, portable neighborhood comparison |
| B · Streamlit | 3.73 | Richer widget-driven exploration with a Python server |
| C · API + frontend + database | 3.28 | Governed services and reusable APIs when demand is confirmed |

**Independent audit results.** The static probe generated identical table bytes for all 88 neighborhoods on two builds. SQLite preserved the neighborhood key and missing rank, providing a partial check of C’s data model. The original benchmark reports that Streamlit’s simulated selector handled a saved rank and an excluded area. Streamlit was unavailable in the independent audit environment.

**What changes the choice.** A also wins with equal weights. B leads when interactive exploration dominates. C leads when API interoperability and scalability carry much more weight. The scores are weighted engineering judgments. The probes cover local feasibility and leave production performance unmeasured.

**Municipal path.** Start with approved aggregate releases. Reassess a managed API and database once programmatic access, governed refreshes, or role-based workflows are confirmed. Keep Moran’s I at release level and fieldwork marked proposed until observations are collected.

[Benchmark report](technical_benchmark.md) · [Criteria, ratings, and weights](technical_benchmark_matrix.csv)
