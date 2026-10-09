"""Assemble saved project evidence without rerunning or replacing any analysis."""
from pathlib import Path
import base64
import hashlib
import html
import json
import re
import textwrap

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import nbformat
from nbclient import NotebookClient
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
NAME = 'Bremen_Smart_Governance_COMPLETE_ANALYSIS'
TITLE = "Data-Driven Smart Governance: A Comparative Evaluation of Methods for Identifying Socioeconomic Inequalities Across Bremen's Neighborhoods."
QUESTION = "How can different data-driven analytical methods identify socioeconomic disparities across Bremen's neighborhoods and support more transparent and equitable smart governance?"
QUESTIONS = [
    "What socioeconomic and demographic differences exist across Bremen's neighborhoods?",
    'Which indicators are most useful for identifying neighborhood disadvantage?',
    'How do different analytical methods compare in identifying and ranking disadvantaged neighborhoods?',
    'How can Bremen integrate these findings into a smart governance decision-support system?']
HEADINGS = ['Project Overview', 'Datasets and Data Preparation', 'Socioeconomic Indicators',
            'Bremen Neighborhood Analysis', 'Composite Disadvantage Index', 'TOPSIS Analysis',
            'K-means Clustering', 'Comparison of the Three Methods', 'Sensitivity and Robustness',
            'Proposed Smart Governance Architecture', 'Key Findings for Our Four Group Members',
            'Limitations, Sources and Reproducibility']
PURPOSES = [
    'Research notes and verified technical evidence for all four group members; not final university report sections.',
    'Read this section to understand source coverage, cleaning, missingness and the annual comparison gate.',
    'Three indicators form the 2024 baseline. Other audited candidates have clearly separated sensitivity or contextual roles.',
    'The tables and charts describe observed neighborhood differences; they do not explain causes or represent population-weighted Bremen rates.',
    'The composite index averages three indicators after putting them on a common scale and reversing employment. Higher scores mean greater measured disadvantage.',
    'TOPSIS asks how close each neighborhood is to a hypothetical profile with high unemployment and benefits and low employment. Higher closeness means greater measured disadvantage.',
    'K-means groups similar neighborhood profiles. Profile labels are names, not numerical levels or disadvantage rankings.',
    'The ranking methods use identical inputs; clustering adds profile information rather than another ranking.',
    'These checks show how results change with analyst choices and clustering refits. Stability is not proof that an index measures all disadvantage.',
    'The diagram describes four required layers. The local Python analysis is implemented; municipal hosting, acquisition and a dashboard remain proposals.',
    'Use these points as evidence prompts for your own writing, discussion and literature research.',
    'Reporting periods, data provenance and unresolved validation limits must accompany any use of the results.']

def read(path):
    return pd.read_csv(ROOT / path, dtype={'geo_code': str}, low_memory=False)

def paragraph(text):
    return ('text', text)

def evidence_table(title, frame):
    return ('table', title, frame)

def figure(filename, caption):
    return ('image', filename, caption)

def document(filename):
    """Convert existing technical Markdown to presentation blocks, retaining its content."""
    lines = (ROOT / filename).read_text(encoding='utf-8').splitlines()
    blocks, prose = [], []
    def flush():
        if prose:
            blocks.append(paragraph('\n'.join(prose)))
            prose.clear()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('|') and i + 1 < len(lines) and re.match(r'^\|[\s:|\-]+\|$', lines[i+1]):
            flush()
            header = [v.strip() for v in line.strip('|').split('|')]
            rows = []
            i += 2
            while i < len(lines) and lines[i].startswith('|'):
                rows.append([v.strip() for v in lines[i].strip('|').split('|')])
                i += 1
            blocks.append(evidence_table(filename, pd.DataFrame(rows, columns=header)))
            continue
        if line.startswith('#'):
            flush()
            blocks.append(('subheading', line.lstrip('#').strip()))
        elif not line.strip():
            flush()
        else:
            prose.append(line)
        i += 1
    flush()
    return blocks

