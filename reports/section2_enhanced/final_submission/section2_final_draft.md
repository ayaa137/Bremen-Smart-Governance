## 2.1 Data Sources and Coverage

Section 2 addresses RQ1 through observed neighborhood differences and RQ2 through indicator suitability. The shared Ortsteilatlas dataset represents 88 Bremen neighborhoods in 2024. Unemployment and employment are available for 79 neighborhoods; SGB II receipt covers 84. All 88 remain in coverage documentation, including nine excluded from the three-indicator complete-case comparison. Official boundaries support the maps, with an explicitly documented Oberneuland geographic crosswalk (Figure 1).

## 2.2 Indicator Selection and Processing

Unemployment measures unemployed people relative to socially insured employees plus unemployed people. Employment relates socially insured employees to residents aged 15?<65; SGB II receipt relates recipients to residents under 65. These percentages have distinct denominators. Geographic codes remain strings; missing observations are neither imputed nor replaced with zero. Original workbook cells, provenance and observation uniqueness were validated. Summaries weight neighborhoods equally, rather than estimating population-weighted city rates. Child receipt and single-parent households provide context; taxpayer income is explicitly historical, from 2020 (Figure 3).

## 2.3 Results and Interpretation

Unemployment ranges from 2.5896% in Seehausen to 27.5409% in Ohlenhof. Across 79 complete observations, unemployment and SGB II receipt show strong monotonic agreement: Spearman ?=0.973856 and Kendall ?-b=0.874716 (Figure 2). Omitting each neighborhood individually leaves Spearman between 0.972837 and 0.977769. Restricting SGB II to complete cases raises its mean by 0.514646 percentage points, demonstrating sample sensitivity. Unemployment and benefit receipt are useful economic disadvantage measures, but their overlap cautions against treating them as independent evidence. Household composition does not inherently imply deprivation. Missingness, unknown denominator counts and uncertain reference-day alignment limit interpretation. Geographic area must not be mistaken for affected population. These associations establish neither causality nor policy priorities; composite weighting, TOPSIS and clustering remain Section 4 responsibilities.

Figure 1. Economic maps, 2024. Sources: Ortsteilatlas; Landesamt GeoInformation Bremen boundaries, CC BY 4.0.

Figure 2. Economic relationships, 2024; n=79. Source: Ortsteilatlas.

Figure 3. Contextual distributions, 2024; income 2020. Source: Ortsteilatlas. Context is not deprivation.
