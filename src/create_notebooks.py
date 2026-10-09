import json
import nbformat as nbf
from nbclient import NotebookClient
from analysis_common import ROOT, write_doc

SETUP = '''from pathlib import Path
import sys
import pandas as pd
from IPython.display import display, Image, Markdown
ROOT = Path.cwd()
if not (ROOT / 'src').is_dir():
    ROOT = ROOT.parent
assert (ROOT / 'src' / 'analysis_common.py').exists(), 'Run from root or notebooks directory'
sys.path.insert(0, str(ROOT / 'src'))
from analysis_common import load_analysis, FEATURES
def read(relative):
    return pd.read_csv(ROOT / relative, dtype={'geo_code': str})
def show_figure(name):
    display(Image(filename=str(ROOT / 'results' / 'figures' / name)))
'''

SPECIFICATIONS = [
    ('01_indicator_exploration', 'Audit six candidates and inspect units, reporting years and coverage before selection.',
     "selection = read('analysis/indicator_selection.csv')\ncoverage = read('analysis/coverage_summary.csv')",
     "display(selection[['feature','english_name','unit','latest_year','latest_covered','role','disadvantage_direction']])\ndisplay(coverage[coverage.year.isin([2020,2024])])",
     "display(Markdown((ROOT / 'analysis/indicator_audit.md').read_text(encoding='utf-8')))"),
    ('02_data_validation', 'Reconstruct sources and validate the 2024 Ortsteil matrix; show blocked historical gates.',
     "from build_analysis_dataset import run\nframe = run()",
     "display(frame[['geo_code','geo_name','year'] + FEATURES + ['scoring_eligible']].head(12))\ndisplay(read('analysis/source_audit.csv'))\ndisplay(read('analysis/excluded_neighborhoods.csv')[['geo_code','geo_name','exclusion_reason']])\nassert frame.geo_code.is_unique\nassert frame.year.eq(2024).all()",
     "display(Markdown((ROOT / 'analysis/dataset_validation.md').read_text(encoding='utf-8')))"),
    ('03_descriptive_analysis', 'Calculate neighborhood-level statistics and descriptive visualizations from actual annual data.',
     "from descriptive_analysis import run\nframe = load_analysis()",
     "statistics = run()\ndisplay(statistics)\ndisplay(read('results/indicator_correlations.csv'))",
     "show_figure('indicator_distributions.png')\nshow_figure('benefit_receipt_comparison.png')\nshow_figure('correlation_matrix.png')\ndisplay(Markdown((ROOT / 'results/descriptive_findings.md').read_text(encoding='utf-8')))"),
    ('04_composite_index', 'Calculate an equal-weight, directed min-max composite score. Higher means greater measured disadvantage.',
     "from composite_index import run, normalize, calculate\nframe = load_analysis()",
     "results = run()\ndisplay(results.head(15))\ndisplay(read('results/composite_normalized_indicators.csv').head())\nassert results.composite_score.between(0,1).all()\nassert results.composite_score.is_monotonic_decreasing",
     "show_figure('composite_ranking.png')\ndisplay(Markdown('Equal weights are 1/3 per indicator. Employment is reversed. Scores use observed sample endpoints. See ../docs/methods.md for formulas and compensability assumptions.'))"),
    ('05_topsis', 'Calculate vector-normalized TOPSIS closeness to the disadvantage ideal on the same matrix.',
     "from topsis import run, components\nframe = load_analysis()",
     "results = run()\ndisplay(results.head(15))\ndisplay(read('results/topsis_ideals.csv'))\nassert results.topsis_score.between(0,1).all()\nassert results.topsis_score.is_monotonic_decreasing",
     "display(Markdown('Higher unemployment/benefits and lower employment define the disadvantage ideal. High closeness means greater relative disadvantage, not greater desirability. Distances and weighted matrix are exported. See ../docs/methods.md.'))"),
    ('06_kmeans', 'Identify nominal socioeconomic profiles, select k using diagnostics, and assess fitting stability.',
     "from clustering import run\nframe = load_analysis()",
     "clusters = run()\ndisplay(read('results/kmeans_diagnostics.csv'))\ndisplay(read('results/cluster_profiles.csv'))\ndisplay(read('results/cluster_stability.csv').groupby('experiment').adjusted_rand_index.agg(['mean','min','max']))\nassert 'rank' not in clusters.columns",
     "show_figure('cluster_profiles.png')\nshow_figure('cluster_projection.png')\nshow_figure('kmeans_diagnostics.png')\ndisplay(Markdown('Profile labels are nominal. K-means uses three standardized variables; PCA is display only. Highest silhouette subject to minimum cluster size three selects k. Stability does not prove profile validity.'))"),
    ('07_methods_comparison', 'Compare rank agreement, discrepancies, profile interpretation and methodological trade-offs.',
     "composite = read('results/composite_index_results.csv')\ntopsis = read('results/topsis_results.csv')\nclusters = read('results/kmeans_results.csv')",
     "assert set(composite.geo_code) == set(topsis.geo_code) == set(clusters.geo_code)\ndisplay(read('results/ranking_agreement_summary.csv'))\ndisplay(read('results/ranking_agreement.csv').head(10))\ndisplay(read('results/method_comparison_table.csv'))",
     "show_figure('ranking_agreement.png')\ndisplay(Markdown((ROOT / 'results/method_comparison.md').read_text(encoding='utf-8')))"),
    ('08_sensitivity_analysis', 'Evaluate weight choices, indicator omission/inclusion and clustering stability without claiming confidence intervals.',
     "from sensitivity_analysis import run\nframe = load_analysis()",
     "summary = run()\ndisplay(summary[~summary.scenario.str.startswith('plausible_random')])\ndisplay(read('results/weight_rank_ranges.csv').head(15))\ndisplay(read('results/cluster_stability_summary.csv'))",
     "show_figure('weight_sensitivity.png')\ndisplay(Markdown((ROOT / 'results/robustness_findings.md').read_text(encoding='utf-8')))")]

