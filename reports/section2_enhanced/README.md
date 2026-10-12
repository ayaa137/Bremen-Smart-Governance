# Section 2 navigation

The group-report contribution is [final_submission/section2_data_and_indicator_analysis.md](final_submission/section2_data_and_indicator_analysis.md). Word counts and preparation checks are recorded separately in that folder. The earlier integration draft remains unchanged.

Use these three existing PNGs, in this order (all paths below are relative to the repository root):

1. `figures/section2_enhanced/enhanced_atlas_economic_maps_side_by_side_2024.png`
2. `figures/section2_enhanced/fig03_economic_indicator_relationships_2024.png`
3. `figures/section2_enhanced/contextual_distributions_separate_periods.png`

Full evidence: [Quarto source](section2_enhanced.qmd), [HTML report](section2_enhanced.html), [PDF report](section2_enhanced.pdf), [offline explorer](evidence_explorer.html), [methods/results](methods_results.md), and [indicator assessment](indicator_suitability_framework.csv). V2 evidence is in `reports/section2_v2/`; geographic evidence and frozen sources are in its `atlas/` subfolder. Earlier Section 2 files are historical evidence, not the current indicator selection.

## Reproduce without changing validated artifacts

From the repository root, using an environment with the existing requirements installed:

```text
python -B src/section2_enhanced/build_enhancement.py --validate-only
```

This recalculates twice in temporary staging, compares scientific tables/figures against existing artifacts, and preserves all outputs. It also renders HTML in staging and tests the explorer when the tools are available. Branch names and current HEAD are execution metadata; the documented baseline and immutable workbook, dataset and geography hashes remain scientific provenance. A precisely pinned compatibility change permits the modified V2 validator; no historical manifest is rewritten. The original V2/Atlas publishing entry points retain their historical guards. Do not run them to replace old evidence.

Quarto and Chromium-family browsers are discovered on PATH, with Windows environment-based fallbacks. Optional overrides: `SECTION2_QUARTO` and `SECTION2_BROWSER`. Missing tools are explicitly reported as BLOCKED, not successful rendering or browser tests. The historical generator without `--validate-only` retains collision protection and may reject changed administrative metadata; use validation mode for this preserved package.

PDF reproduction uses the existing Windows recipe:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File reports/section2_enhanced/render_pdf.ps1
```

It requires installed Quarto with bundled Typst, renders twice in temporary staging and refuses to overwrite a differing PDF. The policy override applies only to that process. This PDF helper remains Windows-specific; PNG/QMD/HTML evidence and Python validation are separately usable. Cross-version byte-identical rendering is not promised.

## Interpretation and attribution

There are 88 represented units and 79 complete economic observations. Indicators have distinct denominators. Income is 2020, not 2024; household structure is contextual, not intrinsic deprivation. Missingness mechanisms, denominator sizes and exact observation days remain unresolved. The Oberneuland crosswalk is explicit; a boundary dataset revision is not certified legal validity. Correlation is not causation. Composite indices, TOPSIS and clustering belong to Section 4.

Retain Ortsteilatlas attribution and boundary attribution to Landesamt GeoInformation Bremen, ATKIS, CC BY 4.0. Boundary licensing does not establish a license for every documentary snapshot or the workbook. Do not omit frozen inputs or older evidence files currently required by historical manifests. See the cleanup audit before choosing staging paths.