def build_sections():
    data = read('data/processed/ortsteil_analysis_ready.csv')
    included = data[data.scoring_eligible].copy()
    composite = read('results/composite_index_results.csv')
    topsis = read('results/topsis_results.csv')
    clusters = read('results/kmeans_results.csv')
    assert set(included.geo_code) == set(composite.geo_code) == set(topsis.geo_code) == set(clusters.geo_code)
    assert included.year.eq(2024).all() and included.geo_code.is_unique
    checks = read('analysis/output_verification.csv')
    assert checks.passed.all(), 'Existing output verification contains a failed check'
    selection = read('analysis/indicator_selection.csv')
    selection['available_years'] = selection.available_years.str.replace(';','; ',regex=False)
    audit = read('analysis/source_audit.csv')
    inventory = read('data_inventory.csv')
    agreement = read('results/ranking_agreement_summary.csv').iloc[0]
    notes = {'unemployment':'Labour-market exclusion; quotient is not the official all-civilian unemployment rate.',
             'employment':'Labour-market participation; low values are an imperfect proxy because self-employment and civil servants are excluded.',
             'benefit_receipt':'Material-support receipt, distinct from unemployment; not all poverty or unmet need.',
             'child_benefits':'Optional overlapping child-benefit sensitivity indicator; not independent baseline evidence.',
             'income_median':'Income context only at 2020; no carry-forward into 2024.',
             'single_parents':'Service-needs context; family structure is not intrinsic disadvantage.'}
    selection['reason_for_role'] = selection.feature.map(notes)
    stats = read('results/descriptive_statistics.csv')
    stats = stats[['feature','count','mean','std','min','25%','50%','75%','max']].rename(columns={'50%':'median'})
    profiles = read('results/cluster_profiles.csv')
    scenarios = read('results/sensitivity_summary.csv')
    random = scenarios[scenarios.scenario.str.startswith('plausible_random')]
    random_summary = random.groupby('method').agg(scenarios=('scenario','count'),
        minimum_rank_correlation=('spearman_vs_baseline','min'), mean_rank_correlation=('spearman_vs_baseline','mean'),
        maximum_rank_movement=('max_absolute_rank_change','max'), minimum_top10_overlap=('top10_overlap','min')).reset_index()
    ranges = read('results/weight_rank_ranges.csv')
    rank_ranges = ranges.pivot(index=['geo_code','geo_name'], columns='method', values=['min','max','median'])
    rank_ranges.columns = ['_'.join(c) for c in rank_ranges.columns]
    rank_ranges = rank_ranges.reset_index()
    sections = [[] for _ in HEADINGS]
    sections[0] = [paragraph('Project title: ' + TITLE), paragraph('Main research question: ' + QUESTION),
        paragraph('Research subquestions:\n'+'\n'.join(f'{i+1}. {q}' for i,q in enumerate(QUESTIONS))),
        paragraph('Constructor University; MSCM-CO-08 Sustainable Cities & Transportation; Track 4: Smart Governance, Open Data & Digital Economy. Focus: Bremen Ortsteile.'),
        paragraph('Objectives: describe observed inequalities, review useful indicators, compare Composite Index/TOPSIS/K-means, assess sensitivity, and specify a transparent municipal decision-support blueprint.'),
        paragraph(f'Approach: reuse validated saved evidence. Primary comparison: 2024, {len(included)} of {len(data)} workbook Ortsteile. Scores capture partial labour-market/material-support disadvantage. All figures and results below are existing calculated outputs; the master notebook does not rerun analytical methods.')]
    sections[1] = [evidence_table('Verified source observations (missing counts apply to statistical observations, not catalogue metadata)', audit),
        paragraph('Sources: 22 historical municipal CSV files, 27 worksheets in the supplied Bremer Ortsteilatlas XLS export, and a separate JSON open-data metadata catalogue. CSV years span 2010-2016; workbook observations span 1969-2025, depending on indicator. These are reporting periods, not current 2026 observations.'),
        paragraph('Cleaning: CP1252 CSV encoding, semicolon delimiter and German decimal comma; legacy XLS read with xlrd; UTF-8 JSON. German names retain Unicode. Column/geographic fields are standardized; raw values and missing statuses are retained. No missing values are replaced with zero or imputed. Different statistical sources are not blindly joined.'),
        paragraph('Ortsteil is the primary level. Stadtteil and Stadtbezirk are aggregates and excluded from rankings. Überseestadt / Ueberseestadt is a documented name alias for code 437, not a validated historical boundary crosswalk.'),
        evidence_table('Original source inventory: all files and workbook sheets', inventory[['dataset_name','source_type','years','processed_records']]),
        *document('analysis/dataset_validation.md'),
        evidence_table('Excluded workbook Ortsteile, 2024', read('analysis/excluded_neighborhoods.csv')[['geo_code','geo_name','exclusion_reason']]),
        paragraph(f'Existing technical verification: {len(checks)} checks passed. Selected observations were also checked against 9,152 original BIFF cells. Source hashes are retained in analysis/source_manifest.csv.')]
    sections[2] = [evidence_table('Candidate names, measurement units, reporting years, roles and direction',
        selection[['feature','original_german_name','english_name','unit','available_years','role','disadvantage_direction']]),
        evidence_table('Definitions and reasons for inclusion or contextual use',selection[['feature','definition','reason_for_role']]),
        evidence_table('Indicator provenance and latest coverage', selection[['feature','source_file','source_sheet','latest_year','latest_covered','total_ortsteile','latest_missing_rate']]),
        evidence_table('Coverage in 2020 and 2024 (proportions are fractions)',read('analysis/coverage_summary.csv').query('year in [2020,2024]')),
        *document('analysis/indicator_audit.md')]
    sections[3] = [evidence_table('Descriptive statistics: 2024 complete cases; all indicators in percent; unweighted Ortsteile',stats),
        evidence_table('Available-case statistics: compare coverage with complete-case results',read('results/available_case_statistics.csv')[['feature','count','mean','std','min','50%','max']]),
        evidence_table('All 79 included Ortsteile: actual 2024 percentages',included[['geo_code','geo_name','unemployment','employment','benefit_receipt']].sort_values('geo_code')),
        *document('results/descriptive_findings.md'),
        figure('results/figures/indicator_distributions.png','Distribution of the three percentage indicators, 2024. Different denominator populations; descriptive only.'),
        figure('results/figures/benefit_receipt_comparison.png','Highest 15 benefit-receipt shares in the covered sample, 2024; excluded places are not ranked.'),
        figure('results/figures/correlation_matrix.png','2024 Spearman association. Correlated constructs may double-count related disadvantage; no causal interpretation.'),
        evidence_table('Spearman indicator correlations (unitless)',read('results/indicator_correlations.csv')),
        evidence_table('IQR outlier flags: retained observations, not automatic errors',read('results/indicator_outliers.csv')),
        paragraph('INCOMPLETE: historical change estimates and trend charts remain blocked because time-stable boundaries and definitions have not been verified. The following is a separate synchronized 2020 context, not a comparison of change and not part of the 2024 score.'),
        figure('results/figures/income_context_2020.png','2020 taxpayer-income context only. Taxpayer income is not disposable household income; no causal claim.')]
    sections[4] = [paragraph('Each indicator is scaled between its observed lowest and highest value. Employment is reversed, so low employment increases the score. The three directed values are averaged with equal weights (one-third each). A high score indicates relative disadvantage on these criteria within this sample.'),
        paragraph('Formula: z=(x-min)/(max-min); for employment use 1-z; composite=sum(weight*z). Rank descending; tied scores share the minimum rank. Min-max endpoints depend on coverage. Strength on one indicator can compensate for weakness on another. Equal indicator weights assign two-thirds combined weight to labour-market measures; domain-balanced scenarios test this choice.'),
        evidence_table('Complete composite results: 2024; score 0-1; rank 1 means greatest measured disadvantage',composite),
        figure('results/figures/composite_ranking.png','Highest 15 baseline composite scores, 2024. Partial relative disadvantage, not an official poverty classification.'),
        evidence_table('Directed normalized indicator values used in the composite (2024; 0-1)',read('results/composite_normalized_indicators.csv'))]
    sections[5] = [paragraph('TOPSIS constructs a hypothetical disadvantage ideal: highest unemployment and benefit receipt, lowest employment. It compares each neighborhood with this profile and the opposite profile. The score is higher when nearer the disadvantage ideal.'),
        paragraph('Calculation: divide each percentage by its column vector norm; apply equal weights; find criterion-specific ideal/anti-ideal extrema; compute Euclidean distances D+ and D-; closeness = D-/(D+ + D-). For this objective employment is a cost criterion, unemployment and benefits are benefit criteria; those words describe optimization direction, not social desirability.'),
        paragraph('Limitations: reference profiles are hypothetical; vector normalization, sample coverage and squared-distance weight contributions affect ranks. A high coefficient is not a quality-of-life score or a policy eligibility threshold.'),
        evidence_table('Complete TOPSIS results, 2024: closeness 0-1 and distances in weighted normalized space',topsis),
        evidence_table('Baseline weights and TOPSIS ideals',read('results/topsis_ideals.csv')),
        figure('results/figures/ranking_agreement.png','TOPSIS versus composite ranks, 2024. The same covered neighborhoods are used; rank 1 means greatest measured disadvantage.')]
    sections[6] = [paragraph('Standardization puts each raw percentage on a zero-mean, unit-standard-deviation scale. K-means then groups nearby profiles. k=2..8 was examined; highest silhouette among solutions with at least three members per cluster selected the baseline. Initialization: k-means++, 30 starts, seed 42.'),
        evidence_table('Cluster-count diagnostics (unitless silhouette and quality statistics)',read('results/kmeans_diagnostics.csv')),
        evidence_table('Nominal profile means: 2024, percent; n is neighborhood count',profiles[['cluster','n','unemployment_mean','employment_mean','benefit_receipt_mean']]),
        paragraph('Profile interpretation comes from the observed means: the profile with higher unemployment/benefit receipt and lower employment is relatively disadvantaged on these criteria. Profile A/B labels are arbitrary and must not be sorted as levels. K-means assumes compact profiles and depends on scaling, k and outliers.'),
        evidence_table('Every covered Ortsteil and its nominal profile, 2024',clusters.sort_values(['cluster','geo_code'])),
        figure('results/figures/cluster_profiles.png','Unweighted observed percentages for nominal profile groups, 2024.'),
        figure('results/figures/cluster_projection.png','PCA visualization only, 2024; K-means uses all three standardized indicators.'),
        figure('results/figures/kmeans_diagnostics.png','Silhouette by tested k, 2024. Diagnostic selection is not proof of a natural municipal taxonomy.')]
    sections[7] = [evidence_table('Method strengths, limitations and municipal uses',read('results/method_comparison_table.csv')),
        evidence_table('Rank agreement across the same 79 Ortsteile, 2024',read('results/ranking_agreement_summary.csv')),
        paragraph(f'Composite and TOPSIS rank agreement: Spearman {agreement.spearman:.4f}, Kendall tau-b {agreement.kendall_tau_b:.4f}. Both place {composite.iloc[0].geo_name} first on the selected indicators. Agreement is internal consistency, not validation against true poverty or independent outcomes.'),
        evidence_table('Largest rank disagreements, with absolute movement',read('results/ranking_agreement.csv').head(15)),
        paragraph('The composite uses directed min-max averaging; TOPSIS uses vector normalization and distance-based closeness. Their effective contributions differ, so different profiles can change rank. K-means adds similarity groups, not a third ranking. Transparency depends on showing definitions, weights, coverage and traces. No method is declared objectively best.'),
        *document('results/method_comparison.md')]
    sections[8] = [*document('results/robustness_findings.md'),
        evidence_table('Declared weight and indicator-selection scenarios (fixed 79 neighborhoods)',scenarios[~scenarios.scenario.str.startswith('plausible_random')]),
        evidence_table('Summary of 200 constrained random weight scenarios per ranking method',random_summary),
        evidence_table('Per-neighborhood weight rank ranges: scenario ranges, not confidence intervals',rank_ranges),
        evidence_table('K-means initialization and bootstrap stability: adjusted Rand index',read('results/cluster_stability_summary.csv')),
        figure('results/figures/weight_sensitivity.png','Baseline top-15 composite ranks across declared weight choices, 2024; ranges are not uncertainty intervals.'),
        paragraph('Reliability interpretation: agreement across many choices supports some within-sample consistency, but individual ranks and bootstrap cluster memberships can move. Missing areas, absent current income, overlapping constructs, small denominators and unknown measurement error remain unresolved. Full scenario rows remain in results/sensitivity_results.csv; no random-weight probability is interpreted as true deprivation.')]
    sections[9] = [figure('architecture/architecture_diagram.png','Four required layers; current local implementation and proposed deployment are explicitly labeled.'),
        *document('architecture/four_layer_architecture.md'),
        paragraph('Actual data flow: original files -> retained preparation output -> raw reconstruction/source hashes -> Ortsteil/unit/year/range/coverage gates -> 2024 complete-case matrix -> composite/TOPSIS/K-means -> robustness checks -> static evidence packages. The JSON catalogue remains separate. Historical changes branch to a blocked validation gate. Proposed publication and a planner dashboard require further human review.'),
        *document('architecture/system_components.md'), *document('architecture/feasibility_and_risks.md')]
    members = pd.DataFrame([
        ['Section 1: Urban Context',f'2024 partial-disadvantage differences across {len(included)} covered Ortsteile; {composite.iloc[0].geo_name} and {composite.iloc[1].geo_name} highest in both baseline rankings.', 'Descriptive statistics; benefit/distribution charts; exact units and coverage.', 'Add verified urban context and resident/service evidence; do not infer individual poverty or causal mechanisms.'],
        ['Section 2: Data & Indicators','Three primary percentage indicators; six audited candidates; nine excluded neighborhoods; no imputation.', 'Source audit, indicator dictionary, coverage and raw-cell verification; correlations and actual rates.', 'Verify municipal definitions/reference dates and broader indicators before claiming general deprivation.'],
        ['Section 3: Architecture','Implemented local Python batch pipeline; proposed four-layer municipal decision support.', 'Architecture diagram, acquisition/network/storage requirements, quality gates and method interfaces.', 'Hosting/API/dashboard/IoT are proposals; define maintenance, security, privacy and human oversight.'],
        ['Section 4: Methods & Benchmarking',f'Rank Spearman {agreement.spearman:.4f}; nominal clusters and weight/feature sensitivity.', 'Method comparison, rank differences, cluster profiles, scenario stability and literature questions.', 'Find real academic benchmarks; assess economic/ecological/social outcomes with new evidence; no impact is measured.']],
        columns=['Member section','Verified evidence','Useful inputs','Work and cautions'])
    sections[10] = [evidence_table('Shared technical notes for four group members',members),
        paragraph('These are supporting evidence notes, not submission-ready paragraphs. Existing individual PDF evidence packages remain in group_results/section_1 through section_4.'),
        *document('results/benchmarking_support.md')]
    versions = json.loads((ROOT/'docs/environment_versions.json').read_text(encoding='utf-8'))
    sections[11] = [paragraph('Primary annual comparison: 2024. Separate income context: 2020. Historical data exists but longitudinal change validation is incomplete. Exact observation days, revisions, denominator counts, historical boundaries and definition stability need verification. Scores describe relative partial disadvantage among covered places, not all socioeconomic needs or operational allocation suitability.'),
        *document('docs/source_notes.md'),
        evidence_table('Exact tested direct dependencies (existing environment)',pd.DataFrame(versions.items(),columns=['Package','Version'])),
        paragraph('Master document reproduction: run python src/create_master_notebook.py from the project root. This only loads existing validated results, executes the master notebook from a fresh kernel, and regenerates its PDF/HTML. No original analyses or existing notebooks/results are replaced. For an intentional full analysis reproduction, follow the existing instructions below separately.'),
        *document('docs/REPRODUCING.md'),
        paragraph('Detailed numerical traces remain in results/composite_normalized_indicators.csv, results/topsis_weighted_matrix.csv, results/topsis_ideals.csv and results/sensitivity_results.csv. Historical review tables remain in data/processed/ortsteil_historical_observations.csv and ortsteil_2020_income_context.csv. This master document presents all substantive results and explains where the full diagnostic row archives reside.')]
    return sections

