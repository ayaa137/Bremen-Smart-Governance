"""Create a fixed-length results summary from verified saved tables and figures."""
import base64
import hashlib
import html
import json
from pathlib import Path
import textwrap

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import nbformat
from nbclient import NotebookClient
import pandas as pd

from create_master_notebook import read, display_section

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'group_results' / 'RESULTS_SUMMARY'
NAME = 'Bremen_Smart_Governance_RESULTS_SUMMARY'
LABELS = {'unemployment':'Unemployment', 'employment':'Employment', 'benefit_receipt':'SGB II under 65'}


def table(title, frame, widths=None):
    return ('table', title, frame, widths)


def image(path, label):
    return ('image', path, label)


def text(label):
    return ('text', label)


def rankings(frame, column, n, bottom=False):
    selected = frame.tail(n) if bottom else frame.head(n)
    return selected[['rank','geo_code','geo_name',column]].rename(columns={
        'rank':'Rank','geo_code':'Code','geo_name':'Ortsteil',column:'Score'})


def build_pages():
    full = read('data/processed/ortsteil_analysis_ready.csv')
    included = full[full.scoring_eligible]
    features = ['unemployment','employment','benefit_receipt']
    assert full.geo_code.is_unique and included.year.eq(2024).all()
    assert (len(full),len(included),len(full)-len(included)) == (88,79,9)
    assert read('analysis/output_verification.csv').passed.all()
    composite = read('results/composite_index_results.csv')
    topsis = read('results/topsis_results.csv')
    profiles = read('results/cluster_profiles.csv')
    assignments = read('results/kmeans_results.csv')
    assert set(included.geo_code)==set(composite.geo_code)==set(topsis.geo_code)==set(assignments.geo_code)
    assert composite.composite_score.is_monotonic_decreasing and topsis.topsis_score.is_monotonic_decreasing
    assert profiles.n.sum()==len(included)
    diag = read('results/kmeans_diagnostics.csv')
    selected_k = len(profiles)
    selected_diag = diag[diag.k==selected_k]
    selection = read('analysis/indicator_selection.csv').set_index('feature').loc[features].reset_index()
    source = read('analysis/source_audit.csv').rename(columns={'source':'Source','records':'Records','missing':'Missing'})
    source['Reporting years'] = ['1969-2025; indicator-specific','2010-2016','Catalogue metadata']
    missing = pd.DataFrame({'Indicator':[LABELS[f] for f in features],
                           'Observed':[full[f].notna().sum() for f in features],
                           'Missing':[full[f].isna().sum() for f in features]})
    overview = pd.DataFrame([
        ['Reporting year','2024'],['Geographic level','Bremen Ortsteile'],['Total Ortsteile',len(full)],
        ['Included',len(included)],['Excluded',len(full)-len(included)],['Baseline indicators',len(features)]],columns=['Field','Value'])
    indicators = selection[['original_german_name','english_name','unit','disadvantage_direction']].copy()
    indicators['Year'] = 2024
    indicators.columns=['Original German definition','English name','Unit','Direction','Year']
    indicators = indicators[['Original German definition','English name','Unit','Year','Direction']]
    stats = read('results/descriptive_statistics.csv')[['feature','count','mean','50%','std','min','max']].copy()
    stats.feature = stats.feature.map(LABELS)
    stats.columns=['Indicator','n','Mean','Median','SD','Minimum','Maximum']
    corr = read('results/indicator_correlations.csv').rename(columns={'feature':'Indicator',**LABELS})
    corr.Indicator = corr.Indicator.map(LABELS)
    cluster_means = profiles[['cluster','n','unemployment_mean','employment_mean','benefit_receipt_mean']].copy()
    cluster_means.columns=['Profile','n','Unemployment (%)','Employment (%)','SGB II under 65 (%)']
    disagreement = read('results/ranking_agreement.csv').head(5)[['geo_name','composite_rank','topsis_rank','rank_difference_topsis_minus_composite','absolute_rank_difference']].copy()
    disagreement.columns=['Ortsteil','Composite rank','TOPSIS rank','TOPSIS - composite','Absolute difference']
    methods = pd.DataFrame([
        ['Composite','Score [0,1]; descending rank','Directed min-max; equal 1/3 weights'],
        ['TOPSIS','Closeness [0,1]; descending rank','Vector norm; equal 1/3 weights; Euclidean distance'],
        ['K-means',f'{selected_k} nominal profiles','StandardScaler; n_init=30; random_state=42']],columns=['Method','Output','Settings'])
    scenarios = read('results/sensitivity_summary.csv')
    names = {'equal':'Equal weights','domain_balanced':'Domain-balanced',
             'unemployment_emphasis':'Unemployment emphasis','employment_emphasis':'Employment emphasis'}
    alternative = scenarios[scenarios.scenario.isin(names)].copy()
    alternative.scenario = alternative.scenario.map(names)
    alternative = alternative[['scenario','method','spearman_vs_baseline','mean_absolute_rank_change','max_absolute_rank_change','top10_overlap']]
    alternative.columns=['Scenario','Method','Spearman','Mean abs. movement','Max movement','Top-10 overlap']
    weight_rows = read('results/sensitivity_results.csv')
    weights = weight_rows[(weight_rows.method=='composite') & weight_rows.scenario.isin(names)][['scenario','weights']].drop_duplicates().copy()
    for i, f in enumerate(features):
        weights[LABELS[f]] = weights.weights.str.split(';').str[i].astype(float)
    weights.scenario = weights.scenario.map(names)
    weights = weights[['scenario']+[LABELS[f] for f in features]].rename(columns={'scenario':'Scenario'})
    omission = scenarios[scenarios.scenario.str.startswith('omit_') | scenarios.scenario.eq('include_child_benefits')].copy()
    omission = omission[['scenario','method','spearman_vs_baseline','max_absolute_rank_change','top10_overlap']]
    omission.columns=['Feature scenario','Method','Spearman','Max movement','Top-10 overlap']
    # Presentation-only aggregation of previously saved scenario diagnostics.
    random = scenarios[scenarios.scenario.str.startswith('plausible_random')]
    random_summary = random.groupby('method').agg(draws=('scenario','count'),
        min_spearman=('spearman_vs_baseline','min'),max_movement=('max_absolute_rank_change','max'),
        min_top10_overlap=('top10_overlap','min')).reset_index()
    random_summary.columns=['Method','Draws','Minimum Spearman','Max movement','Minimum top-10 overlap']
    sources = pd.DataFrame([
        ['Primary statistics','Datentabelle.xls; Bremer Ortsteilatlas','2024 baseline'],
        ['Historical statistics','22 ST*.csv files','2010-2016'],
        ['Discovery metadata','bremen_data.json','Not observations']],columns=['Source','File / dataset','Reporting period'])
    paths = pd.DataFrame([
        ['Complete notebook/PDF','Bremen_Smart_Governance_COMPLETE_ANALYSIS.ipynb / .pdf'],
        ['Full scores, rankings, profiles','results/composite_index_results.csv; topsis_results.csv; kmeans_results.csv'],
        ['Full sensitivity rows','results/sensitivity_results.csv'],
        ['Preparation / validation','src/prepare_data.py; src/build_analysis_dataset.py; src/verify_outputs.py'],
        ['Statistics / scoring','src/descriptive_analysis.py; src/composite_index.py; src/topsis.py'],
        ['Clustering / sensitivity','src/clustering.py; src/sensitivity_analysis.py'],
        ['Settings / dependencies','docs/methods.md; requirements.txt; docs/environment_versions.json'],
        ['Regenerate this summary','python src/create_results_summary.py']],columns=['Artifact','Repository-relative path'])
    pages = [
        ('Dataset Overview',[
            table('2024 analytical dataset',overview,[.42,.58]),
            table('Source counts; source-level missing observations',source[['Source','Records','Missing','Reporting years']],[.40,.13,.13,.34]),
            table('2024 baseline coverage out of 88 Ortsteile',missing,[.60,.20,.20]),
            text('Complete-case scoring; no imputation. Rates and charts use the same 79 Ortsteile unless labeled otherwise.')]),
        ('Socioeconomic Indicators',[
            table('Baseline indicators; source: Datentabelle.xls',indicators,[.48,.25,.06,.08,.13]),
            text('Unemployment denominator: social-insurance employees + registered unemployed. Employment denominator: population aged 15 to under 65. SGB II denominator: population under 65.')]),
        ('Descriptive Statistics',[
            table('2024; percent; unweighted Ortsteile; SD uses ddof=1',stats,[.28,.07,.13,.13,.13,.13,.13]),
            table('Spearman indicator correlations; unitless',corr,[.34,.22,.22,.22])]),
        ('Indicator Distributions',[image('results/figures/indicator_distributions.png','2024; percent; n=79.')]),
        ('Indicator Correlations',[image('results/figures/correlation_matrix.png','2024 Spearman correlation; unitless; n=79.')]),
        ('Neighborhood Comparison',[image('results/figures/benefit_receipt_comparison.png','2024 under-65 SGB II receipt; percent; highest 15 observed shares.')]),
        ('Composite Index: Selected Rankings',[
            table('Top 10; 2024; score 0-1; rank 1 = greatest measured disadvantage',rankings(composite,'composite_score',10),[.10,.10,.57,.23]),
            table('Bottom 5; 2024; descending ranks retained',rankings(composite,'composite_score',5,True),[.10,.10,.57,.23]),
            text('Normalization: (x-min)/(max-min); employment reversed. Weights: 1/3 per indicator. Descending competition ranks.')]),
        ('Composite Index: Ranking Chart',[image('results/figures/composite_ranking.png','2024 equal-weight composite scores; highest 15; score 0-1.')]),
        ('TOPSIS: Selected Rankings',[
            table('Top 10; 2024; disadvantage closeness 0-1',rankings(topsis,'topsis_score',10),[.10,.10,.57,.23]),
            table('Bottom 5; 2024; descending ranks retained',rankings(topsis,'topsis_score',5,True),[.10,.10,.57,.23]),
            text('Vector norm; equal 1/3 weights; Euclidean distances; ideal: high unemployment/SGB II, low employment; C=D-/(D+ + D-).')]),
        ('K-means: Profile Statistics',[
            table(f'Silhouette diagnostics; selected k={selected_k}',diag[['k','silhouette','minimum_cluster_size']], [.20,.40,.40]),
            table('2024 profile sizes and mean indicator percentages',cluster_means,[.20,.10,.23,.23,.24]),
            text('Nominal labels. StandardScaler (ddof=0); k-means++; n_init=30; seed=42. Tested k=2..8; maximum silhouette subject to minimum profile size 3.')]),
        ('K-means: Profile Chart',[image('results/figures/cluster_profiles.png','2024 profile means; percent; labels are nominal.')]),
        ('K-means: PCA Projection',[image('results/figures/cluster_projection.png','2024; standardized coordinates; PCA display only. K-means inputs: three standardized indicators.')]),
        ('Ranking and Method Comparison',[
            table('2024 rank correlations',read('results/ranking_agreement_summary.csv').rename(columns={'spearman':'Spearman','kendall_tau_b':'Kendall tau-b','n':'n'}),[.40,.40,.20]),
            table('Five largest absolute rank disagreements',disagreement,[.30,.15,.15,.20,.20]),
            table('Method outputs and settings',methods,[.16,.32,.52])]),
        ('Ranking Comparison: Scatter Plot',[image('results/figures/ranking_agreement.png','2024; n=79; rank 1 = greatest measured disadvantage.')]),
        ('Sensitivity: Alternative Weights',[
            table('Weight vectors: unemployment / employment / SGB II',weights,[.40,.20,.20,.20]),
            table('Baseline and alternative-weight statistics; n=79; same row set',alternative,[.29,.13,.13,.17,.14,.14])]),
        ('Sensitivity: Feature Sets and Cluster Stability',[
            table('Feature-selection scenarios; n=79',omission,[.32,.16,.18,.17,.17]),
            table('200 constrained random weight draws per method; seed=2024',random_summary,[.18,.12,.25,.20,.25]),
            table('K-means refit stability: adjusted Rand index',read('results/cluster_stability_summary.csv').rename(columns={'experiment':'Refit','mean':'Mean ARI','min':'Min ARI','max':'Max ARI'}),[.46,.18,.18,.18]),
            text('Clustering: 30 initialization seeds and 30 bootstrap refits. Random weights: Dirichlet(3,3,3), each weight in [0.10,0.60].')]),
        ('Sensitivity: Rank-Range Visualization',[image('results/figures/weight_sensitivity.png','2024; 200 weight scenarios; baseline highest 15; scenario ranges, not confidence intervals.')]),
        ('Four-Layer Architecture',[image('architecture/architecture_diagram.png','Existing four-layer diagram; implemented and proposed components labeled.')]),
        ('Sources and Reproducibility',[
            table('Dataset references',sources,[.24,.52,.24]),
            table('Complete outputs and reusable scripts',paths,[.29,.71]),
            text('Official atlas reference: https://www.statistik.bremen.de/datenangebote/bremer-ortsteilatlas-15228'),
            text('Historical change estimates not included: boundary and definition comparability checks remain incomplete. Exact within-year reference dates remain unverified. Display: 3 decimals; stored result precision unchanged.')])]
    # Combine the related indicator and descriptive tables into one dense reference page.
    pages[1] = ('Indicators and Descriptive Statistics', pages[1][1] + pages[2][1])
    del pages[2]
    assert len(pages)==18
    return pages


