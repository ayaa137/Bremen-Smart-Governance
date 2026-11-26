# Bremen decision support · Technical benchmark

**Choose static HTML for the student prototype.** It fits the validated 2024-v1 snapshot and can run offline from saved CSV and PNG files.

| Option | Prototype score / 5 | Best fit |
| --- | ---: | --- |
| **A · Python-generated static HTML** | **4.55** | Reproducible, portable neighborhood comparison |
| B · Streamlit | 3.73 | Richer widget-driven exploration with a Python server |
| C · API + frontend + database | 3.28 | Governed services and reusable APIs when demand is confirmed |

**What we verified locally.** Static HTML rendered all 88 neighborhoods into the same table bytes on two builds. Streamlit’s simulated selector handled both a saved rank and an excluded area. SQLite preserved the neighborhood key and missing rank, providing a partial check of C’s data model.

**What changes the choice.** A also wins with equal weights. B leads when interactive exploration dominates. C leads when API interoperability and scalability carry much more weight. These are weighted engineering judgments, with local feasibility checks providing supporting evidence.

**Municipal path.** Start with approved aggregate releases. Reassess a managed API and database once programmatic access, governed refreshes, or role-based workflows are confirmed. Keep Moran’s I at release level and fieldwork marked proposed until observations are collected.

[Benchmark report](technical_benchmark.md) · [Criteria, ratings, and weights](technical_benchmark_matrix.csv)