def run():
    folder = ROOT / 'notebooks'
    folder.mkdir(exist_ok=True)
    status = []
    for name, purpose, loading, calculation, presentation in SPECIFICATIONS:
        notebook = nbf.v4.new_notebook()
        notebook.metadata.kernelspec = {'display_name':'Python 3','language':'python','name':'python3'}
        notebook.cells = [
            nbf.v4.new_markdown_cell('# ' + name.replace('_',' ') + '\n\n' + purpose + '\n\nTechnical evidence for the confirmed Bremen project. Primary comparison: 2024 Ortsteile. No historical change claim; original data preserved.'),
            nbf.v4.new_markdown_cell('## Setup and relative paths'), nbf.v4.new_code_cell(SETUP),
            nbf.v4.new_markdown_cell('## Data loading and preparation'), nbf.v4.new_code_cell(loading),
            nbf.v4.new_markdown_cell('## Calculation and validation'), nbf.v4.new_code_cell(calculation),
            nbf.v4.new_markdown_cell('## Results, visualization and interpretation'), nbf.v4.new_code_cell(presentation),
            nbf.v4.new_markdown_cell('## Assumptions and limits\n\nComplete-case scoring; no imputation. Different indicator denominators, correlated labour-market measures, unavailable 2024 income, unknown exact reference dates and incomplete historical boundary/definition metadata limit interpretation. Rankings apply only to the covered sample. Clusters are nominal. See analysis/dataset_validation.md and docs/methods.md. Tables are exported by reusable scripts; important figures appear in results/figures/.')]
        path = folder / (name + '.ipynb')
        print('Executing ' + path.name, flush=True)
        try:
            NotebookClient(notebook, timeout=900, kernel_name='python3', resources={'metadata':{'path':str(folder)}}).execute()
        except Exception as exc:
            nbf.write(notebook,path)
            status.append({'notebook':path.name,'passed':False,'error':str(exc)})
            write_doc('analysis/notebook_execution.json',json.dumps(status,indent=2))
            raise
        nbf.write(notebook,path)
        status.append({'notebook':path.name,'passed':True,'code_cells':sum(c.cell_type=='code' for c in notebook.cells)})
        write_doc('analysis/notebook_execution.json',json.dumps(status,indent=2))
    return status

if __name__ == '__main__':
    run()
