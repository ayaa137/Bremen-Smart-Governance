import hashlib
import json
import sys
import platform
import numpy as np
import pandas as pd
import nbformat
import matplotlib.image as mpimg
import xlrd
from analysis_common import ROOT, FEATURES, load_analysis, save_csv, write_doc
from composite_index import calculate as composite_score
from topsis import calculate as topsis_score
from package_results import TITLE, table

def run():
    checks = []
    def check(name, condition, detail=''):
        checks.append({'check':name,'passed':bool(condition),'detail':detail})
        if not condition:
            raise AssertionError(name + ': ' + detail)
    read = lambda p: pd.read_csv(ROOT/p,dtype={'geo_code':str})
    manifest = read('analysis/source_manifest.csv')
    check('all 24 originals unchanged since audit',len(manifest)==24 and all(hashlib.sha256((ROOT/r.file).read_bytes()).hexdigest()==r.sha256 for r in manifest.itertuples()))
    frame = load_analysis().reset_index(drop=True)
    # Check selected measurements directly against BIFF cells, independently of the preparation parser.
    selected = read('data/processed/selected_indicators_long.csv')
    selection = read('analysis/indicator_selection.csv')
    workbook = xlrd.open_workbook(ROOT/'Datentabelle.xls')
    direct_cells = 0
    for definition in selection.itertuples():
        sheet = workbook.sheet_by_name(definition.source_sheet)
        heading = ''
        original = {}
        for col in range(2,sheet.ncols):
            cell_heading = sheet.cell_value(1,col)
            if cell_heading:
                heading = ' '.join(str(cell_heading).split())
            if heading != definition.original_german_name:
                continue
            year = int(float(sheet.cell_value(2,col)))
            for row in range(3,sheet.nrows):
                code = sheet.cell_value(row,0)
                code = str(int(code)) if isinstance(code,(float,int)) and code else str(code).strip()
                if len(code)==3 and code.isdigit():
                    value = sheet.cell_value(row,col)
                    original[(code,year)] = float(value) if value != '' else np.nan
        observations = selected[selected.feature==definition.feature]
        check(definition.feature+' all source BIFF cells match',len(original)==len(observations) and all(
            (pd.isna(r.value) and pd.isna(original[(r.geo_code,r.year)])) or
            np.isclose(r.value,original[(r.geo_code,r.year)],rtol=0,atol=1e-12)
            for r in observations.itertuples()))
        direct_cells += len(original)
    check('independent selected-cell verification performed',direct_cells==len(selected),str(direct_cells)+' original BIFF cells')
    check('unique valid Ortsteil/year matrix',frame.geo_code.is_unique and frame.geo_code.str.fullmatch(r'\d{3}').all() and frame.geo_level.eq('Ortsteil').all() and frame.year.eq(2024).all())
    check('complete finite percent inputs',np.isfinite(frame[FEATURES]).all().all() and frame[FEATURES].ge(0).all().all() and frame[FEATURES].le(100).all().all())
    for filename, function, column in [('composite_index_results.csv',composite_score,'composite_score'),('topsis_results.csv',topsis_score,'topsis_score')]:
        result = read('results/'+filename)
        expected = pd.Series(function(frame),index=frame.geo_code)
        check(filename+' scores independently recompute',np.allclose(result[column],result.geo_code.map(expected),rtol=1e-12,atol=1e-12))
        check(filename+' descending disadvantage ranks',result[column].is_monotonic_decreasing and result['rank'].eq(result[column].rank(ascending=False,method='min')).all())
    # Synthetic monotonicity check catches benefit/cost direction reversal independently of source ranks.
    tiny = pd.DataFrame({'unemployment':[1.,2.,3.],'employment':[90.,60.,30.],'benefit_receipt':[1.,2.,3.]})
    check('both methods increase with all-criteria disadvantage',np.all(np.diff(composite_score(tiny))>0) and np.all(np.diff(topsis_score(tiny))>0))
    clusters = read('results/kmeans_results.csv')
    check('identical method coverage and no cluster ranks',set(clusters.geo_code)==set(frame.geo_code) and 'rank' not in clusters)
    profiles = read('results/cluster_profiles.csv').set_index('cluster')
    for feature in FEATURES:
        check(feature+' cluster means match inputs',np.allclose(clusters.groupby('cluster')[feature].mean().reindex(profiles.index),profiles[feature+'_mean']))
    desc = read('results/descriptive_statistics.csv').set_index('feature')
    check('descriptive means match matrix',np.allclose(desc.loc[FEATURES,'mean'],frame[FEATURES].mean()))
    sensitivity = read('results/sensitivity_results.csv')
    check('sensitivity scenarios preserve method population',sensitivity.groupby(['scenario','method']).geo_code.nunique().eq(len(frame)).all())
    check('three baseline features and correctly preserved years',set(selection[selection.role=='primary'].feature)==set(FEATURES) and frame[[f+'_year' for f in FEATURES]].eq(2024).all().all())
    execution = json.loads((ROOT/'analysis/notebook_execution.json').read_text(encoding='utf-8'))
    check('eight notebooks fresh-kernel execution passed',len(execution)==8 and all(x['passed'] for x in execution))
    for path in sorted((ROOT/'notebooks').glob('*.ipynb')):
        notebook = nbformat.read(path,as_version=4)
        code = [c for c in notebook.cells if c.cell_type=='code']
        check(path.name+' execution and no cell errors',all(c.execution_count is not None for c in code) and not any(o.output_type=='error' for c in code for o in c.outputs))
    for path in sorted((ROOT/'results/figures').glob('*.png')) + [ROOT/'architecture/architecture_diagram.png']:
        pixels = mpimg.imread(path)
        check(path.name+' readable nonblank figure',min(pixels.shape[:2])>300 and pixels[:,:,:3].std()>.03)
    for path in (ROOT/'group_results').glob('section_*/evidence_summary.pdf'):
        check(str(path.relative_to(ROOT))+' valid PDF artifact',path.read_bytes().startswith(b'%PDF') and path.stat().st_size>10000)
    save_csv(pd.DataFrame(checks),'analysis/output_verification.csv')
    write_doc('docs/python_environment.json',json.dumps({'python':sys.version,'platform':platform.platform()},indent=2))
    files = sorted(str(p.relative_to(ROOT)).replace('\\','/') for folder in ['src','notebooks','analysis','results','architecture','group_results','docs'] for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in str(p))
    files += ['data/processed/'+p.name for p in (ROOT/'data/processed').glob('ortsteil*.csv')]+['data/processed/selected_indicators_long.csv','requirements.txt']
    files = sorted(set(files + ['TECHNICAL_COMPLETION_REPORT.md','docs/deliverable_manifest.json']))
    write_doc('docs/deliverable_manifest.json',json.dumps({'deliverable_files':files,
        'modified_existing_files':['requirements.txt'],
        'preserved_original_sources':manifest.file.tolist(),
        'preserved_phase1_outputs':['data_inventory.csv','indicator_catalog.csv','data_quality_report.md',
            'src/prepare_data.py','data/processed/excel_ortsteilatlas_long.csv',
            'data/processed/csv_district_statistics_long.csv','data/processed/bremen_open_data_catalog.csv',
            'data/processed/geography_lookup.csv','data/processed/validation_summary.csv']},indent=2))
    composite = read('results/composite_index_results.csv')
    topsis = read('results/topsis_results.csv')
    agreement = read('results/ranking_agreement_summary.csv').iloc[0]
    source_audit = read('analysis/source_audit.csv')
    all_rows = load_analysis(False)
    blocked = 'Historical change estimates remain incomplete: time-stable boundaries and definitions are not verified. Historical tables and separate 2020 income context are review artifacts only. Exact within-year reference dates, revisions and denominator counts remain unavailable. Operational allocation suitability and full multidimensional disadvantage are not validated.'
    write_doc('TECHNICAL_COMPLETION_REPORT.md',f'''# Technical completion report

{TITLE}

Scope: reproducible technical evidence and proposed architecture. No final university report sections, slides, interactive application or GitHub push. Course MSCM-CO-08; Track 4; Bremen Ortsteile. Exact confirmed questions appear in group_results/OVERVIEW.md.

## Completed and verified

All 24 original files reread. Statistical rows reconstructed and compared against existing Phase 1 outputs. In addition, {direct_cells} selected indicator observations were checked directly against original BIFF cells independently of the preparation parser:

{table(source_audit,['source','records','missing','passed'])}

Six candidates audited; three primary indicators selected: unemployment quotient (higher disadvantage), social-insurance employment share aged 15-under-65 (lower), and SGB II receipt under 65 (higher). Child SGB II receipt is a sensitivity extension; median taxpayer income is separate 2020 context; single parenthood is context only. Exact German names, units, denominators, years and coverage are in analysis/indicator_selection.csv.

Primary annual reporting year: 2024; {len(frame)} of {len(all_rows)} workbook Ortsteile ({len(frame)/len(all_rows):.1%}) included. Nine areas excluded for unavailable labour-market indicators. No imputation, aggregate leakage or mixed-year scores. Income is not carried forward from 2020.

Implemented: directed min-max equal-weight composite, vector-normalized equal-weight TOPSIS, standardized K-means with diagnostics and initialization/bootstrap stability; ranking comparison, declared weight/feature robustness and readable visualizations. Architecture documents mark implemented local pipeline versus proposed municipal deployment. Four section packages include evidence guides, tables, figures and readable PDFs. Eight notebooks execute from fresh kernels. Scripts run through the pipeline; persisted calculations, source hashes, score directions, inputs/coverage, figures and notebook execution are checked in analysis/output_verification.csv ({len(checks)} passed checks).

## Verified findings

Highest composite score areas: {', '.join(composite.head(5).geo_name)}. Highest TOPSIS disadvantage closeness: {', '.join(topsis.head(5).geo_name)}. Rank Spearman {agreement.spearman:.4f}, Kendall tau-b {agreement.kendall_tau_b:.4f}; these are within-sample agreement metrics, not truth validation. K-means returns {clusters.cluster.nunique()} nominal profiles; profile statistics and stability are exported. Actual descriptive ranges, score values, rank differences and sensitivity findings are in results/; no causal or policy-impact claims.

## Gates and remaining work

PASS: source reconstruction, unique Ortsteil IDs, geographic level, three defensible partial-disadvantage criteria, percentage ranges/units, complete-case annual scoring, coverage threshold, method directions and shared inputs. Primary gate passes for exploratory annual comparison only. BLOCKED: historical change claims. Conditional/unverified: source reference dates and full operational suitability.

{blocked}

Group members must add real academic references and external benchmarks, verify municipal metadata/boundary history, discuss indicator/weight choices and coverage with stakeholders, supply broader indicators if needed, and independently write report/presentation sections. The architecture remains a blueprint. No economic, ecological or social intervention outcome has been measured.

## Files and reproduction

Start with group_results/OVERVIEW.md and your section's evidence_summary.pdf. Review docs/REPRODUCING.md; run notebooks 01-08 in order. Run python src/run_technical_pipeline.py, python src/create_notebooks.py, then python src/verify_outputs.py. Exact tested package versions are in docs/environment_versions.json. docs/deliverable_manifest.json lists deliverables, modified existing files and preserved sources; original sources and Phase 1 preparation/output files are retained. requirements.txt is the only existing dependency file modified.

This completes the defensible cross-sectional technical foundation and independent architecture/package work. It does not complete the blocked longitudinal validation or the group's final academic submission.
''')
    print(f'{len(checks)} output checks passed; longitudinal gate remains blocked.',flush=True)
    return checks

if __name__ == '__main__':
    run()