def fmt(value):
    if pd.isna(value):
        return '—'
    return f'{value:.3f}' if isinstance(value,float) else str(value)


def protected_files():
    paths = [p for p in ROOT.rglob('*') if p.is_file() and '.git' not in p.relative_to(ROOT).parts
             and '__pycache__' not in p.parts and OUT not in p.parents]
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def export_pdf(pages):
    with PdfPages(OUT/(NAME+'.pdf')) as pdf:
        for number,(title,blocks) in enumerate(pages,1):
            fig = plt.figure(figsize=(11.69,8.27))
            fig.text(.045,.955,title,fontsize=19,weight='bold',va='top',color='#203e48')
            fig.text(.045,.90,'Bremen | Statistical Results Summary',fontsize=10,color='#53656d')
            fig.text(.045,.028,'Source: supplied municipal datasets; saved verified outputs.',fontsize=8.5,color='#53656d')
            fig.text(.95,.028,f'{number} / {len(pages)}',fontsize=9,ha='right',color='#53656d')
            if len(blocks)==1 and blocks[0][0]=='image':
                _,filename,caption = blocks[0]
                ax = fig.add_axes([.035,.115,.93,.735])
                ax.imshow(plt.imread(ROOT/filename))
                ax.axis('off')
                fig.text(.045,.080,caption,fontsize=10)
            else:
                cursor = .84
                for block in blocks:
                    if block[0]=='text':
                        lines = textwrap.wrap(block[1],width=130,break_on_hyphens=False)
                        fig.text(.045,cursor,'\n'.join(lines),fontsize=10,va='top',linespacing=1.4)
                        cursor -= .024*len(lines)+.015
                        continue
                    _,label,frame,widths = block
                    assert widths is not None
                    label_lines = textwrap.wrap(label,width=115)
                    fig.text(.045,cursor,'\n'.join(label_lines),fontsize=11,weight='bold',va='top')
                    cursor -= .025*len(label_lines)+.012
                    # Page dimensions and character budgets keep all text at a printable 10 points.
                    chars = [max(5,int(w*133)) for w in widths]
                    headers = [textwrap.fill(str(c).replace('_',' '),width=n,break_on_hyphens=False) for c,n in zip(frame.columns,chars)]
                    rows = [[textwrap.fill(fmt(v),width=n,break_on_hyphens=False) for v,n in zip(row,chars)] for row in frame.itertuples(index=False,name=None)]
                    heights = [.021*(1+max(t.count('\n') for t in row))+.015 for row in [headers]+rows]
                    height = sum(heights)
                    assert cursor-height > .068, f'Page {number} table exceeds available area: {label}'
                    ax = fig.add_axes([.045,cursor-height,.91,height])
                    ax.axis('off')
                    t = ax.table(cellText=rows,colLabels=headers,colWidths=widths,cellLoc='left',bbox=[0,0,1,1])
                    t.auto_set_font_size(False)
                    t.set_fontsize(10)
                    for (r,c),cell in t.get_celld().items():
                        cell.set_height(heights[r]/height)
                        cell.set_edgecolor('#c8d3d8')
                        cell.set_linewidth(.6)
                        cell.set_facecolor('#e8f0f2' if r==0 else '#f5f8f9' if r%2==0 else 'white')
                        cell.get_text().set_wrap(False)
                    cursor -= height+.026
                assert cursor > .050, f'Page {number} text exceeds available area'
            pdf.savefig(fig)
            plt.close(fig)


