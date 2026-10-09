import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from analysis_common import ROOT, YEAR, FEATURES, LABELS, SOURCE, load_analysis, save_csv, write_doc

plt.rcParams.update({'font.size': 10, 'axes.titlesize': 13, 'figure.dpi': 130,
                     'axes.spines.top': False, 'axes.spines.right': False})

def export_figure(fig, name, caveat='Complete cases; unweighted neighborhoods; descriptive, not causal.'):
    folder = ROOT / 'results/figures'
    folder.mkdir(parents=True, exist_ok=True)
    fig.text(.02, .025, SOURCE + '\n' + caveat, fontsize=8)
    fig.tight_layout(rect=(0, .09, 1, 1))
    fig.savefig(folder / (name + '.png'), bbox_inches='tight')
    plt.close(fig)

def run():
    all_rows = load_analysis(False)
    frame = load_analysis()
    stats = frame[FEATURES].describe().T.reset_index(names='feature')
    stats['unit'] = '%'
    stats['year'] = YEAR
    stats['population'] = 'complete-case Ortsteile; unweighted'
    save_csv(stats, 'results/descriptive_statistics.csv')
    available = all_rows[FEATURES].describe().T.reset_index(names='feature')
    available['year'] = YEAR
    available['unit'] = '%'
    save_csv(available, 'results/available_case_statistics.csv')
    corr = frame[FEATURES].corr(method='spearman')
    save_csv(corr.reset_index(names='feature'), 'results/indicator_correlations.csv')
    pearson = frame[FEATURES].corr()
    save_csv(pearson.reset_index(names='feature'), 'results/pearson_correlations.csv')
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.5))
    for ax, feature, color in zip(axes, FEATURES, ['#147d92', '#b04c59', '#4a8c58']):
        ax.hist(frame[feature], bins=12, color=color, edgecolor='white')
        ax.set(xlabel=LABELS[feature], ylabel='Number of Ortsteile', title=str(YEAR))
    fig.suptitle('Distribution of neighborhood indicators')
    export_figure(fig, 'indicator_distributions')
    fig, ax = plt.subplots(figsize=(8, 6))
    top = frame.nlargest(15, 'benefit_receipt').sort_values('benefit_receipt')
    ax.barh(top.geo_name, top.benefit_receipt, color='#147d92')
    ax.set(xlabel=LABELS['benefit_receipt'], title=f'Highest observed benefit-receipt shares, {YEAR}')
    export_figure(fig, 'benefit_receipt_comparison')
    fig, ax = plt.subplots(figsize=(7, 6))
    image = ax.imshow(corr, vmin=-1, vmax=1, cmap='RdBu_r')
    ax.set_xticks(range(3), ['Unemployment', 'Employment', 'SGB II'], rotation=20)
    ax.set_yticks(range(3), ['Unemployment', 'Employment', 'SGB II'])
    for i in range(3):
        for j in range(3):
            ax.text(j, i, f'{corr.iloc[i,j]:.2f}', ha='center', va='center', color='black')
    fig.colorbar(image, ax=ax, label='Spearman rank correlation (unitless)')
    ax.set_title(f'Indicator association across Ortsteile, {YEAR}')
    export_figure(fig, 'correlation_matrix', 'Correlation does not imply causation; indicators overlap conceptually.')
    outliers = []
    for feature in FEATURES:
        q1, q3 = frame[feature].quantile([.25, .75])
        lower, upper = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
        for _, row in frame[(frame[feature] < lower) | (frame[feature] > upper)].iterrows():
            outliers.append({'geo_code': row.geo_code, 'geo_name': row.geo_name, 'year': YEAR,
                             'feature': feature, 'value': row[feature], 'lower_fence': lower, 'upper_fence': upper})
    save_csv(pd.DataFrame(outliers, columns=['geo_code','geo_name','year','feature','value','lower_fence','upper_fence']), 'results/indicator_outliers.csv')
    details = []
    for feature in FEATURES:
        lo, hi = frame.loc[frame[feature].idxmin()], frame.loc[frame[feature].idxmax()]
        details.append(f'- {LABELS[feature]}: {lo[feature]:.2f} in {lo.geo_name} to {hi[feature]:.2f} in {hi.geo_name}; neighborhood mean {frame[feature].mean():.2f}, median {frame[feature].median():.2f}.')
    write_doc('results/descriptive_findings.md', f'''# Descriptive evidence

Reporting year {YEAR}; {len(frame)} complete-case Ortsteile of {len(all_rows)} workbook Ortsteile. Every number is computed from the supplied workbook. Percentages have different denominators, documented in analysis/data_dictionary.csv. Means are unweighted neighborhood means, not Bremen population rates. Available-case statistics are exported separately to expose coverage effects.

''' + '\n'.join(details) + f'''

Unemployment versus benefit receipt Spearman correlation: {corr.loc['unemployment','benefit_receipt']:.3f}. These are descriptive associations within the covered sample, with no causal or significance claims. The overlapping constructs motivate sensitivity tests.

Figures: indicator_distributions.png shows the spread; benefit_receipt_comparison.png shows the highest 15 observed shares; correlation_matrix.png shows pairwise Spearman association. Exact figure data is the complete-case subset of ortsteil_analysis_ready.csv. Excluded places may differ systematically; rankings are not citywide censuses of every neighborhood.

Historical changes and trend charts are withheld: boundary and definition stability are not established. Historical observation tables remain available for source review, without change estimates. Nominal taxpayer income is not used as current household income.
''')
    return stats

if __name__ == '__main__':
    print(run().to_string(index=False))
