import importlib.metadata
import json
import shutil
import textwrap
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from analysis_common import ROOT, YEAR, FEATURES, LABELS, SOURCE, load_analysis, save_csv, write_doc
from descriptive_analysis import export_figure

TITLE = "Data-Driven Smart Governance: A Comparative Evaluation of Methods for Identifying Socioeconomic Inequalities Across Bremen's Neighborhoods."
QUESTION = "How can different data-driven analytical methods identify socioeconomic disparities across Bremen's neighborhoods and support more transparent and equitable smart governance?"

def read(relative):
    return pd.read_csv(ROOT / relative, dtype={'geo_code':str})

def table(frame, columns=None, digits=3):
    frame = frame[columns].copy() if columns else frame.copy()
    def fmt(v):
        if pd.isna(v):
            return ''
        return f'{v:.{digits}f}' if isinstance(v, (float, np.floating)) else str(v).replace('|','/')
    lines = ['| ' + ' | '.join(frame.columns) + ' |', '| ' + ' | '.join(['---'] * len(frame.columns)) + ' |']
    lines += ['| ' + ' | '.join(fmt(v) for v in row) + ' |' for row in frame.itertuples(index=False, name=None)]
    return '\n'.join(lines)

def architecture_figure():
    fig, ax = plt.subplots(figsize=(12, 9))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 10)
    ax.axis('off')
    ax.text(6,9.7,'Bremen Smart Governance: Four-Layer Blueprint',ha='center',fontsize=17,weight='bold')
    ax.text(6,9.25,'Local implementation and proposed deployment are explicitly distinguished',ha='center',fontsize=10)
    layers = [
        ('1. Sensing / Data Acquisition', 'CURRENT: municipal XLS + historical CSV; JSON catalogue\nPROPOSED: versioned municipal release retrieval; no live sensors', '#dfefea'),
        ('2. Transmission / Network', 'CURRENT: local filesystem transfer\nPROPOSED: HTTPS / supported secure API; IoT networks only as future extensions', '#e5edf5'),
        ('3. Processing / Cloud or Edge', 'CURRENT: Python validation, CSV storage, notebooks; index / TOPSIS / K-means\nPROPOSED: scheduled jobs, PostgreSQL, immutable object store / municipal hosting', '#f3e6e8'),
        ('4. Application / AI and Decision Support', 'CURRENT: static tables, charts, PDFs and evidence packages\nPROPOSED: planner dashboard; weights, nominal profiles, provenance, exclusions', '#eeeaf4')]
    for i, (label, body, color) in enumerate(layers):
        y = 7.4 - i*2.05
        ax.add_patch(FancyBboxPatch((.4,y),11.2,1.65,boxstyle='round,pad=0.02,rounding_size=0.08',facecolor=color,edgecolor='#65716d'))
        ax.text(.7,y+1.25,label,fontsize=13,weight='bold')
        ax.text(.7,y+.65,body,fontsize=10,va='center',linespacing=1.7)
        if i < 3:
            ax.annotate('',xy=(6,y-.35),xytext=(6,y-.03),arrowprops={'arrowstyle':'->','lw':2,'color':'#46545a'})
    ax.text(.5,.4,'Validation gates: primary annual coverage passed; historical change gate blocked.\nProposed decision support requires human review; no operational dashboard deployed.',fontsize=10)
    folder = ROOT / 'architecture'
    folder.mkdir(exist_ok=True)
    fig.savefig(folder/'architecture_diagram.png',bbox_inches='tight',dpi=170)
    plt.close(fig)

