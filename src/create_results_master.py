"""Regenerate the master documents from saved quantitative outputs only."""
import hashlib
import json
from pathlib import Path

import nbformat
from nbclient import NotebookClient
import pandas as pd

import create_master_notebook as presentation

ROOT = presentation.ROOT
NAME = presentation.NAME
HEADINGS = ['Dataset Summary', 'Indicators and Coverage', 'Descriptive Statistics',
            'Neighborhood Comparisons', 'Composite Index', 'TOPSIS', 'K-means',
            'Ranking Comparison', 'Sensitivity and Stability',
            'Four-Layer Architecture Diagram', 'Sources and Reproducibility']
METADATA = [
    'Primary reporting year: 2024. Geographic level: Ortsteil. No imputation.',
    'Baseline: unemployment, employment, benefit_receipt. Coverage proportions are fractions.',
    '2024; unweighted neighborhood statistics; sample standard deviation (ddof=1); rates in percent.',
    '2024 complete-case neighborhoods; 2020 income context shown separately.',
    'Directed min-max normalization; equal weights (1/3 each); score 0-1; descending competition ranks.',
    'Column vector normalization; equal weights (1/3 each); Euclidean distance; descending closeness ranks.',
    'StandardScaler (ddof=0); KMeans; k-means++; n_init=30; random_state=42; nominal profile labels.',
    'Same 2024 row set and three indicators; rank 1 = greatest measured disadvantage.',
    'Fixed ranking sample; alternative weights and feature sets; 30 initialization and 30 bootstrap refits.',
    'Existing architecture figure.',
    'Saved results, source references, calculation settings and script links.']
T = presentation.evidence_table
F = presentation.figure
P = presentation.paragraph
read = presentation.read