def export_html(pages):
    content = ['<h1>Bremen Statistical Results Summary</h1><nav><ol>']
    content += [f'<li><a href="#page-{i}">{html.escape(title)}</a></li>' for i,(title,_) in enumerate(pages,1)]
    content += ['</ol></nav>']
    for i,(title,blocks) in enumerate(pages,1):
        content.append(f'<section id="page-{i}"><h2>{i}. {html.escape(title)}</h2>')
        for block in blocks:
            if block[0]=='text':
                content.append('<p>'+html.escape(block[1])+'</p>')
            elif block[0]=='table':
                content.append('<h3>'+html.escape(block[1])+'</h3><div class="table">'+block[2].map(fmt).to_html(index=False,escape=True)+'</div>')
            else:
                encoded = base64.b64encode((ROOT/block[1]).read_bytes()).decode('ascii')
                content.append(f'<figure><img src="data:image/png;base64,{encoded}" alt="{html.escape(block[2],quote=True)}"><figcaption>{html.escape(block[2])}</figcaption></figure>')
        content.append('</section>')
    css = 'body{font:16px/1.5 Arial,sans-serif;max-width:1100px;margin:30px auto;padding:0 20px;color:#23333b}h2{margin-top:38px;border-bottom:2px solid #397d8a;padding-bottom:10px}h3{font-size:17px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{border:1px solid #cad4d8;padding:9px;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:#e8f0f2}tr:nth-child(even){background:#f5f8f9}.table{overflow-x:auto}figure{margin:20px 0}img{max-width:100%;height:auto}figcaption{font-size:14px}p{overflow-wrap:anywhere}@media print{section{break-before:page}tr,figure{break-inside:avoid}}'
    (OUT/(NAME+'.html')).write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Bremen Results Summary</title><style>'+css+'</style></head><body>'+''.join(content)+'</body></html>',encoding='utf-8')