def display_section(blocks):
    from IPython.display import display, Markdown, Image
    for block in blocks:
        if block[0] in ['text','subheading']:
            display(Markdown(('### ' if block[0]=='subheading' else '')+block[1]))
        elif block[0]=='table':
            display(Markdown('**'+block[1]+'**'))
            display(block[2].style.hide(axis='index').format(precision=3,na_rep='Unavailable')
                .set_table_attributes('style="width:100%;table-layout:fixed"')
                .set_properties(**{'text-align':'left','white-space':'normal','overflow-wrap':'anywhere','font-size':'13px'})
                .set_table_styles([{'selector':'th','props':[('white-space','normal'),('overflow-wrap','anywhere'),('text-align','left')]}]))
        else:
            display(Image(filename=str(ROOT/block[1])))
            display(Markdown('*'+block[2]+'*'))

def plain(text):
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)',r'\1 (\2)',text)
    return text.replace('**','').replace('`','')

def formatted(frame):
    return frame.map(lambda v: 'Unavailable' if pd.isna(v) else f'{v:.3f}' if isinstance(v,float) else str(v))

def export_html(sections):
    body = ['<h1>Bremen Smart Governance: Complete Technical Analysis</h1>', '<nav><h2>Contents</h2><ol>']
    body += [f'<li><a href="#section-{i+1}">{html.escape(title)}</a></li>' for i,title in enumerate(HEADINGS)]
    body.append('</ol></nav>')
    for i,(title,blocks) in enumerate(zip(HEADINGS,sections)):
        body += [f'<section id="section-{i+1}"><h2>{i+1}. {html.escape(title)}</h2>',f'<p>{html.escape(PURPOSES[i])}</p>']
        for block in blocks:
            if block[0]=='text':
                body.append('<p>'+html.escape(plain(block[1])).replace('\n','<br>')+'</p>')
            elif block[0]=='subheading':
                body.append('<h3>'+html.escape(block[1])+'</h3>')
            elif block[0]=='table':
                body.append('<h3>'+html.escape(block[1])+'</h3><div class="table">'+formatted(block[2]).to_html(index=False,escape=True)+'</div>')
            else:
                encoded = base64.b64encode((ROOT/block[1]).read_bytes()).decode('ascii')
                body.append(f'<figure><img src="data:image/png;base64,{encoded}" alt="{html.escape(block[2],quote=True)}"><figcaption>{html.escape(block[2])}</figcaption></figure>')
        body.append('</section>')
    css = 'body{font:16px/1.6 Arial,sans-serif;color:#202c32;max-width:1150px;margin:35px auto;padding:0 24px}h1{font-size:30px}h2{font-size:24px;border-bottom:2px solid #147d92;padding-bottom:8px;margin-top:48px}h3{font-size:18px}p{overflow-wrap:anywhere}a{color:#11677a}table{border-collapse:collapse;width:100%;font-size:13px}td,th{border:1px solid #cad2d7;padding:8px;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:#e9f1f2}tr:nth-child(even){background:#f6f8f9}.table{overflow-x:auto}figure{margin:30px 0}img{max-width:100%;height:auto}figcaption{font-size:14px;color:#46525a}@media print{body{max-width:none}h2{break-before:page}tr,figure{break-inside:avoid}.table{overflow:visible}}'
    (ROOT/(NAME+'.html')).write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+NAME+'</title><style>'+css+'</style></head><body>'+''.join(body)+'</body></html>',encoding='utf-8')

