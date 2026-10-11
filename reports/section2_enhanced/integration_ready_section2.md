# Section 2 — integration-ready text

## 2.1 Data sources, coverage and indicator selection

The shared 2024 dataset contains 88 represented Bremen statistical Ortsteile, including 79 complete cases for unemployment, socially insured employment and SGB II receipt. Original workbook cells and provenance were verified. All records remain in missingness documentation; blanks are not imputed. Percentages have distinct denominators: unemployment uses insured employees plus unemployed; employment uses population aged 15–<65; SGB II uses population under 65. Under-15 receipt is supplementary, household composition contextual, and 2020 taxpayer income historical. Official ATKIS polygons match 87 direct Ortsteile plus an explicit undivided Oberneuland crosswalk. Dataset revision is 11 December 2024, not a verified legal validity date.

## 2.2 Neighborhood differences and robustness

Observed unemployment ranges from 2.5896% in Seehausen to 27.5409% in Ohlenhof; SGB II receipt from 0.9901% in In den Hufen to 34.6216% in Ohlenhof. Employment ranges from 44.1589% in Fähr-Lobbendorf to 72.7138% in Seehausen. Summaries are equally weighted neighborhood observations, not city population rates. Valid exploratory outliers were retained after source verification.

Unemployment–SGB II Spearman rho=0.973856 and Kendall tau-b=0.874716, n=79. All primary pairwise samples equal the complete-case sample. Across 79 single-case omissions, rho ranges 0.972837–0.977769; the largest absolute change is 0.003913, excluding Fähr-Lobbendorf. This strong monotonic relationship is robust to a single omission, not causal or independent validation of deprivation. Restricting SGB II from 84 available observations to 79 raises the mean by 0.514646 points and median by 0.763750 points; missingness assumptions remain unsupported.

Child SGB II receipt averages 22.0805% (n=84), with strong overlap with overall receipt. Single-parent share averages 24.9255% (n=83), describing family structure rather than intrinsic disadvantage. Historical median taxpayer-income values remain explicitly 2020. These do not fully characterize demographic inequality.

## 2.3 Indicator suitability and governance implications

The three primary indicators offer complementary restricted economic perspectives; high unemployment–receipt overlap requires attention in Section 4 without assigning weights here. Maps retain all 88 units and original tertiles; 65/79 (82.28%) paired observations share a tertile. Missingness is visible: 79 complete areas, five missing two indicators and four missing all three. These are evidence gaps, not favorable conditions or official risk classes. Geography, reference-day and denominator limitations remain explicit; land area is not affected population. The offline explorer exposes these caveats transparently. Composite indices, TOPSIS, clustering, architecture and resource-allocation decisions belong outside Section 2.