def run():
    before = protected_files()
    pages = build_pages()
    OUT.mkdir(parents=True,exist_ok=True)
    n = nbformat.v4.new_notebook()
    n.metadata.kernelspec = {'display_name':'Python 3','language':'python','name':'python3'}
    toc = f'# Bremen Statistical Results Summary\n\nReporting year: 2024. PDF: {len(pages)} pages.\n\n## Contents\n\n'+'\n'.join(f'{i}. [{title}](#page-{i})' for i,(title,_) in enumerate(pages,1))
    setup = "from pathlib import Path\nimport sys\nROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / 'src' / 'create_results_summary.py').is_file())\nsys.path.insert(0, str(ROOT / 'src'))\nfrom create_results_summary import build_pages\nfrom create_master_notebook import display_section\npages = build_pages()"
    hidden = {'jupyter':{'source_hidden':True}}
    n.cells = [nbformat.v4.new_markdown_cell(toc),nbformat.v4.new_code_cell(setup,metadata=hidden)]
    for i,(title,_) in enumerate(pages,1):
        n.cells += [nbformat.v4.new_markdown_cell(f'<a id="page-{i}"></a>\n\n## {i}. {title}'),
                    nbformat.v4.new_code_cell(f'display_section(pages[{i-1}][1])',metadata=hidden)]
    print('Executing summary notebook from a fresh kernel; reading saved results only.',flush=True)
    NotebookClient(n,timeout=300,kernel_name='python3',resources={'metadata':{'path':str(OUT)}}).execute()
    nbformat.write(n,OUT/(NAME+'.ipynb'))
    code = [c for c in n.cells if c.cell_type=='code']
    assert all(c.execution_count is not None and not any(o.output_type=='error' for o in c.outputs) for c in code)
    export_pdf(pages)
    export_html(pages)
    assert before==protected_files(), 'An existing project artifact changed'
    status = {'pdf_pages':len(pages),'fresh_kernel_execution':'passed','executed_code_cells':len(code),
              'saved_images':sum(b[0]=='image' for _,s in pages for b in s),
              'existing_files_unchanged':len(before),'analysis_methods_rerun':False,
              'pdf_table_font_points':10,'summary_only':True,
              'figure_sources':sorted({b[1] for _,s in pages for b in s if b[0]=='image'}),
              'outputs':[NAME+suffix for suffix in ['.ipynb','.pdf','.html']]}
    (OUT/'validation.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
    print(json.dumps(status,indent=2),flush=True)


if __name__=='__main__':
    run()
