# Reproducing and reviewing the technical work

Run commands in the project root. Python 3.10+ recommended (the tested environment version is recorded in environment_versions.json). Install only requirements.txt dependencies:

```powershell
python -m pip install -r requirements.txt
python src/run_technical_pipeline.py
python src/create_notebooks.py
python src/verify_outputs.py
```

The pipeline reuses existing Phase 1 preparation, independently rereads originals, verifies every existing statistical observation, and writes the new analysis/results packages. It does not rerun prepare_data.py to replace the Phase 1 inventory. Existing original and Phase 1 source outputs are retained. All new outputs are derived artifacts; reproduction regenerates those files deterministically. Source hashes are rechecked before completion. A serious gate failure stops dependent scoring. The known longitudinal gate failure is documented; no change estimates are generated.

Open notebooks 01 through 08 in order in VS Code/Jupyter. Each locates the root relative to its working directory and uses reusable src functions. The notebook generator executes each from a fresh Python kernel and saves actual outputs. Scripts never depend on notebook state. Read data loading, calculation and results cells in sequence. A Python kernel is required; the generated notebook metadata records its name.

01 audits six candidate indicators and coverage. 02 independently rebuilds and validates the annual matrix. 03 computes descriptions/plots. 04 runs the composite index. 05 runs TOPSIS. 06 runs K-means diagnostics and stability. 07 compares saved baseline results. 08 runs weight/feature sensitivity. Review notes explicitly distinguish blocked longitudinal work from valid annual results.

For non-programmers: start at group_results/OVERVIEW.md, then the PDF and EVIDENCE_GUIDE.md in your section folder. All result tables and figures can be opened independently. Detailed formulas are in docs/methods.md. Source/revision verification limits are in docs/source_notes.md. TECHNICAL_COMPLETION_REPORT.md records final checks and remaining work.

requirements.txt expresses compatible minimum versions; environment_versions.json and requirements-tested.txt record exact tested direct dependencies, not a complete transitive environment lock. No cloud/API/mapping dependencies are needed. Figures are PNGs; PDFs are simple evidence summaries, not university report drafts. No source or result is pushed to GitHub.