def export_pdf(sections):
    page_count = 0
    with PdfPages(ROOT/(NAME+'.pdf')) as pdf:
        def finish(fig):
            nonlocal page_count
            page_count += 1
            fig.text(.06,.025,f'Bremen Smart Governance | Technical evidence | Page {page_count}',fontsize=8,color='#46525a')
            pdf.savefig(fig)
            plt.close(fig)
        def text_pages(title,text):
            lines = []
            for paragraph_text in plain(text).split('\n'):
                lines += textwrap.wrap(paragraph_text, width=125,break_long_words=True,break_on_hyphens=False) or ['']
            for start in range(0,len(lines),28):
                fig = plt.figure(figsize=(11.69,8.27))
                fig.text(.06,.94,textwrap.fill(title,105),fontsize=15,weight='bold',va='top')
                fig.text(.06,.83,'\n'.join(lines[start:start+28]),fontsize=10,va='top',linespacing=1.6)
                finish(fig)
        text_pages('Bremen Smart Governance: Complete Technical Analysis',TITLE+'\n\nContents\n'+'\n'.join(f'{i+1}. {h}' for i,h in enumerate(HEADINGS))+'\n\nShared technical evidence, not final university report sections. Primary reporting year 2024; historical changes remain blocked. All figures and tables are reused from saved validated outputs.')
        for i,(title,blocks) in enumerate(zip(HEADINGS,sections)):
            section_title = f'{i+1}. {title}'
            prose = [PURPOSES[i]]
            def flush():
                if prose:
                    text_pages(section_title,'\n\n'.join(prose))
                    prose.clear()
            for block in blocks:
                if block[0] in ['text','subheading']:
                    prose.append(block[1])
                elif block[0]=='image':
                    flush()
                    fig,ax = plt.subplots(figsize=(11.69,8.27))
                    ax.imshow(plt.imread(ROOT/block[1]))
                    ax.axis('off')
                    fig.subplots_adjust(left=.03,right=.97,top=.92,bottom=.12)
                    fig.text(.04,.96,section_title,fontsize=13,weight='bold',va='top')
                    fig.text(.04,.09,textwrap.fill(block[2],145),fontsize=9,va='top')
                    finish(fig)
                else:
                    flush()
                    df = formatted(block[2])
                    if df.empty:
                        text_pages(section_title,block[1]+'\nNo rows were flagged in the saved result.')
                        continue
                    lengths = [max(len(str(c)),df[c].str.len().quantile(.7)) for c in df.columns]
                    widths = [max(7,min(45,v)) for v in lengths]
                    widths = [w/sum(widths) for w in widths]
                    chars = [max(6,int(w*145)) for w in widths]
                    header = [textwrap.fill(str(c).replace('_',' '),width=n) for c,n in zip(df.columns,chars)]
                    rows = [[textwrap.fill(plain(v),width=n,break_on_hyphens=False) for v,n in zip(row,chars)] for row in df.itertuples(index=False,name=None)]
                    cursor = 0
                    while cursor < len(rows):
                        chunk,heights = [], []
                        header_height = .026*(1+max(h.count('\n') for h in header))+.025
                        used = header_height
                        while cursor < len(rows):
                            row_height = .026*(1+max(v.count('\n') for v in rows[cursor]))+.018
                            if chunk and used+row_height > .76:
                                break
                            chunk.append(rows[cursor]); heights.append(row_height)
                            used += row_height; cursor += 1
                        fig,ax = plt.subplots(figsize=(11.69,8.27))
                        ax.axis('off')
                        fig.subplots_adjust(left=.035,right=.965,top=.83,bottom=.06)
                        fig.text(.04,.96,section_title,fontsize=13,weight='bold',va='top')
                        fig.text(.04,.91,textwrap.fill(block[1],125),fontsize=10,va='top')
                        t = ax.table(cellText=chunk,colLabels=header,colWidths=widths,loc='upper center',cellLoc='left')
                        t.auto_set_font_size(False); t.set_fontsize(7.5)
                        for (row,col),cell in t.get_celld().items():
                            cell.set_height(header_height if row==0 else heights[row-1])
                            cell.set_edgecolor('#cad2d7')
                            cell.set_facecolor('#e9f1f2' if row==0 else '#f6f8f9' if row%2==0 else 'white')
                        finish(fig)
            flush()
    return page_count