def result_figures(frame, composite, topsis, clusters):
    fig, ax = plt.subplots(figsize=(8,6))
    top = composite.head(15).sort_values('composite_score')
    ax.barh(top.geo_name, top.composite_score,color='#9c405c')
    ax.set(xlabel='Equal-weight composite score (0-1; higher = more disadvantage)',
           title=f'Highest composite scores among covered Ortsteile, {YEAR}')
    export_figure(fig,'composite_ranking')
    agreement = read('results/ranking_agreement.csv')
    fig, ax = plt.subplots(figsize=(7,6))
    ax.scatter(agreement.composite_rank,agreement.topsis_rank,color='#147d92',s=25)
    ax.plot([1,len(frame)],[1,len(frame)],color='gray',linestyle='--',linewidth=1)
    for _, r in agreement.head(5).iterrows():
        ax.annotate(r.geo_name,(r.composite_rank,r.topsis_rank),fontsize=8,xytext=(4,4),textcoords='offset points')
    ax.set(xlabel='Composite rank (1 = greatest measured disadvantage)',ylabel='TOPSIS rank (same direction)',
           title=f'Ranking agreement and largest differences, {YEAR}')
    export_figure(fig,'ranking_agreement')
    profiles = clusters.groupby('cluster')[FEATURES].mean()
    fig, axes = plt.subplots(1,3,figsize=(12,5))
    for ax, f in zip(axes,FEATURES):
        ax.bar(profiles.index,profiles[f],color=['#147d92','#9c405c','#4a8c58'][:len(profiles)])
        ax.set(ylabel=LABELS[f],title=LABELS[f].replace(' (%)',''))
    fig.suptitle(f'Nominal cluster profiles: observed mean percentages, {YEAR}')
    export_figure(fig,'cluster_profiles','Labels are arbitrary; clusters are profiles, not ranks. Means are unweighted.')
    pca = PCA(n_components=2)
    xy = pca.fit_transform(StandardScaler().fit_transform(frame[FEATURES]))
    projected = frame[['geo_code','geo_name','year']].copy()
    projected['PC1'], projected['PC2'] = xy[:,0],xy[:,1]
    projected = projected.merge(clusters[['geo_code','cluster']],on='geo_code',validate='one_to_one')
    save_csv(projected,'results/cluster_projection.csv')
    save_csv(pd.DataFrame({'component':['PC1','PC2'],'explained_variance_ratio':pca.explained_variance_ratio_}), 'results/pca_projection_variance.csv')
    fig, ax = plt.subplots(figsize=(7,6))
    for name, group in projected.groupby('cluster'):
        ax.scatter(group.PC1,group.PC2,label=name,s=30)
    ax.set(xlabel=f'PC1 (unitless; {pca.explained_variance_ratio_[0]:.1%} variance)',
           ylabel=f'PC2 (unitless; {pca.explained_variance_ratio_[1]:.1%} variance)',title=f'K-means profiles in a 2D projection, {YEAR}')
    ax.legend()
    export_figure(fig,'cluster_projection','PCA is visualization only; clustering uses all three standardized indicators.')
    diag = read('results/kmeans_diagnostics.csv')
    fig, ax = plt.subplots(figsize=(7,5))
    ax.plot(diag.k,diag.silhouette,marker='o',color='#147d92')
    ax.set(xlabel='Number of clusters k',ylabel='Mean silhouette (unitless)', title=f'Cluster-count diagnostic, {YEAR}')
    ax.set_xticks(diag.k)
    export_figure(fig,'kmeans_diagnostics','Highest silhouette selected among solutions with minimum cluster size at least three.')
    sensitivity = read('results/weight_rank_ranges.csv')
    ranges = sensitivity[sensitivity.method=='composite'].set_index('geo_code').loc[composite.head(15).geo_code].reset_index()
    fig, ax = plt.subplots(figsize=(8,6))
    y = np.arange(len(ranges))
    ax.hlines(y,ranges['min'],ranges['max'],color='#147d92',linewidth=3)
    ax.scatter(ranges['median'],y,color='#9c405c',s=25)
    ax.set_yticks(y,ranges.geo_name)
    ax.invert_yaxis()
    ax.set(xlabel='Composite rank across 200 weight scenarios',title=f'Weight sensitivity: baseline highest 15, {YEAR}')
    export_figure(fig,'weight_sensitivity','Scenario ranges, not confidence intervals. Fixed 79-neighborhood sample.')
    income = read('data/processed/ortsteil_2020_income_context.csv')
    eligible = income[income.complete_four_indicators]
    fig, ax = plt.subplots(figsize=(7,6))
    ax.scatter(eligible.income_median,eligible.benefit_receipt,color='#4a8c58',s=28)
    ax.set(xlabel='Median total income per taxpayer (1000 EUR)',ylabel=LABELS['benefit_receipt'],
           title=f'Separate income context, 2020 ({len(eligible)} complete Ortsteile)')
    export_figure(fig,'income_context_2020','2020 context only; not joined to 2024 scores. Taxpayer income is not household disposable income.')

