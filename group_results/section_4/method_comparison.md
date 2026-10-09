# Method comparison evidence

Shared data: 79 Ortsteile, 2024, three indicators, no imputation. Highest equal-weight composite scores:

| geo_name | composite_score | rank |
| --- | --- | --- |
| Ohlenhof | 0.943 | 1 |
| Gröpelingen | 0.876 | 2 |
| Grohn | 0.821 | 3 |
| Blumenthal | 0.795 | 4 |
| Lindenhof | 0.777 | 5 |
| Tenever | 0.769 | 6 |
| Lüssum-Bockhorn | 0.724 | 7 |
| Kirchhuchting | 0.708 | 8 |
| Bahnhofsvorstadt | 0.698 | 9 |
| Fähr-Lobbendorf | 0.693 | 10 |

Highest TOPSIS disadvantage closeness:

| geo_name | topsis_score | rank |
| --- | --- | --- |
| Ohlenhof | 0.971 | 1 |
| Gröpelingen | 0.911 | 2 |
| Blumenthal | 0.810 | 3 |
| Lindenhof | 0.796 | 4 |
| Tenever | 0.767 | 5 |
| Grohn | 0.738 | 6 |
| Lüssum-Bockhorn | 0.726 | 7 |
| Bahnhofsvorstadt | 0.726 | 8 |
| Neuenland | 0.699 | 9 |
| Kirchhuchting | 0.696 | 10 |

Rank Spearman 0.9743; Kendall tau-b 0.8832. Agreement is within-sample consistency, not evidence of correct identification of true poverty. Both scores are relative, with different normalizations and aggregation geometries.

Largest rank differences and observed percentages (unemployment, employment, benefits; all 2024):

| geo_name | composite_rank | topsis_rank | unemployment | employment | benefit_receipt |
| --- | --- | --- | --- | --- | --- |
| Rablinghausen | 73.000 | 50.000 | 9.073 | 72.401 | 10.984 |
| St. Magnus | 38.000 | 57.000 | 9.229 | 51.704 | 6.176 |
| Lehe | 49.000 | 63.000 | 6.676 | 54.140 | 6.251 |
| Fähr-Lobbendorf | 10.000 | 20.000 | 17.411 | 44.159 | 17.669 |
| Oberneuland | 60.000 | 69.000 | 5.466 | 56.202 | 4.471 |
| Mahndorf | 54.000 | 45.000 | 9.290 | 64.645 | 12.379 |
| Ueberseestadt | 16.000 | 24.000 | 14.129 | 47.633 | 19.422 |
| Steintor | 51.000 | 58.000 | 8.126 | 58.080 | 7.624 |

Min-max equal-weight scoring gives each observed indicator range equal contribution. TOPSIS vector normalization gives columns different effective spreads, and closeness uses Euclidean distances. The differing observed profiles explain why an employment weakness can change rank differently from a benefit-receipt weakness; no causal explanation of neighborhood conditions is inferred.

K-means selected k=2; mean silhouette 0.5277. Labels are nominal:

- Profile A: n=51; unemployment 8.45%, employment 61.40%, SGB II receipt 9.82%.
- Profile B: n=28; unemployment 18.08%, employment 53.58%, SGB II receipt 23.99%.

The same profile has the highest unemployment and benefit receipt and the lowest employment, supporting a relative disadvantage description on these three indicators. No Profile A/B ordering is inferred. Stability evidence is in robustness_findings.md; cluster count is an algorithmic diagnostic choice, not a proven municipal taxonomy.

Interpretability: the composite average is easiest to reconstruct; TOPSIS requires understanding normalization and hypothetical ideals; clusters require inspecting profiles rather than reading rank numbers. Transparency depends on publishing definitions, weights, coverage and traces for all three. Robustness tests show dependence on analyst choices. Data requirements are a complete consistent numeric matrix; K-means additionally requires enough varied observations and standardized scales. No winner is declared.

Figures and evidence: composite_ranking.png, ranking_agreement.png, cluster_profiles.png, cluster_projection.png, kmeans_diagnostics.png, weight_sensitivity.png. Rankings may guide questions for planners, not dictate budgets or individual eligibility. Wider income, education, housing and health indicators, denominator counts, source-definition verification and external validation are needed for a general disadvantage measure.
