# Implemented method specifications

Baseline: 2024, 79 complete-case Ortsteile, three percentage indicators. Higher unemployment quotient, lower social-insurance employment participation, and higher SGB II receipt under 65 represent greater measured disadvantage. The intended scope is partial labour-market/material-support disadvantage, not a validated universal poverty measure. Every method uses the same rows and columns.

Descriptive means and quartiles treat each neighborhood equally. The descriptive standard deviation uses ddof=1; StandardScaler uses population standard deviation (ddof=0). Neither convention supplies uncertainty for small-area source rates. All figures identify units, reporting year, source and interpretation limits; figure_notes.md provides captions.

## Composite index

For each indicator, transform x to z = (x - observed minimum) / (observed maximum - observed minimum). Reverse employment as 1-z. The score is sum(w_j * z_j), with w_j = 1/3. Score 1 means the observed high-disadvantage endpoint on all criteria; score 0 means the opposite endpoint. Rank in descending order with competition ties (1,2,2,4). Endpoints depend on sample coverage. A compensatory average lets relative strength on one indicator offset weakness on another. Equal indicator weights are a transparent baseline, not a value-free choice: labour-market variables receive two-thirds combined weight. Domain-balanced sensitivity reduces that double emphasis.

## TOPSIS

Use original percentages x, vector normalization r_ij = x_ij / sqrt(sum_i x_ij^2), and weighted values v_ij = w_j*r_ij. For the disadvantage ideal, choose column maximum for unemployment/benefits and minimum for employment. Choose the opposite extrema for the anti-ideal. Euclidean distances D+ and D- measure distance to those two hypothetical profiles. Closeness C = D-/(D+ + D-) is higher near the disadvantage ideal. Rank descending. Employment is a cost criterion relative to the disadvantage objective; unemployment/benefits are benefit criteria for that objective, not societal benefits. Neither ideal needs to be an actual neighborhood.

TOPSIS weights scale distances: their squared contribution enters Euclidean squared distance. Consequently, an equal-weight TOPSIS score is not the same aggregation as an equal-weight min-max average. No extra min-max transformation precedes baseline TOPSIS. Reference population and normalization matter. Exact weighted matrix, weights, ideals and distances are exported for inspection.

## K-means

Standardize raw indicators to mean zero and population standard deviation one using StandardScaler. Use scikit-learn KMeans with k-means++ initialization, random_state=42, n_init=30. Test k=2 through 8 and retain diagnostics for each. Choose the highest mean silhouette among solutions with at least three members in every cluster; this minimum-size constraint is pragmatic. Report inertia, silhouette, Calinski-Harabasz and Davies-Bouldin diagnostics, observed percent profiles, size, and 30-seed initialization plus 30 bootstrap-refit ARI checks.

K-means minimizes within-cluster squared Euclidean distance. It is suited to roughly compact profiles, is sensitive to scaling/outliers, and does not establish natural or policy-optimal groups. Profile A/B/etc. are arbitrary nominal labels, never a ranking. Direction reversal would not change distances, so raw standardized percentages are used. Describe a profile as relatively disadvantaged only when its observed unemployment, employment and benefit means support that description.

## Robustness and inference boundaries

Use fixed covered neighborhoods for all ranking scenarios. Test domain-balanced and employment/unemployment-emphasis weights, leave-one-indicator-out diagnostics, 200 constrained random weight vectors, and child benefit receipt as an overlapping fourth variable when complete coverage is retained. Spearman and Kendall describe rank agreement; top-ten overlap is a communication diagnostic, not a service eligibility threshold. Weight rank ranges are scenario ranges, not confidence intervals.

Initialization and bootstrap clustering ARI measure algorithm/fitting-sample stability, not measurement accuracy. No significance tests, causal effects, policy impacts, population-weighted city rates, or longitudinal change estimates are claimed. The absence of denominator counts prevents reliable small-area uncertainty estimation. Historical records and separate 2020 income context are preserved for review; no mixed-year primary dataset is used.