def pdf_summary(path, heading, facts, tables, figures):
    with PdfPages(path) as pdf:
        fig = plt.figure(figsize=(8.27,11.69))
        fig.text(.08,.94,heading,fontsize=16,weight='bold',va='top')
        y = .88
        for fact in facts:
            wrapped = textwrap.fill(fact,90)
            fig.text(.08,y,wrapped,fontsize=10,va='top',linespacing=1.5)
            y -= .023 * (wrapped.count('\n') + 1) + .025
        fig.text(.08,.055,'Technical evidence for group review; not a final university report section.\nSource: supplied municipal workbook. Primary reporting year: 2024.',fontsize=9)
        pdf.savefig(fig)
        plt.close(fig)
        for name, df in tables:
            fig, ax = plt.subplots(figsize=(8.27,11.69))
            ax.axis('off')
            ax.set_title(name,fontsize=14,pad=20)
            text = [[f'{v:.3f}' if isinstance(v,(float,np.floating)) else str(v) for v in row] for row in df.itertuples(index=False,name=None)]
            t = ax.table(cellText=text,colLabels=df.columns,loc='upper center',cellLoc='left')
            t.auto_set_font_size(False)
            t.set_fontsize(8)
            t.scale(1,1.8)
            fig.text(.08,.04,'Reporting years and units are identified in table headings; ranks refer only to covered Ortsteile.',fontsize=8)
            pdf.savefig(fig,bbox_inches='tight')
            plt.close(fig)
        for filename in figures:
            fig, ax = plt.subplots(figsize=(11.69,8.27))
            ax.imshow(plt.imread(ROOT / filename))
            ax.axis('off')
            pdf.savefig(fig,bbox_inches='tight')
            plt.close(fig)

