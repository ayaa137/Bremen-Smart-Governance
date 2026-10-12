# Section 2 V2 — Data and Indicator Analysis

## Scope and authoritative baseline

Branch analysis/section-2-v2; fetched baseline 20b79ae817c5d7c7b80e1d93c79d415d47037be7. RQ1: What socioeconomic and demographic differences exist across Bremen's neighborhoods? RQ2: Which indicators are most useful for identifying neighborhood disadvantage?

This independently recalculated evidence package reads the shared ortsteil_analysis_ready.csv, selected_indicators_long.csv, indicator_selection.csv and data_dictionary.csv. It does not read old Section 2 statistical outputs or modify shared files. The specifically titled five-page 'Bremen Smart Governance — Section 2 Guide' was not located; available shared evidence guides are not claimed to be that document. Implementation follows the supplied detailed requirements and group_results/OVERVIEW.md. No composite indices, TOPSIS, clustering, disadvantage ranking or architecture are implemented.

## Data selection and quality

Master coverage: 88 Ortsteile, 2024. Comparison: shared 79-row scoring_eligible sample, used here only as a completeness flag. Codes remain strings; no Stadtteil/Stadtbezirk/city aggregates enter. Eligibility was independently checked against all three nonmissing values. No missing values were replaced with zero or imputed. Exact source worksheet, German label, block=1, units and annual reporting periods were checked. All 9,152 selected observations, including blanks, match original workbook cells; all 24 original-source hashes match the shared source manifest. Geographic-year-feature keys are unique, and selected observations have no invalid statuses or out-of-range percentages. The income analysis unit is explicitly 1000 EUR from its original heading; its original inferred unit is blank.

| feature | year | represented_n | observed_n | missing_n | missing_pct |
| --- | --- | --- | --- | --- | --- |
| unemployment | 2024 | 88 | 79 | 9 | 10.2273 |
| employment | 2024 | 88 | 79 | 9 | 10.2273 |
| benefit_receipt | 2024 | 88 | 84 | 4 | 4.5455 |
| child_benefits | 2024 | 88 | 84 | 4 | 4.5455 |
| single_parents | 2024 | 88 | 83 | 5 | 5.6818 |
| income_median | 2020 | 88 | 84 | 4 | 4.5455 |

| geo_code | geo_name | year | exclusion_reason |
| --- | --- | --- | --- |
| 122 | Industriehäfen | 2024 | unemployment:missing;employment:missing;benefit_receipt:missing |
| 124 | Neustädter Hafen | 2024 | unemployment:missing;employment:missing;benefit_receipt:missing |
| 125 | Hohentorshafen | 2024 | unemployment:missing;employment:missing;benefit_receipt:missing |
| 271 | Strom | 2024 | unemployment:missing;employment:missing |
| 411 | Blockland | 2024 | unemployment:missing;employment:missing |
| 424 | In den Hufen | 2024 | unemployment:missing;employment:missing |
| 436 | Hohweg | 2024 | unemployment:missing;employment:missing |
| 444 | In den Wischen | 2024 | unemployment:missing;employment:missing;benefit_receipt:missing |
| 512 | Werderland | 2024 | unemployment:missing;employment:missing |

These nine areas remain in coverage evidence. Source reasons for missingness are unknown; concentrated exclusions can distort coverage. The 79-area sample is not all Bremen neighborhoods. Validation reports in the shared baseline document source reconstruction and an exploratory annual gate; exact observation dates and historical comparability remain unverified.

## Methods

Both complete-case and available-case descriptive tables report valid n, missingness, extrema with names, mean/median, ddof=1 sample SD, linear-interpolation quartiles/IQR/P10/P90 and percentage-point range. Complete-case tables show zero within-sample missingness; exclusion coverage is reported separately against 88 master records. All neighborhood means give each area equal weight, not each resident. Context uses available observations in its own year; income is never carried forward.

Spearman coefficients use average ranks on the fixed 79-case economic sample, independently checked against Pearson correlation of average ranks. No p-values, confidence intervals, causal effects or spatial independence claims are asserted. Correlation measures monotone association, not numerical interchangeability, external validity or predictive performance. Employment's raw direction is retained. The child-benefit overlap calculation is supplementary and explicitly overlapping, not a fourth independent baseline criterion.

Median quadrants are exploratory: strict above/below comparisons, equality kept as a boundary category. No indicator is aggregated and no deprivation label or neighborhood rank is assigned. Thresholds depend on the sample; they are not official poverty standards. Tukey fences (Q1−1.5×IQR, Q3+1.5×IQR) flag extremes separately by sample. Flags and extrema were checked against workbook coordinates and retained; transcription agreement does not resolve small-denominator uncertainty.

## RQ1 — observed differences

Shared complete-case descriptions:

| feature | valid_n | mean | median | minimum | minimum_names | maximum | maximum_names | sd_sample | iqr | p10 | p90 | range |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| unemployment | 79 | 11.8617 | 10.9762 | 2.5896 | Seehausen | 27.5409 | Ohlenhof | 5.5536 | 8.7611 | 5.2720 | 19.4385 | 24.9513 |
| employment | 79 | 58.6303 | 59.4037 | 44.1589 | Fähr-Lobbendorf | 72.7138 | Seehausen | 5.3129 | 6.5646 | 51.6214 | 63.6274 | 28.5549 |
| benefit_receipt | 79 | 14.8438 | 13.2323 | 1.7015 | Borgfeld | 34.6216 | Ohlenhof | 8.3924 | 12.2281 | 3.8139 | 26.3729 | 32.9201 |

