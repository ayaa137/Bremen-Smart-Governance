import numpy as np
import pandas as pd
from scipy.stats import spearmanr, kendalltau
import composite_index
import topsis
from analysis_common import ROOT, FEATURES, load_analysis, save_csv, write_doc

def ranks(scores):
    return pd.Series(scores).rank(ascending=False, method='min').to_numpy()

def run():
    frame = load_analysis().reset_index(drop=True)
    baseline = {'composite': ranks(composite_index.calculate(frame)), 'topsis': ranks(topsis.calculate(frame))}
    scenarios = [('equal', FEATURES, [1,1,1]), ('domain_balanced', FEATURES, [.25,.25,.5]),
                 ('unemployment_emphasis', FEATURES, [.5,.25,.25]), ('employment_emphasis', FEATURES, [.25,.5,.25])]
    scenarios += [('omit_' + f, [x for x in FEATURES if x != f], None) for f in FEATURES]
    rng = np.random.default_rng(2024)
    # Constrain all random weights to [0.10, 0.60], avoiding nearly single-criterion scores.
    for i in range(200):
        while True:
            w = rng.dirichlet([3,3,3])
            if (w >= .1).all() and (w <= .6).all():
                break
        scenarios.append((f'plausible_random_{i:03}', FEATURES, w))
    long = pd.read_csv(ROOT / 'data/processed/selected_indicators_long.csv', dtype={'geo_code':str})
    child = long[(long.feature == 'child_benefits') & (long.year == 2024)][['geo_code','value']].rename(columns={'value':'child_benefits'})
    frame = frame.merge(child, on='geo_code', validate='one_to_one')
    if frame.child_benefits.notna().all():
        scenarios.append(('include_child_benefits', FEATURES + ['child_benefits'], None))
    rows, summaries = [], []
    for name, features, weights in scenarios:
        w = np.ones(len(features)) / len(features) if weights is None else np.asarray(weights) / np.sum(weights)
        for method, calculate in [('composite', composite_index.calculate), ('topsis', topsis.calculate)]:
            scores = calculate(frame, features, w)
            rank = ranks(scores)
            delta = rank - baseline[method]
            base_top = set(frame.loc[baseline[method] <= 10, 'geo_code'])
            top = set(frame.loc[rank <= 10, 'geo_code'])
            summaries.append({'scenario':name, 'method':method, 'spearman_vs_baseline':spearmanr(rank,baseline[method]).statistic,
                              'mean_absolute_rank_change': np.abs(delta).mean(), 'max_absolute_rank_change': np.abs(delta).max(),
                              'top10_overlap': len(top & base_top), 'n':len(frame)})
            for i, row in frame.iterrows():
                rows.append({'scenario':name, 'method':method, 'geo_code':row.geo_code, 'geo_name':row.geo_name, 'year':2024,
                             'features':';'.join(features), 'weights':';'.join(f'{v:.8f}' for v in w),
                             'score':scores[i], 'rank':rank[i], 'baseline_rank':baseline[method][i], 'rank_change':delta[i]})
    sensitivity = pd.DataFrame(rows)
    save_csv(sensitivity,'results/sensitivity_results.csv')
    summary = pd.DataFrame(summaries)
    save_csv(summary,'results/sensitivity_summary.csv')
    ranges = sensitivity[sensitivity.scenario.str.startswith('plausible_random')].groupby(['method','geo_code','geo_name'])['rank'].agg(['min','max','median']).reset_index()
    save_csv(ranges,'results/weight_rank_ranges.csv')
    rho = spearmanr(baseline['composite'],baseline['topsis']).statistic
    tau = kendalltau(baseline['composite'],baseline['topsis']).statistic
    comparison = frame[['geo_code','geo_name','year']].copy()
    comparison['composite_rank'] = baseline['composite']
    comparison['topsis_rank'] = baseline['topsis']
    comparison['rank_difference_topsis_minus_composite'] = baseline['topsis'] - baseline['composite']
    comparison['absolute_rank_difference'] = comparison.rank_difference_topsis_minus_composite.abs()
    save_csv(comparison.sort_values('absolute_rank_difference',ascending=False),'results/ranking_agreement.csv')
    save_csv(pd.DataFrame([{'spearman':rho,'kendall_tau_b':tau,'n':len(frame)}]),'results/ranking_agreement_summary.csv')
    cluster = pd.read_csv(ROOT/'results/cluster_stability.csv')
    stability = cluster.groupby('experiment').adjusted_rand_index.agg(['mean','min','max'])
    save_csv(stability.reset_index(), 'results/cluster_stability_summary.csv')
    worst = summary.loc[summary.spearman_vs_baseline.idxmin()]
    write_doc('results/robustness_findings.md', f'''# Robustness evidence

Same {len(frame)} complete-case neighborhoods throughout; no resampling changes ranking coverage. Equal weights, domain-balanced weights (labour-market domain 0.5 split across two indicators; benefits 0.5), single-indicator emphasis, each indicator omitted, 200 constrained Dirichlet weight draws, and optional child-benefit inclusion are calculated for both ranking methods. Omission scenarios are diagnostics, not validated replacement indices. Random weights represent analyst choices, not probability distributions of true deprivation.

Composite/TOPSIS rank Spearman: {rho:.4f}; Kendall tau-b: {tau:.4f}. Lowest scenario rank correlation is {worst.spearman_vs_baseline:.4f} ({worst['method']}, {worst.scenario}), with maximum rank movement {worst.max_absolute_rank_change:.0f}. Full scenario results and top-ten overlap are in sensitivity_summary.csv. Rank ranges are NOT confidence intervals and do not quantify sampling error.

K-means initialization stability mean ARI {stability.loc['initialization','mean']:.4f}, minimum {stability.loc['initialization','min']:.4f}. Bootstrap-neighborhood refitting mean ARI {stability.loc['bootstrap_neighborhoods','mean']:.4f}, minimum {stability.loc['bootstrap_neighborhoods','min']:.4f}. Bootstrap models predict the full fixed standardized sample; this tests fitting-sample sensitivity, not longitudinal stability. Cluster labels are nominal.

Outliers flagged by 1.5-IQR fences remain in analysis; they are not automatically errors. Min-max index endpoints and TOPSIS vector normalization depend on the included sample. Correlated indicators, different denominators, absent income in 2024, unknown measurement error, and missing neighborhoods remain material uncertainties. Agreement between methods is not external validation. No method is objectively best on this evidence.
''')
    return summary

if __name__ == '__main__':
    print(run().head(14).to_string(index=False))