def run():
    frame = load_analysis()
    composite,topsis,clusters = read('results/composite_index_results.csv'),read('results/topsis_results.csv'),read('results/kmeans_results.csv')
    agreement = read('results/ranking_agreement_summary.csv').iloc[0]
    rankdiff = read('results/ranking_agreement.csv').head(8).merge(frame[['geo_code']+FEATURES],on='geo_code',validate='one_to_one')
    profiles = clusters.groupby('cluster')[FEATURES].mean()
    k = len(profiles)
    diag = read('results/kmeans_diagnostics.csv')
    silhouette = float(diag[diag.k==k].silhouette.iloc[0])
    method_table = pd.DataFrame([
        {'method':'Composite index','output':'score [0,1]; descending rank','normalization':'min-max, employment reversed',
         'weights':'equal 1/3 baseline','strength':'transparent arithmetic and per-feature contributions','limitation':'compensatory; endpoints and correlated variables matter',
         'governance_use':'auditable screening; inspect components before any decision'},
        {'method':'TOPSIS','output':'disadvantage closeness [0,1]; descending rank','normalization':'column vector norm',
         'weights':'equal 1/3 baseline','strength':'explicit reference profiles and distance trade-offs','limitation':'scaling, weights and sample-dependent ideals affect distance',
         'governance_use':'alternative screening; show rank disagreements'},
        {'method':'K-means','output':f'{k} nominal profile groups','normalization':'StandardScaler z-scores',
         'weights':'no explicit weights; standardized Euclidean geometry','strength':'shows similar multidimensional neighborhood profiles','limitation':'k and scaling choices; no intrinsic ordering; compact-cluster assumption',
         'governance_use':'describe differentiated needs; not a deprivation league table'}])
    save_csv(method_table,'results/method_comparison_table.csv')
    lines = []
    for cluster, means in profiles.iterrows():
        lines.append(f'- {cluster}: n={int((clusters.cluster==cluster).sum())}; unemployment {means.unemployment:.2f}%, employment {means.employment:.2f}%, SGB II receipt {means.benefit_receipt:.2f}%.')
    high_u = profiles.unemployment.idxmax()
    interpretation = ('The same profile has the highest unemployment and benefit receipt and the lowest employment, supporting a relative disadvantage description on these three indicators.'
                      if profiles.benefit_receipt.idxmax()==high_u and profiles.employment.idxmin()==high_u
                      else 'Indicators do not jointly order all profiles; describe their differences without imposing levels.')
    write_doc('results/method_comparison.md',f'''# Method comparison evidence

Shared data: {len(frame)} Ortsteile, 2024, three indicators, no imputation. Highest equal-weight composite scores:

{table(composite.head(10),['geo_name','composite_score','rank'])}

Highest TOPSIS disadvantage closeness:

{table(topsis.head(10),['geo_name','topsis_score','rank'])}

Rank Spearman {agreement.spearman:.4f}; Kendall tau-b {agreement.kendall_tau_b:.4f}. Agreement is within-sample consistency, not evidence of correct identification of true poverty. Both scores are relative, with different normalizations and aggregation geometries.

Largest rank differences and observed percentages (unemployment, employment, benefits; all 2024):

{table(rankdiff,['geo_name','composite_rank','topsis_rank','unemployment','employment','benefit_receipt'])}

Min-max equal-weight scoring gives each observed indicator range equal contribution. TOPSIS vector normalization gives columns different effective spreads, and closeness uses Euclidean distances. The differing observed profiles explain why an employment weakness can change rank differently from a benefit-receipt weakness; no causal explanation of neighborhood conditions is inferred.

K-means selected k={k}; mean silhouette {silhouette:.4f}. Labels are nominal:

'''+'\n'.join(lines)+f'''

{interpretation} No Profile A/B ordering is inferred. Stability evidence is in robustness_findings.md; cluster count is an algorithmic diagnostic choice, not a proven municipal taxonomy.

Interpretability: the composite average is easiest to reconstruct; TOPSIS requires understanding normalization and hypothetical ideals; clusters require inspecting profiles rather than reading rank numbers. Transparency depends on publishing definitions, weights, coverage and traces for all three. Robustness tests show dependence on analyst choices. Data requirements are a complete consistent numeric matrix; K-means additionally requires enough varied observations and standardized scales. No winner is declared.

Figures and evidence: composite_ranking.png, ranking_agreement.png, cluster_profiles.png, cluster_projection.png, kmeans_diagnostics.png, weight_sensitivity.png. Rankings may guide questions for planners, not dictate budgets or individual eligibility. Wider income, education, housing and health indicators, denominator counts, source-definition verification and external validation are needed for a general disadvantage measure.
''')
    write_doc('results/benchmarking_support.md', '''# Benchmarking support and literature questions

Composite indices aggregate selected normalized indicators; TOPSIS compares distance to hypothetical ideal/anti-ideal profiles; K-means identifies similar standardized profiles. See docs/methods.md and method_comparison_table.csv for implemented assumptions and trade-offs. No international cases or academic findings are invented here.

Comparable published outputs could include indicator definitions and geographic scale, coverage, normalization and weights, score/rank correlations, cluster profiles, silhouette diagnostics and robustness protocols. Scores from different cities or samples are not directly comparable merely because they range from zero to one. Harmonized units, denominator populations, periods, boundary definitions and feature sets are required. K-means labels have no cross-study identity without profile matching.

Questions for the literature member: How do municipal deprivation studies validate indicators externally? How is correlated-indicator double counting handled? How are small denominators and suppressed values treated? What evidence supports equal versus stakeholder weights? How are changing boundaries harmonized? How are uncertainty, ecological inference and neighborhood stigma handled? What governance use has been evaluated rather than merely proposed? Locate real peer-reviewed references and municipal cases; distinguish cited results from this project's calculations.

Triple-bottom-line evaluation framework (proposed evaluation, not measured impacts):

| Dimension | Potential evaluation question | Evidence needed | Current limit |
| --- | --- | --- | --- |
| Economic | Does decision support reduce planning effort or improve allocation efficiency? | Staff time, implementation costs, allocation outcomes and a comparison baseline | None measured; no savings claim |
| Ecological | Does an intervention improve sustainable access or reduce emissions? | Travel/access data, intervention records, emissions measures and evaluation design | Current indicators do not establish ecological benefits |
| Social | Do service access and distributional outcomes improve equitably? | Need validation, resident consultation, service outcomes, coverage and fairness measures | Current scores describe partial relative disadvantage, not impact |

Correlations and rankings cannot establish any of these causal impacts. Teammates must add literature, contextual evidence and appropriately designed evaluation before drawing such conclusions.
''')
    architecture_figure()
    result_figures(frame,composite,topsis,clusters)
    captions = [
        ('indicator_distributions.png','Distribution of the three 2024 percentages across 79 complete-case Ortsteile; different denominators; not population-weighted.'),
        ('benefit_receipt_comparison.png','Top 15 observed 2024 under-65 SGB II shares in the analysis sample; does not represent every excluded place.'),
        ('correlation_matrix.png',f'2024 pairwise Spearman correlations; unemployment/benefits {frame.unemployment.corr(frame.benefit_receipt,method="spearman"):.3f}; overlapping constructs, not causation.'),
        ('composite_ranking.png',f'2024 equal-weight index; {composite.iloc[0].geo_name} has highest baseline score; sample-relative and partial disadvantage.'),
        ('ranking_agreement.png',f'2024 rank agreement Spearman {agreement.spearman:.4f}; marked largest differences; agreement does not externally validate either method.'),
        ('cluster_profiles.png',f'{k} nominal 2024 clusters; raw percent means support profile interpretation; labels are not ordered.'),
        ('cluster_projection.png','2024 standardized profiles projected by PCA for display only; three-dimensional inputs used for clustering.'),
        ('kmeans_diagnostics.png',f'2024 k=2..8 silhouette comparison; selected k={k} subject to minimum size three, not a proven natural taxonomy.'),
        ('weight_sensitivity.png','2024 top-15 baseline composite rank ranges under 200 declared weight choices; not confidence intervals.'),
        ('income_context_2020.png','Separate synchronized 2020 income/benefit context; nominal taxpayer income, not current household income or a trend.')]
    write_doc('results/figures/figure_notes.md','# Figure interpretations\n\n'+ '\n\n'.join(f'**{name}**: {caption}\nSource: supplied Datentabelle.xls. Reproduce with src/descriptive_analysis.py and src/package_results.py.' for name,caption in captions))
    package_groups(frame,composite,topsis,clusters,lines,silhouette,agreement)
    versions = {name:importlib.metadata.version(name) for name in ['pandas','xlrd','numpy','scipy','scikit-learn','matplotlib','nbformat','nbclient','ipykernel']}
    write_doc('docs/environment_versions.json',json.dumps(versions,indent=2))
    write_doc('docs/requirements-tested.txt','\n'.join(name+'=='+version for name,version in versions.items()))
    return method_table