def preserved_files():
    paths = list(ROOT.glob('ST*.csv'))+[ROOT/'Datentabelle.xls',ROOT/'bremen_data.json']
    paths += [p for folder in ['data','analysis','results','architecture','group_results','notebooks'] for p in (ROOT/folder).rglob('*') if p.is_file()]
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}

def run():
    before = preserved_files()
    sections = build_sections()
    notebook = nbformat.v4.new_notebook()
    notebook.metadata.kernelspec = {'display_name':'Python 3','language':'python','name':'python3'}
    toc = '# Bremen Smart Governance: Complete Technical Analysis\n\nShared technical evidence for all four group members. Saved outputs can be read without running Python.\n\n## Table of Contents\n\n'+'\n'.join(f'{i+1}. [{h}](#section-{i+1})' for i,h in enumerate(HEADINGS))
    setup = "from pathlib import Path\nimport sys\nROOT = Path.cwd()\nif not (ROOT / 'src').is_dir():\n    ROOT = ROOT.parent\nassert (ROOT / 'src' / 'create_master_notebook.py').is_file(), 'Run from project root'\nsys.path.insert(0, str(ROOT / 'src'))\nfrom create_master_notebook import build_sections, display_section\nsections = build_sections()"
    notebook.cells = [nbformat.v4.new_markdown_cell(toc),nbformat.v4.new_code_cell(setup,metadata={'jupyter':{'source_hidden':True}})]
    for i,h in enumerate(HEADINGS):
        notebook.cells += [nbformat.v4.new_markdown_cell(f'<a id="section-{i+1}"></a>\n\n## {i+1}. {h}\n\n'+PURPOSES[i]),
                          nbformat.v4.new_code_cell(f'display_section(sections[{i}])',metadata={'jupyter':{'source_hidden':True}})]
    path = ROOT/(NAME+'.ipynb')
    print('Executing master notebook from a fresh kernel (loading saved evidence only).',flush=True)
    NotebookClient(notebook,timeout=300,kernel_name='python3',resources={'metadata':{'path':str(ROOT)}}).execute()
    nbformat.write(notebook,path)
    assert all(c.execution_count is not None and not any(o.output_type=='error' for o in c.outputs) for c in notebook.cells if c.cell_type=='code')
    export_html(sections)
    pages = export_pdf(sections)
    assert before == preserved_files(), 'An existing source or analysis artifact changed'
    status = {'notebook':path.name,'fresh_kernel_execution':'passed','code_cells':13,
              'sections':12,'pdf_pages':pages,'html_self_contained':True,
              'image_occurrences':sum(b[0]=='image' for s in sections for b in s),
              'table_occurrences':sum(b[0]=='table' for s in sections for b in s),
              'protected_existing_files':len(before),'existing_files_unchanged':True,
              'analysis_rerun':False,'outputs':[NAME+ext for ext in ['.ipynb','.pdf','.html']]}
    (ROOT/'docs/master_export_validation.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
    print(json.dumps(status,indent=2),flush=True)

if __name__=='__main__':
    run()
