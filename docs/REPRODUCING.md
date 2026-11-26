# Reproducing and reviewing the technical work

Run commands in the project root using the existing environment. No installation is needed when its requirements are already available. Python 3.10+ is recommended; recorded tested versions are in environment_versions.json.

```powershell
.\.venv-section2\Scripts\python.exe -B src/run_technical_pipeline.py
.\.venv-section2\Scripts\python.exe -B src/create_notebooks.py
.\.venv-section2\Scripts\python.exe -B src/verify_outputs.py
```

Routine packaging reuses `architecture/architecture_diagram.png`. It does not regenerate the image or rewrite architecture source documents. Packaging fails before its writes if the image is missing and regeneration was not requested; earlier scientific stages of the full pipeline may already have written their outputs. Group packaging still refreshes copies and evidence summaries under `group_results/`, including section 3.

Only when architecture-image regeneration is explicitly intended, use one of:

```powershell
.\.venv-section2\Scripts\python.exe -B src/package_results.py --regenerate-architecture
.\.venv-section2\Scripts\python.exe -B src/run_technical_pipeline.py --regenerate-architecture
```

The standalone packaging command without the flag also reuses the existing image. Existing no-argument Python calls remain supported; `package_results.run()` now defaults to `regenerate_architecture=False`.

The pipeline reuses existing Phase 1 preparation, independently rereads originals, verifies every existing statistical observation, and writes the new analysis/results packages. It does not rerun prepare_data.py to replace the Phase 1 inventory. Existing original and Phase 1 source outputs are retained. All new outputs are derived artifacts; reproduction regenerates those files deterministically. Source hashes are rechecked before completion. A serious gate failure stops dependent scoring. The known longitudinal gate failure is documented; no change estimates are generated.

Open notebooks 01 through 08 in order in VS Code/Jupyter. Each locates the root relative to its working directory and uses reusable src functions. The notebook generator executes each from a fresh Python kernel and saves actual outputs. All eight notebooks must execute and validate before publication starts. Successful notebooks and the execution-status JSON are staged on their destination filesystems; closed temporary files are published using atomic per-file replacements, with `analysis/notebook_execution.json` last. Execution or staging failure leaves previously published notebooks and status unchanged. Temporary-file cleanup is best effort: every removal is attempted, and failed paths are reported because files may remain. Cleanup errors do not replace the original execution, staging, or publication exception; if cleanup is the only failure, the command fails rather than claiming success. Publication exceptions and interruptions are re-raised unchanged. After completed notebook replacements, the generator warns of possible partial publication; it does not issue that warning before any replacement has completed. The previous status remains unchanged when publication stops before its final replacement; if that replacement is interrupted, inspect the status file because completion was not confirmed. Inspect notebook/status consistency before retrying. This is not a multi-file transaction. Notebook cells can regenerate analysis outputs while executing; those side effects are not rolled back by the publication safeguard. Scripts never depend on notebook state. Read data loading, calculation and results cells in sequence. A Python kernel is required; the generated notebook metadata records its name.

01 audits six candidate indicators and coverage. 02 independently rebuilds and validates the annual matrix. 03 computes descriptions/plots. 04 runs the composite index. 05 runs TOPSIS. 06 runs K-means diagnostics and stability. 07 compares saved baseline results. 08 runs weight/feature sensitivity. Review notes explicitly distinguish blocked longitudinal work from valid annual results.

For non-programmers: start at group_results/OVERVIEW.md, then the PDF and EVIDENCE_GUIDE.md in your section folder. All result tables and figures can be opened independently. Detailed formulas are in docs/methods.md. Source/revision verification limits are in docs/source_notes.md. TECHNICAL_COMPLETION_REPORT.md records final checks and remaining work.

requirements.txt expresses compatible minimum versions; environment_versions.json and requirements-tested.txt record exact tested direct dependencies, not a complete transitive environment lock. No cloud/API/mapping dependencies are needed. Figures are PNGs; PDFs are simple evidence summaries, not university report drafts. No source or result is pushed to GitHub.