def package_groups(frame, composite, topsis, clusters, profile_lines, silhouette, agreement):
    folders = ['section_1','section_2','section_3','section_4']
    for folder in folders:
        (ROOT/'group_results'/folder).mkdir(parents=True,exist_ok=True)
    shared = f'''# Group technical evidence overview

**Project title:** {TITLE}

**Main question:** {QUESTION}

Course MSCM-CO-08 Sustainable Cities & Transportation, Constructor University. Track 4: Smart Governance, Open Data & Digital Economy. Geographic focus: Bremen Ortsteile.

Confirmed subquestions: (1) What socioeconomic and demographic differences exist across Bremen's neighborhoods? (2) Which indicators are most useful for identifying neighborhood disadvantage? (3) How do different analytical methods compare in identifying and ranking disadvantaged neighborhoods? (4) How can Bremen integrate these findings into a smart governance decision-support system?

Open the PDF in your section folder for an offline evidence summary, then the Markdown evidence notes and copied tables/figures. CSVs use UTF-8 BOM for spreadsheet readability; decimal separator is a point. Unicode names are preserved. No programming required to review these packages. Counts and scores are calculated, not hypothetical.

Primary evidence: 2024, {len(frame)} of 88 workbook Ortsteile, three labour-market/benefit indicators. This is partial relative disadvantage, not an official multidimensional poverty classification. Original source and definition/date caveats remain visible. Income context is 2020; historical changes are blocked pending validation. No observations are claimed to describe 2026.

Section 1: urban-context facts and planner discussion questions. Section 2: data definitions, coverage and reproduction evidence. Section 3: proposed four-layer architecture. Section 4: methods, actual results, robustness and literature questions. These are working evidence packages, not ready-to-submit report sections.

Work still required: verify source reference dates/definitions and historical boundaries, acquire broader indicators and denominator counts where possible, locate real academic references and external municipal benchmarks, discuss indicators with stakeholders, and write your own report/presentation with properly attributed findings.
'''
    write_doc('group_results/OVERVIEW.md',shared)
    mappings = {
        'section_1':['results/descriptive_statistics.csv','results/descriptive_findings.md','analysis/data_dictionary.csv','docs/source_notes.md','results/figures/benefit_receipt_comparison.png','results/figures/indicator_distributions.png'],
        'section_2':['analysis/indicator_selection.csv','analysis/data_dictionary.csv','analysis/coverage_summary.csv','analysis/dataset_validation.md','analysis/excluded_neighborhoods.csv','analysis/source_audit.csv','results/descriptive_statistics.csv','results/available_case_statistics.csv','results/indicator_correlations.csv','results/figures/correlation_matrix.png','docs/REPRODUCING.md'],
        'section_3':['architecture/architecture_diagram.png','architecture/four_layer_architecture.md','architecture/system_components.md','architecture/data_flow.md','architecture/feasibility_and_risks.md'],
        'section_4':['docs/methods.md','results/method_comparison.md','results/method_comparison_table.csv','results/composite_index_results.csv','results/topsis_results.csv','results/kmeans_results.csv','results/cluster_profiles.csv','results/robustness_findings.md','results/sensitivity_summary.csv','results/weight_rank_ranges.csv','results/benchmarking_support.md','results/figures/composite_ranking.png','results/figures/ranking_agreement.png','results/figures/cluster_profiles.png','results/figures/weight_sensitivity.png']}
    for folder,files in mappings.items():
        for file in files:
            shutil.copy2(ROOT/file,ROOT/'group_results'/folder/Path_name(file))
    facts = [f'2024 analysis: {len(frame)} complete-case Ortsteile from 88 workbook areas; no missing value imputation.',
             'Three indicators: unemployment quotient, social-insurance employment participation, and SGB II benefit receipt under age 65. Percentages have different denominators.',
             f'Highest composite scores: {", ".join(composite.head(5).geo_name)}. Highest TOPSIS closeness: {", ".join(topsis.head(5).geo_name)}.',
             f'Rank Spearman correlation: {agreement.spearman:.4f}. K-means selects {len(clusters.cluster.unique())} nominal profiles; silhouette {silhouette:.4f}.',
             'Scores are relative to the covered sample and describe partial disadvantage. They do not establish individual poverty, causal effects, current 2026 conditions or an allocation rule.',
             'Historical change claims remain blocked. Boundary/definition history and exact current reference dates need municipal verification. Income context is kept at 2020.']
    section_text = [
        'Discussion prompts: where might planners investigate labour-market and benefit-related service needs? What contextual and resident evidence is needed before allocating resources? Demographic identities are not scored. Urban mobility and environmental outcomes need additional data.',
        'Data review: inspect the exact German headings, denominators, coverage, missingness and source reconstruction audit. Reproduction instructions are included. The analytical file retains all 88 areas and flags the 79 eligible rows.',
        'Architecture review: current local files and Python pipeline are implemented. HTTPS acquisition, database/cloud hosting and a planner dashboard are proposed. Sensors and their networks are only future extensions.',
        'Method review: composite index averages directed min-max indicators; TOPSIS measures closeness to the disadvantage ideal; K-means describes similar profiles. Read robustness scenarios and literature questions; no method is declared objectively best.']
    rank_table = composite.head(10)[['geo_name','composite_score','rank']].rename(columns={'geo_name':'Ortsteil','composite_score':'Score','rank':'Rank'})
    for i,folder in enumerate(folders):
        write_doc(f'group_results/{folder}/EVIDENCE_GUIDE.md',f'# Section {i+1} evidence guide\n\n'+'\n\n'.join(facts+[section_text[i]])+'\n\nUse the accompanying files as evidence. Write your own section and add verified academic/contextual sources. The shared overview states the exact project questions.')
        figures = mappings[folder]
        figures = [file for file in figures if file.endswith('.png')]
        pdf_summary(ROOT/f'group_results/{folder}/evidence_summary.pdf',f'Section {i+1}: Technical Evidence',facts+[section_text[i]],
                    [('2024 composite results: highest 10 covered Ortsteile',rank_table)] if i in [0,3] else [],figures)

def Path_name(relative):
    return relative.rsplit('/',1)[-1]

if __name__ == '__main__':
    print(run().to_string(index=False))