Available-case descriptions:

| feature | valid_n | mean | median | minimum | minimum_names | maximum | maximum_names | range |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| unemployment | 79 | 11.8617 | 10.9762 | 2.5896 | Seehausen | 27.5409 | Ohlenhof | 24.9513 |
| employment | 79 | 58.6303 | 59.4037 | 44.1589 | Fähr-Lobbendorf | 72.7138 | Seehausen | 28.5549 |
| benefit_receipt | 84 | 14.3292 | 12.4686 | 0.9901 | In den Hufen | 34.6216 | Ohlenhof | 33.6315 |

The SGB II available-case and complete-case summaries differ because five areas outside the common sample retain observed benefit values. This is a sample-composition effect, not a change in their measurements. Large neighborhood contrasts support investigation of differing labor-market/material-support conditions; they do not establish individual poverty or intervention needs.

Supplementary/contextual evidence:

| feature | year | valid_n | mean | median | minimum | minimum_names | maximum | maximum_names |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| child_benefits | 2024 | 84 | 22.0805 | 20.7702 | 0.0000 | In den Hufen | 53.6825 | Bahnhofsvorstadt |
| single_parents | 2024 | 83 | 24.9255 | 25.9427 | 9.7561 | Blockland | 42.8571 | Hohweg |
| income_median | 2020 | 84 | 28.0060 | 27.0980 | 16.0030 | Lindenhof | 51.8630 | Borgfeld |

Single-parent share describes household composition and cannot establish disadvantage by itself. Child benefit receipt reflects a narrower, overlapping recipient population. Median taxpayer income is historical 2020 context only. The current data do not adequately answer broad age, migration, health or other demographic dimensions of RQ1; this is a substantive limitation rather than a reason to import old indicators automatically.

## RQ2 — usefulness and overlap

| first | second | n | spearman_rho |
| --- | --- | --- | --- |
| unemployment | employment | 79 | -0.6674 |
| unemployment | benefit_receipt | 79 | 0.9739 |
| employment | benefit_receipt | 79 | -0.5879 |

Unemployment and benefit receipt describe strongly associated but differently defined economic conditions. Employment adds participation information with a reversed disadvantage direction, while excluding self-employment and civil servants. The three have credible directional interpretations for partial economic disadvantage; none is a universal deprivation measure. Correlation/redundancy should be handed to Section 4 without selecting weights here. Definition clarity, coverage, dispersion and timeliness are assessed in indicator_assessment.csv; no indicator is declared objectively best without an external criterion.

Supplementary under-65 versus child-benefit Spearman rho is 0.973466, n=79. This overlap does not provide independent validation.

Median-quadrant result: 76 same-side and 1 opposite-side observations among 77 strictly off-boundary cases (98.70% same-side); 2 equal at least one median. All 79 observations remain in the plotted/table evidence. Exact medians and group identities are exported. This sample-relative concordance is descriptive, not a deprivation index, policy threshold or resource-allocation rule.

## Figures, maps and interpretation

Five 300-dpi figures cover distributions, transparent selected contrasts, economic relationships, exploratory quadrant concordance and all-88 missingness. Each identifies year, level, units and sources. Exact plotted inputs, selection rules and captions are retained. No boundary polygon file is available; maps are not defensible and were not generated. Geographic inequality is therefore presented as differences across named Ortsteile, not spatial-autocorrelation or location effects. See figure_captions.md and data_blind_spots.md.

For the final report use Figures 1 and 3, optionally 4; keep the full missingness view supplementary. A presentation can use Figures 2 and 4 plus a coverage summary. Contextual household characteristics do not automatically indicate deprivation. Ecological rates cannot identify individual disadvantage, and different reference dates may affect comparison. Historical changes, current-2026 claims and causal/resource-allocation conclusions remain unsupported.

## Reproduction and handover

From the repository root, using the existing Section 2 environment:

```powershell
.\.venv-section2\Scripts\python.exe -B src/analyze_section2_v2.py
```

The script reads shared utilities for ROOT/YEAR/FEATURES only; it never runs the shared pipeline or its output-writing helpers. Required runtime packages are pandas, numpy, scipy, matplotlib and xlrd already available in that environment. Exact runtime versions and input/output hashes are recorded in reproduction_manifest.json. Reproduction in another environment requires those packages; no package installation is part of this task.

Existing outputs are never overwritten: an identical rerun checks equality and leaves files untouched; differing existing V2 outputs cause failure. All tracked and pre-existing untracked non-V2 files are hashed before and after execution. New outputs are staged, schema/count/figure inputs and correlation calculations are checked, and published only after validation. Source and output hashes plus baseline commit allow review without trusting notebook state. No commits or pushes are made. This is technical evidence, not a substitute for the group's literature review or verified municipal metadata. See handover_sections_1_3_4.md for section boundaries.