def build_sections():
    all_rows = read('data/processed/ortsteil_analysis_ready.csv')
    included = all_rows[all_rows.scoring_eligible]
    composite = read('results/composite_index_results.csv')
    topsis = read('results/topsis_results.csv')
    clusters = read('results/kmeans_results.csv')
    assert included.geo_code.is_unique and included.year.eq(2024).all()
    assert set(included.geo_code) == set(composite.geo_code) == set(topsis.geo_code) == set(clusters.geo_code)
    assert read('analysis/output_verification.csv').passed.all()
    selection = read('analysis/indicator_selection.csv').copy()
    selection.available_years = selection.available_years.str.replace(';','; ',regex=False)
    definitions = {
        'unemployment': 'Registered unemployed / (social-insurance employees + registered unemployed).',
        'employment': 'Social-insurance employees at residence / population aged 15 to under 65; excludes self-employment and civil servants.',
        'benefit_receipt': 'SGB II entitled recipients / population under 65.',
        'child_benefits': 'SGB II entitled recipients under 15 / population under 15.',
        'income_median': 'Median total income per taxpayer, thousand EUR.',
        'single_parents': 'Single-parent households / main-residence households with children.'}
    selection['measurement_definition'] = selection.feature.map(definitions)
    sections = [[] for _ in HEADINGS]
    summary = pd.DataFrame([
        ['Primary reporting year', int(included.year.iloc[0])],
        ['Workbook Ortsteile', len(all_rows)], ['Complete-case Ortsteile',len(included)],
        ['Excluded Ortsteile',len(all_rows)-len(included)],
        ['Baseline indicators',3], ['Imputed values',0]],columns=['Field','Value'])
    sections[0] = [T('Dataset counts',summary),
        T('Statistical source observations, missing values and reporting years',read('data/processed/validation_summary.csv')),
        T('Source reconstruction audit; JSON records are metadata',read('analysis/source_audit.csv')),
        T('Source inventory; catalogue years are title metadata, not observation years',read('data_inventory.csv')[['dataset_name','source_type','years','processed_records']]),
        T('Excluded Ortsteile, 2024',read('analysis/excluded_neighborhoods.csv')[['geo_code','geo_name','exclusion_reason']]),
        T('Validation metadata',pd.DataFrame([
            ['CSV format','CP1252; semicolon; decimal comma'],['Excel format','BIFF XLS; xlrd; numeric cells'],
            ['Missing data','Retained; complete-case scoring'],['Aggregate geographic levels','Excluded from scoring'],
            ['Name alias','Überseestadt / Ueberseestadt: code 437'],
            ['Historical change calculations','Not produced; boundary and definition stability unverified'],
            ['Within-year reference dates','Unverified']],columns=['Field','Status']))]
    sections[1] = [T('Indicators: original names, units, available years and scoring direction',selection[['feature','original_german_name','english_name','unit','available_years','role','disadvantage_direction']]),
        T('Measurement definitions',selection[['feature','measurement_definition']]),
        T('Indicator sources and latest coverage',selection[['feature','source_file','source_sheet','latest_year','latest_covered','total_ortsteile','latest_coverage_proportion','latest_missing_rate']]),
        T('Coverage by indicator and reporting year',read('analysis/coverage_summary.csv'))]
    sections[2] = [T('Complete-case statistics, 2024; percent',read('results/descriptive_statistics.csv')[['feature','count','mean','std','min','25%','50%','75%','max']].rename(columns={'50%':'median'})),
        T('Available-case statistics, 2024; percent',read('results/available_case_statistics.csv')[['feature','count','mean','std','min','25%','50%','75%','max']].rename(columns={'50%':'median'})),
        F('results/figures/indicator_distributions.png','2024 indicator distributions; percent; complete cases.'),
        T('Spearman indicator correlations; unitless',read('results/indicator_correlations.csv')),
        T('Pearson indicator correlations; unitless',read('results/pearson_correlations.csv')),
        F('results/figures/correlation_matrix.png','2024 Spearman correlations; unitless.'),
        T('1.5-IQR flags; observations retained',read('results/indicator_outliers.csv'))]
    sections[3] = [T('All included Ortsteile, 2024; indicator values in percent',included[['geo_code','geo_name','year','unemployment','employment','benefit_receipt']].sort_values('geo_code')),
        F('results/figures/benefit_receipt_comparison.png','2024 under-65 SGB II receipt; percent; highest 15 observed shares.'),
        F('results/figures/income_context_2020.png','2020 only; median income per taxpayer in 1000 EUR; SGB II receipt in percent.')]
    sections[4] = [T('Complete composite scores and ranks, 2024; score 0-1',composite),
        F('results/figures/composite_ranking.png','2024 composite scores; equal indicator weights; highest 15 scores.'),
        T('Directed normalized indicators, 2024; 0-1',read('results/composite_normalized_indicators.csv'))]
    sections[5] = [T('Complete TOPSIS closeness, ranks and normalized distances, 2024',topsis),
        T('TOPSIS weights and ideal profiles',read('results/topsis_ideals.csv')),
        T('TOPSIS weighted normalized matrix, 2024',read('results/topsis_weighted_matrix.csv')),
        F('results/figures/ranking_agreement.png','2024 TOPSIS and composite ranks.')]
    profiles = read('results/cluster_profiles.csv')
    sections[6] = [T('Cluster-count diagnostics',read('results/kmeans_diagnostics.csv')),
        T('Cluster sizes and mean percentages, 2024',profiles[['cluster','n','unemployment_mean','employment_mean','benefit_receipt_mean']]),
        T('All cluster assignments, 2024; labels are nominal',clusters[['geo_code','geo_name','year','cluster']].sort_values(['cluster','geo_code']))]
    for feature in ['unemployment','employment','benefit_receipt']:
        sections[6].append(T(feature+' cluster statistics, 2024; percent',profiles[['cluster','n']+[feature+'_'+s for s in ['mean','std','min','max']]]))
    sections[6] += [F('results/figures/cluster_profiles.png','2024 cluster mean percentages; labels are nominal.'),
        F('results/figures/cluster_projection.png','2024 PCA projection; standardized input; unitless coordinates.'),
        T('PCA explained variance ratios',read('results/pca_projection_variance.csv')),
        F('results/figures/kmeans_diagnostics.png','Silhouette by tested cluster count; unitless.')]
    sections[7] = [T('Rank agreement statistics, 2024',read('results/ranking_agreement_summary.csv')),
        T('All pairwise rank differences, 2024',read('results/ranking_agreement.csv'))]
    scenarios = read('results/sensitivity_summary.csv')
    named = scenarios[~scenarios.scenario.str.startswith('plausible_random')]
    random = scenarios[scenarios.scenario.str.startswith('plausible_random')]
    random_summary = random.groupby('method').agg(scenarios=('scenario','count'),
        minimum_rank_correlation=('spearman_vs_baseline','min'), mean_rank_correlation=('spearman_vs_baseline','mean'),
        maximum_rank_movement=('max_absolute_rank_change','max'), minimum_top10_overlap=('top10_overlap','min')).reset_index()
    rows = read('results/sensitivity_results.csv')
    settings = rows[~rows.scenario.str.startswith('plausible_random')][['scenario','method','features','weights']].drop_duplicates()
    for c in ['features','weights']:
        settings[c] = settings[c].str.replace(';','; ',regex=False)
    ranges = read('results/weight_rank_ranges.csv').pivot(index=['geo_code','geo_name'],columns='method',values=['min','max','median'])
    ranges.columns = ['_'.join(c) for c in ranges.columns]
    sections[8] = [T('Named sensitivity scenarios: feature sets and weight vectors',settings),
        T('Named scenario rank robustness statistics',named),
        T('200 constrained random weight scenarios per method: summary',random_summary),
        T('Every random-weight scenario: calculated robustness statistics',random),
        T('Neighborhood rank ranges across random weight scenarios; not confidence intervals',ranges.reset_index()),
        T('Initialization and bootstrap clustering stability: adjusted Rand index',read('results/cluster_stability_summary.csv')),
        T('All clustering refit stability statistics',read('results/cluster_stability.csv')),
        F('results/figures/weight_sensitivity.png','2024 composite rank ranges; 200 weight scenarios; baseline highest 15.')]
    sections[9] = [F('architecture/architecture_diagram.png','Existing four-layer architecture diagram.')]
    settings = pd.DataFrame([
        ['Primary inputs','2024; complete cases; unemployment, employment, benefit_receipt'],
        ['Composite','Min-max; employment reversed; equal weights; descending minimum-tie rank'],
        ['TOPSIS','Vector normalization; equal weights; Euclidean distances; high unemployment/benefits and low employment ideal'],
        ['K-means','StandardScaler; k=2..8; highest silhouette with minimum cluster size 3; n_init=30; seed=42'],
        ['Random weights','200 draws; Dirichlet(3,3,3); weights constrained to [0.10,0.60]; seed=2024'],
        ['Cluster stability','30 initialization seeds; 30 bootstrap neighborhood refits; ARI on fixed full sample'],
        ['Display precision','3 decimal places; stored CSV precision unchanged']],columns=['Calculation','Setting'])
    scripts = pd.DataFrame([
        ['Preparation','src/prepare_data.py'],['Analysis-ready dataset','src/build_analysis_dataset.py'],
        ['Descriptive statistics','src/descriptive_analysis.py'],['Composite','src/composite_index.py'],
        ['TOPSIS','src/topsis.py'],['K-means','src/clustering.py'],['Sensitivity','src/sensitivity_analysis.py'],
        ['Figures and packages','src/package_results.py'],['Verification','src/verify_outputs.py'],
        ['Results-only master exports','src/create_results_master.py']],columns=['Output','Script'])
    versions = json.loads((ROOT/'docs/environment_versions.json').read_text(encoding='utf-8'))
    sections[10] = [T('Calculation settings',settings),
        T('Dataset references',pd.DataFrame([
            ['Primary statistics','Datentabelle.xls','https://www.statistik.bremen.de/datenangebote/bremer-ortsteilatlas-15228'],
            ['Historical CSV statistics','22 ST*.csv files','data_inventory.csv'],
            ['Catalogue metadata','bremen_data.json','data/processed/bremen_open_data_catalog.csv'],
            ['Raw-source checksums','analysis/source_manifest.csv','SHA-256']],columns=['Source','Local file','Reference'])),
        T('Scripts used',scripts),
        P('\n'.join(f'[{r.Script}]({r.Script})' for r in scripts.itertuples())),
        T('Exact tested direct dependencies',pd.DataFrame(versions.items(),columns=['Package','Version'])),
        P('Rebuild these documents only: `python src/create_results_master.py`'),
        P('Full precision: `results/*.csv`. Full scenario scores: `results/sensitivity_results.csv`. Original calculation settings: `docs/methods.md`.')]
    return sections


