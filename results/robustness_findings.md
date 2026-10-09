# Robustness evidence

Same 79 complete-case neighborhoods throughout; no resampling changes ranking coverage. Equal weights, domain-balanced weights (labour-market domain 0.5 split across two indicators; benefits 0.5), single-indicator emphasis, each indicator omitted, 200 constrained Dirichlet weight draws, and optional child-benefit inclusion are calculated for both ranking methods. Omission scenarios are diagnostics, not validated replacement indices. Random weights represent analyst choices, not probability distributions of true deprivation.

Composite/TOPSIS rank Spearman: 0.9743; Kendall tau-b: 0.8832. Lowest scenario rank correlation is 0.9622 (composite, plausible_random_135), with maximum rank movement 17. Full scenario results and top-ten overlap are in sensitivity_summary.csv. Rank ranges are NOT confidence intervals and do not quantify sampling error.

K-means initialization stability mean ARI 1.0000, minimum 1.0000. Bootstrap-neighborhood refitting mean ARI 0.8917, minimum 0.5913. Bootstrap models predict the full fixed standardized sample; this tests fitting-sample sensitivity, not longitudinal stability. Cluster labels are nominal.

Outliers flagged by 1.5-IQR fences remain in analysis; they are not automatically errors. Min-max index endpoints and TOPSIS vector normalization depend on the included sample. Correlated indicators, different denominators, absent income in 2024, unknown measurement error, and missing neighborhoods remain material uncertainties. Agreement between methods is not external validation. No method is objectively best on this evidence.