def protected_files():
    paths = [p for folder in ['src','data','analysis','results','architecture','group_results','notebooks','docs']
             for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in str(p)]
    paths += list(ROOT.glob('ST*.csv'))
    paths += [ROOT/p for p in ['Datentabelle.xls','bremen_data.json','requirements.txt','README.md',
                              'data_inventory.csv','indicator_catalog.csv','data_quality_report.md','TECHNICAL_COMPLETION_REPORT.md']]
    paths = [p for p in paths if p.name != 'results_master_export_validation.json']
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def run():
    before = protected_files()
    sections = build_sections()
    notebook = nbformat.v4.new_notebook()
    notebook.metadata.kernelspec = {'display_name':'Python 3','language':'python','name':'python3'}
    toc = '# Bremen Statistical Results\n\n2024 Ortsteile; separate 2020 income context.\n\n## Contents\n\n'+'\n'.join(f'{i+1}. [{h}](#section-{i+1})' for i,h in enumerate(HEADINGS))
    setup = "from pathlib import Path\nimport sys\nROOT = Path.cwd()\nif not (ROOT / 'src').is_dir():\n    ROOT = ROOT.parent\nsys.path.insert(0, str(ROOT / 'src'))\nfrom create_results_master import build_sections\nfrom create_master_notebook import display_section\nsections = build_sections()"
    hidden = {'jupyter':{'source_hidden':True}}
    notebook.cells = [nbformat.v4.new_markdown_cell(toc),nbformat.v4.new_code_cell(setup,metadata=hidden)]
    for i,h in enumerate(HEADINGS):
        notebook.cells += [nbformat.v4.new_markdown_cell(f'<a id="section-{i+1}"></a>\n\n## {i+1}. {h}\n\n'+METADATA[i]),
                          nbformat.v4.new_code_cell(f'display_section(sections[{i}])',metadata=hidden)]
    print('Executing results-only master; loading saved outputs, no analysis rerun.',flush=True)
    NotebookClient(notebook,timeout=300,kernel_name='python3',resources={'metadata':{'path':str(ROOT)}}).execute()
    path = ROOT/(NAME+'.ipynb')
    nbformat.write(notebook,path)
    code = [c for c in notebook.cells if c.cell_type=='code']
    assert all(c.execution_count is not None and not any(o.output_type=='error' for o in c.outputs) for c in code)
    # Reuse the original presentation helpers without editing the original generator.
    presentation.HEADINGS = HEADINGS
    presentation.PURPOSES = METADATA
    presentation.TITLE = '2024 Ortsteil statistical results; separate 2020 income context.'
    presentation.export_html(sections)
    pages = presentation.export_pdf(sections)
    assert before == protected_files(), 'Protected project files changed'
    status = {'content':'results only','sections':len(sections),'fresh_kernel_execution':'passed',
              'executed_code_cells':len(code),'pdf_pages':pages,
              'image_occurrences':sum(b[0]=='image' for s in sections for b in s),
              'table_occurrences':sum(b[0]=='table' for s in sections for b in s),
              'protected_files_unchanged':len(before),'analytical_methods_rerun':False,
              'outputs':[NAME+suffix for suffix in ['.ipynb','.pdf','.html']]}
    (ROOT/'docs/results_master_export_validation.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
    print(json.dumps(status,indent=2),flush=True)


if __name__=='__main__':
    run()
