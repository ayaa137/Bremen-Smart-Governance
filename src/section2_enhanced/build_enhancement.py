"""Additive Section 2 robustness package. Run with Python -B; never overwrite outputs."""
from pathlib import Path
import sys, json, hashlib, subprocess, tempfile, shutil, itertools, platform, os, re
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
import numpy as np
import pandas as pd
import scipy
from scipy.stats import spearmanr,kendalltau,skew
import matplotlib
import analyze_section2_v2 as v2
import build_section2_atlas as atlas
from PIL import Image

REPORT=ROOT/'reports/section2_enhanced'
FIGURES=ROOT/'figures/section2_enhanced'
FEATURES=['unemployment','employment','benefit_receipt']
CONTEXT=['child_benefits','single_parents','income_median']
ALL=FEATURES+CONTEXT
ENHANCED_PREFIXES=('src/section2_enhanced/','reports/section2_enhanced/','figures/section2_enhanced/')
def discover_executable(override,names,windows_locations=()):
    configured=os.environ.get(override)
    if configured:
        found=shutil.which(configured) or (configured if Path(configured).is_file() else None)
        if not found:raise RuntimeError('Executable override not found: '+override)
        return Path(found)
    for name in names:
        found=shutil.which(name)
        if found:return Path(found)
    for variable,suffix in windows_locations:
        base=os.environ.get(variable)
        if base and (Path(base)/suffix).is_file():return Path(base)/suffix
    return None

QUARTO=discover_executable('SECTION2_QUARTO',['quarto.exe','quarto'],[('ProgramFiles','Quarto/bin/quarto.exe')])
BROWSER=discover_executable('SECTION2_BROWSER',['msedge','chromium','chromium-browser','google-chrome'],
    [('ProgramFiles(x86)','Microsoft/Edge/Application/msedge.exe'),('ProgramFiles','Google/Chrome/Application/chrome.exe')])
APPROVED_PORTABLE_V2_SHA='60b6cc0d543cd7c37fb92a1369e82ff36fdc9f358ffda9c4044287c9348270bc'

def verify_historical_hash(name,digest):
    actual=sha(ROOT/name)
    if name=='src/analyze_section2_v2.py' and actual==APPROVED_PORTABLE_V2_SHA:
        original=json.loads((ROOT/'reports/section2_v2/reproduction_manifest.json').read_text())
        require(digest==original['script_sha256'],'Historical V2 script provenance differs')
    else:require(actual==digest,'Existing verified file changed: '+name)

def require(x,message):
    if not x:raise AssertionError(message)

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()

def relative(p):return Path(p).relative_to(ROOT).as_posix()
def json_text(x):return json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
def protected_files():
    raw=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=ROOT)
    names={x.decode() for x in raw.split(b'\0') if x}
    return {n:sha(ROOT/n) for n in sorted(names) if not n.startswith(ENHANCED_PREFIXES) and (ROOT/n).is_file()}
def csv(table,p):table.to_csv(p,index=False,encoding='utf-8',float_format='%.17g')
def markdown(table):return atlas.markdown_table(table)

def verify_existing():
    for p in [ROOT/'reports/section2_v2/reproduction_manifest.json',ROOT/'reports/section2_v2/atlas/atlas_reproduction_manifest.json']:
        m=json.loads(p.read_text(encoding='utf-8'))
        for group in ['outputs','protected_input_hashes']:
            for name,h in m[group].items():verify_historical_hash(name,h)
        verify_historical_hash(m['generator'],m['script_sha256'])
    frame,long,definitions,context,coords,source_validation=v2.load_validate(validate_git=False)
    polygons,join,geoval,geo_source,extent=atlas.load_geography(frame)
    return frame,long,definitions,context,coords,source_validation,polygons,join,geoval,geo_source,extent

def stats(x):
    x=np.asarray(x.dropna(),dtype=float);n=len(x)
    q1,q3=np.quantile(x,[.25,.75],method='linear')
    return dict(n=n,mean=float(np.mean(x)),median=float(np.median(x)),sd=float(np.std(x,ddof=1)),
                q1=float(q1),q3=float(q3),iqr=float(q3-q1),minimum=float(x.min()),maximum=float(x.max()),
                p10=float(np.quantile(x,.1)),p90=float(np.quantile(x,.9)))

def tau_independent(x,y):
    x=np.asarray(x);y=np.asarray(y);i,j=np.triu_indices(len(x),1)
    dx=np.sign(x[i]-x[j]);dy=np.sign(y[i]-y[j]);den=float(np.sqrt(np.count_nonzero(dx)*np.count_nonzero(dy)))
    return float(np.sum(dx*dy)/den)

def corr(x,y):
    rho=float(spearmanr(x,y).statistic);tau=float(kendalltau(x,y,variant='b').statistic)
    independent=pd.DataFrame({'x':np.asarray(x),'y':np.asarray(y)}).rank(method='average').corr().iloc[0,1]
    require(np.isclose(rho,independent,rtol=0,atol=1e-14),'Independent Spearman check failed')
    require(np.isclose(tau,tau_independent(x,y),rtol=0,atol=1e-14),'Independent tau-b check failed')
    return rho,tau

def analyze(frame,context,definitions,coords):
    master=frame[['geo_code','geo_name','year',*FEATURES]].copy()
    for f in CONTEXT:master[f]=master.geo_code.map(context[f].set_index('geo_code').value)
    complete=master[frame.scoring_eligible].copy()
    sensitivity=[];distributions=[];outliers=[];descriptive_loo=[]
    for f in ALL:
        parts=[('available',master)] if f in CONTEXT else [('available',master),('complete',complete)]
        for sample,part in parts:
            st=stats(part[f]);year=2020 if f=='income_median' else 2024
            row=dict(feature=f,sample=sample,year=year,unit='1000 EUR' if f=='income_median' else '%',**st)
            row.update(missing_n=len(part)-st['n'],missing_pct=(len(part)-st['n'])/len(part)*100)
            valid=part.dropna(subset=[f]);x=valid[f].to_numpy();n=len(x)
            row['minimum_names']='; '.join(valid.loc[valid[f].eq(st['minimum']),'geo_name'])
            row['maximum_names']='; '.join(valid.loc[valid[f].eq(st['maximum']),'geo_name'])
            row['skewness_adjusted_fisher_pearson']=float(skew(x,bias=False))
            moments=x-x.mean();m2=np.mean(moments**2);m3=np.mean(moments**3)
            independent=np.sqrt(n*(n-1))/(n-2)*m3/m2**1.5
            require(np.isclose(row['skewness_adjusted_fisher_pearson'],independent,atol=1e-12),'Independent skewness check failed')
            row['tukey_lower_fence']=st['q1']-1.5*st['iqr'];row['tukey_upper_fence']=st['q3']+1.5*st['iqr']
            flags=(valid[f]<row['tukey_lower_fence'])|(valid[f]>row['tukey_upper_fence'])
            row['tukey_flag_n']=int(flags.sum());distributions.append(row)
            for r in valid.itertuples():
                val=getattr(r,f);flag=val<row['tukey_lower_fence'] or val>row['tukey_upper_fence']
                if flag or val==st['minimum'] or val==st['maximum']:
                    wr,wc=coords[(r.geo_code,year,f)]
                    outliers.append(dict(feature=f,sample=sample,year=year,geo_code=r.geo_code,geo_name=r.geo_name,value=val,
                      tukey_flag=flag,minimum=val==st['minimum'],maximum=val==st['maximum'],
                      lower_fence=row['tukey_lower_fence'],upper_fence=row['tukey_upper_fence'],
                      source_workbook='Datentabelle.xls',workbook_row_zero_based=wr,workbook_column_zero_based=wc,
                      source_cell_verified=True,decision='Retained; all selected workbook cells reverified, no denominator-based inference.'))
            if f in FEATURES:
                for r in valid.itertuples():
                    reduced=valid[valid.geo_code.ne(r.geo_code)][f];loo=stats(reduced)
                    descriptive_loo.append(dict(feature=f,sample=sample,excluded_geo_code=r.geo_code,excluded_geo_name=r.geo_name,n=loo['n'],
                         **{f'loo_{k}':loo[k] for k in ['mean','median','sd','iqr']},
                         **{f'delta_{k}':loo[k]-st[k] for k in ['mean','median','sd','iqr']}))
    dist=pd.DataFrame(distributions)
    for f in FEATURES:
        a=dist[(dist.feature==f)&(dist['sample']=='available')].iloc[0]
        c=dist[(dist.feature==f)&(dist['sample']=='complete')].iloc[0]
        sensitivity.append(dict(feature=f,year=2024,available_n=int(a.n),complete_n=int(c.n),
            **{f'available_{k}':float(a[k]) for k in ['mean','median','sd','iqr']},
            **{f'complete_{k}':float(c[k]) for k in ['mean','median','sd','iqr']},
            **{f'complete_minus_available_{k}':float(c[k]-a[k]) for k in ['mean','median','sd','iqr']}))
    correlations=[]
    for f,g in itertools.combinations(FEATURES,2):
        for sample,part in [('complete',complete),('pairwise',master.dropna(subset=[f,g]))]:
            rho,tau=corr(part[f],part[g])
            correlations.append(dict(first=f,second=g,sample=sample,n=len(part),year=2024,
                spearman_rho=rho,kendall_tau_b=tau,first_ties=len(part)-part[f].nunique(),second_ties=len(part)-part[g].nunique(),
                same_codes_as_complete=part.geo_code.tolist()==complete.geo_code.tolist()))
    baseline_rho,baseline_tau=corr(complete.unemployment,complete.benefit_receipt)
    loo=[]
    for r in complete.itertuples():
        part=complete[complete.geo_code.ne(r.geo_code)];rho,tau=corr(part.unemployment,part.benefit_receipt)
        loo.append(dict(excluded_geo_code=r.geo_code,excluded_geo_name=r.geo_name,n=78,spearman_rho=rho,kendall_tau_b=tau,
                        delta_rho=rho-baseline_rho,abs_delta_rho=abs(rho-baseline_rho),delta_tau_b=tau-baseline_tau))
    loo=pd.DataFrame(loo);cut=float(loo.abs_delta_rho.quantile(.9,interpolation='linear'))
    loo['sensitivity_flag']=loo.abs_delta_rho.ge(cut)
    loo['flag_criterion']='Absolute Spearman change >= sample 90th percentile; descriptive sensitivity flag, not a significance test.'
    associations=[]
    for c in ['child_benefits','single_parents']:
        for f in FEATURES:
            part=master.dropna(subset=[c,f]);rho,tau=corr(part[c],part[f])
            associations.append(dict(context=c,primary=f,year=2024,n=len(part),spearman_rho=rho,kendall_tau_b=tau,
               context_ties=len(part)-part[c].nunique(),primary_ties=len(part)-part[f].nunique(),
               interpretation='Exploratory ecological association; different populations; no causal or intrinsic-disadvantage interpretation.'))
    # Historical income is described separately; no mixed-year correlation is silently labeled 2024.
    stloo=pd.DataFrame(descriptive_loo)
    lo_summary=[]
    for (f,s),part in stloo.groupby(['feature','sample'],sort=True):
        rec=dict(feature=f,sample=s,omissions=len(part))
        for k in ['mean','median','sd','iqr']:
            rec[k+'_loo_min']=float(part['loo_'+k].min());rec[k+'_loo_max']=float(part['loo_'+k].max())
            rec[k+'_max_absolute_delta']=float(part['delta_'+k].abs().max())
        lo_summary.append(rec)
    summary=dict(n=79,baseline_rho=baseline_rho,baseline_tau_b=baseline_tau,
                 loo_n_each=78,loo_replicates=79,loo_rho_min=float(loo.spearman_rho.min()),loo_rho_max=float(loo.spearman_rho.max()),
                 loo_tau_b_min=float(loo.kendall_tau_b.min()),loo_tau_b_max=float(loo.kendall_tau_b.max()),
                 sensitivity_threshold_abs_delta_rho_p90=cut,flagged_n=int(loo.sensitivity_flag.sum()),
                 largest_change_name=loo.loc[loo.abs_delta_rho.idxmax(),'excluded_geo_name'],
                 largest_abs_delta_rho=float(loo.abs_delta_rho.max()))
    tables={'correlation_robustness.csv':pd.DataFrame(correlations),'missingness_sensitivity.csv':pd.DataFrame(sensitivity),
            'distribution_robustness.csv':dist,'source_verified_extremes.csv':pd.DataFrame(outliers),
            'correlation_leave_one_out.csv':loo,'descriptive_leave_one_out.csv':stloo,
            'descriptive_sensitivity_ranges.csv':pd.DataFrame(lo_summary),'contextual_associations_2024.csv':pd.DataFrame(associations)}
    # Independently recalculated results must agree with the preserved V2 tables.
    for sample,path in [('available','descriptive_available_cases.csv'),('complete','descriptive_complete_cases.csv')]:
        previous=pd.read_csv(ROOT/'reports/section2_v2'/path,float_precision='round_trip').set_index('feature')
        for r in dist[(dist['sample']==sample)&dist.feature.isin(FEATURES)].itertuples():
            for key,oldkey in [('n','valid_n'),('mean','mean'),('median','median'),('sd','sd_sample'),('iqr','iqr')]:
                require(np.isclose(getattr(r,key),previous.loc[r.feature,oldkey],rtol=0,atol=1e-12),'Prior statistics inconsistent')
    return master,complete,tables,summary

def assessment(definitions,tables):
    distribution=tables['distribution_robustness.csv'].set_index(['feature','sample'])
    corrtable=tables['correlation_robustness.csv'];contextcorr=tables['contextual_associations_2024.csv']
    rows=[]
    for r in definitions.itertuples():
        s=distribution.loc[(r.feature,'available')]
        if r.feature in FEATURES:
            associations=corrtable[(corrtable['sample']=='complete')&((corrtable['first']==r.feature)|(corrtable['second']==r.feature))]
            overlap='; '.join(f'{p.first}/{p.second}: rho={p.spearman_rho:.6f}, tau-b={p.kendall_tau_b:.6f}, n={p.n}' for p in associations.itertuples())
        elif r.feature=='child_benefits':
            p=contextcorr[(contextcorr.context==r.feature)&(contextcorr.primary=='benefit_receipt')].iloc[0]
            overlap=f'Under-15 population overlaps under-65 population: matched rho={p.spearman_rho:.6f}, n={p.n}; conceptual dependence, not independent validation.'
        elif r.feature=='single_parents':overlap='Exploratory ecological associations do not make family structure a deprivation measure.'
        else:overlap='Excluded from 2024 associations; year and taxpayer denominator differ.'
        role={'child_benefits':'Supplementary 2024 child-focused economic context','single_parents':'2024 household-composition context; no intrinsic deprivation direction',
              'income_median':'Separate 2020 historical taxpayer-income context'}.get(r.feature,'Primary 2024 economic measure')
        measurement={'unemployment':'Restricted unemployment quotient; not the official all-civilian-labour-force rate.',
                     'employment':'Insured employees only; excludes self-employment/civil servants. Lower participation has multiple possible explanations.',
                     'benefit_receipt':'Benefit entitlement/receipt; not all poverty or unmet need, and may coexist with employment.',
                     'child_benefits':'Child age-subgroup benefit reliance; denominators overlap overall receipt, not general child wellbeing.',
                     'single_parents':'Households with children at main residence; composition does not establish economic deprivation.',
                     'income_median':'Total income per taxpayer, not household disposable income or per-resident income.'}[r.feature]
        rows.append(dict(feature=r.feature,german_source_label=r.original_german_name,english_translation=r.english_name,
            source_file=r.source_file,source_worksheet=r.source_sheet,indicator_block=int(r.indicator_block),
            definition_and_denominator=r.definition,unit=r.unit,reporting_year=int(s.year),geographic_level='Ortsteil statistical unit',
            valid_n=int(s.n),master_n=88,missing_n=int(s.missing_n),missing_pct=float(s.missing_pct),
            conceptual_relevance=r.role,measurement_validity_and_scope=measurement,role_recommendation=role,
            temporal_consistency='Annual reporting period verified; exact reference day and revision policy unverified. No trend comparability established.' if r.feature!='income_median' else '2020 only; no carry-forward, 2024 pairing or current-condition claim.',
            source_traceability='Exact worksheet, heading, block and original workbook cells reverified; input hashes frozen.',
            redundancy_evidence=overlap,missingness_limitations='Available cases and 79-case economic baseline distinguished; reasons/mechanism unknown, no imputation or MAR assumption.',
            municipal_interpretation='Expose denominators, dates, exclusions and geography crosswalk; aggregate evidence, no causal or allocation rule.',
            downstream_methods='Section 4 may assess sensitivity to redundant economic indicators; no weights or numeric suitability scores supplied.' if r.feature in FEATURES else 'Keep supplementary/contextual/historical role explicit; do not automatically add as a deprivation component.',
            suitability_is_not_correlation='Qualitative relevance, measurement scope and traceability are evaluated separately from empirical association.',
            unresolved_definition_issues='Exact municipal reference days, denominator counts, household/taxpayer conventions and full boundary equivalence require verification.'))
    return pd.DataFrame(rows)

def audit(protected,sourceval,geoval):
    original_v2=json.loads((ROOT/'reports/section2_v2/reproduction_manifest.json').read_text(encoding='utf-8'))
    original_atlas=json.loads((ROOT/'reports/section2_v2/atlas/atlas_reproduction_manifest.json').read_text(encoding='utf-8'))
    now_v2={n:h for n,h in v2.protected_files().items() if not n.startswith(ENHANCED_PREFIXES[1:])}
    now_atlas={n:h for n,h in atlas.protected_files().items() if not n.startswith(ENHANCED_PREFIXES[1:])}
    findings=[
      ('Confirmed issue','V2 geographic-availability paragraph is historical','The V2 note says polygons are unavailable; the later atlas archives official GML/ZIP polygons. The old note is preserved as an audit-time document.','Enhanced report cites the later atlas resources and its geographic caveats.'),
      ('Confirmed issue','Broad inventory guards prevent additive-project reruns',f'Frozen V2 inventory={len(original_v2["protected_input_hashes"])}, current={len(now_v2)}; frozen atlas inventory={len(original_atlas["protected_input_hashes"])}, current={len(now_atlas)}. File-content hashes still agree; inventory growth can make old manifest equality fail.','Do not run or alter old generators. Enhanced pipeline excludes its own namespaces and keeps a separate manifest; fixed inputs and prior artifact hashes are still verified.'),
      ('Confirmed issue','Prior contextual overlap used a narrower sample','V2 under-65/under-15 receipt association is on 79 complete economic cases. Matched available observations permit 84 pairs; the previous result is valid for its stated sample.','Recalculate and label both contextual coverage and matched available-case associations; no old finding overwritten.'),
      ('Potential issue requiring verification','Oberneuland boundary equivalence', '87 direct Ortsteil polygons + explicit undivided Stadtteil 04011360 -> statistical 361. Documentary correspondence supports this exception but does not prove exact 2024 legal boundary-reference day.','Retain the archived documented crosswalk; no general level conversion, no new geometry or claim of legal certification.'),
      ('Potential issue requiring verification','Statistical and boundary reference days','Dataset revision is 11 December 2024, not exact legal validity; annual statistical reporting periods do not identify identical observation days.','Display revision date accurately; prohibit causal/current-2026 and historical-change claims.'),
      ('Potential issue requiring verification','Geometry topology certification','Finite closed rings, area checks and code coverage passed. No installed GIS topology engine certifies self-intersections, overlaps or gaps.','Keep original coordinates and disclose scope of checks; do not claim full topology certification.'),
      ('Potential issue requiring verification','Missingness mechanism and denominator size','No documented reasons or denominator counts establish MAR, sampling precision or population consequences.','No imputation, causal interpretation, confidence intervals or missingness-reason speculation.'),
      ('Optional improvement','Correlation robustness','Prior Spearman results are consistent with recalculated values; alternative rank metric and omission sensitivity were absent.','Add independently checked Kendall tau-b and all 79 leave-one-out checks; sensitivity flags are descriptive.'),
      ('Optional improvement','Publication precision and visual semantics','Atlas cards display four decimals; sequential palette grows lighter with value and bivariate cutpoints are mainly in reports.','Cards use one decimal, retain CSV precision; higher-value darker palette and numerical bivariate cutpoints; preserve class assignments.'),
      ('Optional improvement','Interactive evidence and report formats','No project Quarto/QMD convention was found; static validated figures are available.','New standalone QMD and offline inline-SVG explorer; preserve shared configuration and avoid external tiles.'),
    ]
    table=pd.DataFrame(findings,columns=['classification','finding','supporting_evidence','handling'])
    text=f'''# Independent quality audit

Audited shared definitions, source workbook, V2/atlas scripts, manifests, reports, source licensing and original figures. This is additive; all existing validated outputs are preserved.

Verified baseline: {sourceval['commit']}, branch analysis/section-2-v2. Source checks: {sourceval['workbook_cells_verified']} original workbook cells, {sourceval['source_hashes_verified']} source hashes; geographic join {geoval['final_matched']}/88, with one explicit Oberneuland level exception. Existing descriptive tables agree with independent NumPy recalculation within 1e-12; Spearman independently agrees with rank covariance and tau-b with pairwise concordance/tie counts. All old manifest outputs/input hashes agree.

{markdown(table)}

The old manifests are frozen historical inventories. Their metadata changes after unrelated additions are not evidence that original numeric results changed. The current counts above exclude enhancement output directories for stable audit reporting; older guards also see those additional outputs after publication. This enhancement generator therefore validates the prior hashes without publishing or rewriting old results. It also reuses read-only source/geometry validators, not their output-writing entry points.

No untracked output path existed in any of the three enhancement directories at first inspection. New paths are independently staged, collision-checked and hashed. Existing figures are visually inspected and PNG metadata verified; their economic observations, selected cases, class assignments and denominators remain unchanged in refined copies. New demographic claims are restricted to the two available contextual indicators; income remains 2020.

No packages installed. No shared tracked edits, branch changes, commits or pushes. See preservation_inventory.csv and enhancement_validation.json for evidence.
'''
    return table,text

def report_text(master,tables,summary,assessment_table,classes):
    dist=tables['distribution_robustness.csv'];correlations=tables['correlation_robustness.csv'];sens=tables['missingness_sensitivity.csv']
    contextcorr=tables['contextual_associations_2024.csv']
    benefit=sens[sens.feature.eq('benefit_receipt')].iloc[0]
    flagged=tables['correlation_leave_one_out.csv'].query('sensitivity_flag').sort_values(['abs_delta_rho','excluded_geo_code'],ascending=[False,True])
    brief=dist[(dist['sample']=='available')][['feature','year','n','mean','median','sd','iqr','skewness_adjusted_fisher_pearson']].rename(columns={'skewness_adjusted_fisher_pearson':'adjusted_skewness'})
    primarycorr=correlations[correlations['sample']=='complete'][['first','second','n','spearman_rho','kendall_tau_b']]
    defs=assessment_table[['feature','german_source_label','english_translation','source_worksheet','indicator_block','unit','reporting_year','valid_n','missing_pct','definition_and_denominator']]
    definition_blocks='\n\n'.join(f'**{r.english_translation}** ({r.reporting_year}; {r.unit}; n={r.valid_n}/88). German source heading: {r.german_source_label}. Worksheet: {r.source_worksheet}, block {r.indicator_block}. {r.definition_and_denominator}' for r in defs.itertuples())
    sens_display=sens[['feature','available_n','complete_n','available_mean','complete_mean','complete_minus_available_mean']].rename(columns={'complete_minus_available_mean':'mean_difference_pp'})
    images='../../figures/section2_enhanced/'
    body=f'''## 2.1 Data Sources and Geographic Coverage

Section 2 answers RQ1, **what socioeconomic and demographic differences exist across Bremen neighborhoods**, and RQ2, **which indicators are useful for identifying neighborhood disadvantage**. The evidence concerns 2024 observations, not current conditions. Input is the shared `data/processed/ortsteil_analysis_ready.csv` at commit `{atlas.BASELINE}`. Supplementary data come from `selected_indicators_long.csv`; definitions come from `analysis/indicator_selection.csv` and `analysis/data_dictionary.csv`.

All 88 represented statistical records remain in coverage documentation. The comparison sample comprises 79 Ortsteile with all three primary economic indicators. Codes remain strings. No missing observation is imputed. Exact German headings, units, reporting periods and all 9,152 selected workbook cells were reverified; 24 original-source hashes match. Descriptive statistics are unweighted neighborhood summaries, not population-weighted Bremen city rates.

Official boundaries are archived ATKIS Verwaltungsgrenzen from **Landesamt GeoInformation Bremen**, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), EPSG:25832. [Official metadata]({atlas.META}) identifies a dataset revision of **11 December 2024**; access was 10 October 2026. A revision date is not proof of an exact legal validity day. The join matches 87 direct Ortsteil polygons and one explicitly documented undivided Oberneuland Stadtteil polygon to statistical code 361. All 88 records match; the three spelling differences remain documented. The separate overseas-port enclave and Bremerhaven are outside the represented mainland scope. Closed rings, coordinates, CRS and published areas were checked; no full topology certification is claimed.

## 2.2 Indicator Selection and Preprocessing

Unemployment is registered unemployed divided by insured employees plus unemployed; it is **not** the official all-civilian-labour-force unemployment rate. Employment participation covers socially insured employees at residence relative to population aged 15–<65, excluding employment outside social insurance. SGB II receipt covers recipients relative to population under 65, not all poverty or unmet benefit need. These different populations make percentages non-interchangeable.

Under-15 SGB II receipt is child-focused economic context and overlaps under-65 receipt. Single-parent share describes main-residence households with children and is **not intrinsic disadvantage**. Taxpayer income is a separate **2020** median in thousand EUR, not 2024 household disposable income. The available contextual indicators do not fully characterize demographic inequality.

Exact definitions and coverage:

{definition_blocks}

{markdown(assessment_table[['feature','reporting_year','valid_n','missing_n','missing_pct','role_recommendation']])}

The qualitative suitability framework evaluates relevance, measurement scope, coverage, reference periods, traceability, redundancy and municipal interpretability separately. Empirical correlation is one source of overlap evidence, not a criterion that establishes validity or selects an objectively best indicator. Primary economic measures remain unemployment, employment participation and SGB II receipt; child receipt is supplementary, household composition contextual, and income historical. No numerical suitability scores or weights are assigned. Full assessment: `indicator_suitability_framework.csv`.

## 2.3 Neighborhood Differences, Indicator Relationships and Robustness

### Observed differences and distribution shapes

The following available-case results retain source precision in CSVs; displayed values are rounded. Sample SD uses ddof=1; quartiles/percentiles use linear interpolation. Adjusted Fisher–Pearson skewness is independently checked using central moments. Histograms support shape interpretation; skewness alone does not establish a distributional model.

{markdown(brief)}

Unemployment ranges from Seehausen 2.5896% to Ohlenhof 27.5409%; SGB II receipt from In den Hufen 0.9901% to Ohlenhof 34.6216%. Employment ranges from Fähr-Lobbendorf 44.1589% to Seehausen 72.7138%. These are observed economic contrasts; neither individual need nor causes can be inferred.

![Economic distributions, 2024, 79 complete Ortsteile; distinct denominators, unweighted counts. Source: supplied workbook via shared data. All observations retained.]({images}fig01_economic_distributions_2024.png)

The exploratory Tukey rule flags values below Q1−1.5×IQR or above Q3+1.5×IQR, strictly outside the fences. Employment flags Rablinghausen, Seehausen, Grohn and Fähr-Lobbendorf. Unemployment and under-65 SGB II have no such flags. Hohweg is flagged for single-parent share, and Borgfeld for historical income. All flagged/extreme cells were reverified in the original workbook and retained. Flags are not errors or neighborhood risk labels. Source review and both sample-specific rules are in `source_verified_extremes.csv`.

### Rank relationships and omission sensitivity

{markdown(primarycorr)}

Each primary pairwise sample contains the **same 79 codes** as the complete-case sample, so pairwise correlations do not recover additional evidence. Spearman is checked against rank covariance; Kendall tau-b is checked independently using all concordant/discordant pairs with tie-adjusted denominator. No tied primary values occur here; the implementation and tests still handle ties. [SciPy's Kendall tau-b definition](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.kendalltau.html) documents the variant. P-values are not used to turn a descriptive observed-area comparison into a random-sample inference.

The unemployment–SGB II relationship has rho={summary['baseline_rho']:.10f} and tau-b={summary['baseline_tau_b']:.10f}, n=79. Across all 79 single-neighborhood omissions (n=78 each), rho spans **{summary['loo_rho_min']:.10f}–{summary['loo_rho_max']:.10f}** and tau-b **{summary['loo_tau_b_min']:.10f}–{summary['loo_tau_b_max']:.10f}**. The largest absolute rho change is **{summary['largest_abs_delta_rho']:.10f}**, excluding {summary['largest_change_name']}. The strong positive monotonic association persists under every single omission; this does not address simultaneous omissions, definition changes, population weights or unobserved areas.

Eight observations meet the reproducible exploratory sensitivity criterion |delta rho|≥the sample 90th percentile ({summary['sensitivity_threshold_abs_delta_rho_p90']:.10f}). This is an operational review flag, not a significance test or proof of statistical influence. All observations remain in the baseline analysis:

{markdown(flagged[['excluded_geo_code','excluded_geo_name','spearman_rho','delta_rho','delta_tau_b']])}

![Distribution of all 79 omission correlations; each recalculation uses 78 Ortsteile. Narrow separate horizontal scales are explicit; these ranges are not confidence intervals.]({images}correlation_leave_one_out_sensitivity_2024.png)

All available/complete-case descriptive leave-one-out values and their mean/median/SD/IQR ranges are exported. This checks whether a single case changes summaries without deleting valid observations or changing source data.

### Missingness sensitivity

{markdown(sens_display)}

Unemployment and employment use identical available and complete samples. Restricting SGB II from 84 to 79 raises its mean by **{benefit.complete_minus_available_mean:.6f} percentage points**, median by **{benefit.complete_minus_available_median:.6f} points**, reduces SD by {abs(benefit.complete_minus_available_sd):.6f} points and IQR by {abs(benefit.complete_minus_available_iqr):.6f} points. The minimum changes from In den Hufen to Borgfeld; the maximum remains Ohlenhof. Thus broad observed variation persists but numerical summaries and extrema depend on sample restriction. No missing-at-random assumption or correction for selection bias is made.

### Contextual variation and exploratory association

Child SGB II receipt has 84 observations, mean 22.0805%, median 20.7702%, range 0.0000% (In den Hufen)–53.6825% (Bahnhofsvorstadt). The genuine zero is preserved; blanks are not treated as zero. Single-parent share has 83 observations, mean 24.9255%, median 25.9427%, range 9.7561% (Blockland)–42.8571% (Hohweg). Historical taxpayer income has 84 observations in 2020, mean 28.0060 and median 27.0980 thousand EUR, range 16.0030 (Lindenhof)–51.8630 (Borgfeld). Income is described separately, with no mixed-year association presented as 2024.

{markdown(contextcorr[['context','primary','year','n','spearman_rho','kendall_tau_b']])}

Under-15 and under-65 receipt share a population component and a benefit-system concept. Their available matched correlation uses n=84, unlike the preserved V2 n=79 result. This strong relationship does not supply independent corroboration. Household-structure associations are ecological and cannot justify an intrinsic-deprivation interpretation or distinguish selection from other mechanisms. These are exploratory comparisons without causal claims or confirmatory multiple-test inference.

![Two 2024 contextual distributions and separately labeled 2020 taxpayer income; available-case counts differ and axes are separate. Family structure is contextual, not intrinsic deprivation.]({images}contextual_distributions_separate_periods.png)

## 2.4 Atlas Evidence and Smart-Governance Implications

Redesigned maps keep the original geographic join, data values, extents and fixed 5-percentage-point classes (0–35% for unemployment/SGB II). The perceptually ordered cividis palette is reversed so higher numerical rates are darker. Gray denotes missing. This color ordering describes indicator values, not an official deprivation classification. Land area is not affected population.

![Comparable unemployment and SGB II maps; all 88 represented statistical units, n=79 and n=84 observed respectively. Distinct denominators. Boundaries: Landesamt GeoInformation Bremen, ATKIS, dataset revision 11 December 2024, CC BY 4.0; explicit Oberneuland exception.]({images}enhanced_atlas_economic_maps_side_by_side_2024.png)

The bivariate map preserves original sample tertiles and assignments. Unemployment cutpoints are 8.5398%/14.1290%; SGB II 10.2200%/18.0283%. Values exactly on boundaries go to the lower class; each marginal has group sizes 27/26/26. Of 79 paired observations, 65 (82.28%) occupy the same tertile and 14 differ. These sample-relative categories are not official socioeconomic risk groups, a composite score or evidence of formal spatial clustering.

![Unchanged bivariate assignments; numeric cutpoints, dimensions and 65/79 agreement are visible. Nine records missing either rate remain gray; all 88 geographic records retained.]({images}enhanced_atlas_bivariate_economic_2024.png)

The missingness map retains 79 complete areas, five missing two economic indicators and four missing all three. None lack exactly one; no selected geometry lacks a socioeconomic row. Missingness explanations are unknown. Hiding excluded units from decision support would conceal evidence gaps, but neither affected population nor allocation consequences are estimated.

![Economic data blind spots across all 88 represented units; missing is not zero. Official boundary attribution and revision date remain explicit.]({images}enhanced_atlas_data_blind_spots_2024.png)

Cards retain the atlas's purposive selection: Ohlenhof (coincident maxima), Seehausen (unemployment minimum), Industriehäfen (first-code wholly missing case), and Hastedt (only strict median-disagreement case). Hastedt is above the unemployment median and below the SGB II median, but remains in the middle tertile of both; disagreement depends on thresholds. Percentages display to one decimal while CSV precision is unchanged. These examples are not representative or officially classified.

![Selected economic evidence cards, 2024; shared 0–100% axes, explicit denominators, missing labels and highlighted threshold-dependent Hastedt contrast.]({images}enhanced_atlas_neighborhood_evidence_cards_2024.png)

The offline `evidence_explorer.html` exposes selectable primary indicators, 88 original-coordinate polygons, definitions, values, missingness and geography caveats without external tiles, scripts or network data. It is a research prototype, not a deployed municipal service. Keyboard focus, a neighborhood selector and browser-tested events support access. No universal color-vision or WCAG certification is claimed.

## 2.5 Limitations and Handover

RQ1 is answered by the documented differences and coverage gaps; the two contextual indicators do not constitute a comprehensive demographic inequality assessment. RQ2 supports the three economic measures within their restricted definitions, distinguishes demographic context and historical income, and flags strong overlap. Suitability rests on substantive scope and traceability, not correlation alone.

Exact statistical reference dates, denominator counts, full municipal definitions and legal boundary-validity day remain unresolved. Geographic compatibility is documented annually, not certified historically. Missingness reasons are unknown. Rates are ecological and unweighted; there are no causal, individual-poverty, random-sample or current-2026 claims. Omission sensitivity checks a limited perturbation, not all robustness threats. No composite index, TOPSIS, clustering, method-agreement metric or deprivation ranking is implemented.

Section 1 can use verified contrasts for framing. Section 3 can use definitions, provenance, exclusions and geographic caveats for transparent decision support. Section 4 receives unchanged primary values and overlap warnings; its weighting, normalization, composite methods and comparative-method assessment remain separate. Existing validated artifacts are preserved; new manifests and audit findings are additive.

Reproduce from repository root:

```powershell
.\\.venv-section2\\Scripts\\python.exe -B src\\section2_enhanced\\build_enhancement.py
```

No new packages are required. All figures have PNG/PDF/SVG versions, with deterministic export metadata. Quarto rendering and browser checks run in temporary isolated directories. Offline reproduction depends on the archived authoritative inputs and polygons. Original generator inventories can reject a new full rerun after additive files appear; their frozen evidence remains verified unchanged. The enhanced pipeline has an independent manifest and collision guard.
'''
    integration=f'''# Section 2 — integration-ready text

## 2.1 Data sources, coverage and indicator selection

The shared 2024 dataset contains 88 represented Bremen statistical Ortsteile, including 79 complete cases for unemployment, socially insured employment and SGB II receipt. Original workbook cells and provenance were verified. All records remain in missingness documentation; blanks are not imputed. Percentages have distinct denominators: unemployment uses insured employees plus unemployed; employment uses population aged 15–<65; SGB II uses population under 65. Under-15 receipt is supplementary, household composition contextual, and 2020 taxpayer income historical. Official ATKIS polygons match 87 direct Ortsteile plus an explicit undivided Oberneuland crosswalk. Dataset revision is 11 December 2024, not a verified legal validity date.

## 2.2 Neighborhood differences and robustness

Observed unemployment ranges from 2.5896% in Seehausen to 27.5409% in Ohlenhof; SGB II receipt from 0.9901% in In den Hufen to 34.6216% in Ohlenhof. Employment ranges from 44.1589% in Fähr-Lobbendorf to 72.7138% in Seehausen. Summaries are equally weighted neighborhood observations, not city population rates. Valid exploratory outliers were retained after source verification.

Unemployment–SGB II Spearman rho={summary['baseline_rho']:.6f} and Kendall tau-b={summary['baseline_tau_b']:.6f}, n=79. All primary pairwise samples equal the complete-case sample. Across 79 single-case omissions, rho ranges {summary['loo_rho_min']:.6f}–{summary['loo_rho_max']:.6f}; the largest absolute change is {summary['largest_abs_delta_rho']:.6f}, excluding {summary['largest_change_name']}. This strong monotonic relationship is robust to a single omission, not causal or independent validation of deprivation. Restricting SGB II from 84 available observations to 79 raises the mean by {benefit.complete_minus_available_mean:.6f} points and median by {benefit.complete_minus_available_median:.6f} points; missingness assumptions remain unsupported.

Child SGB II receipt averages 22.0805% (n=84), with strong overlap with overall receipt. Single-parent share averages 24.9255% (n=83), describing family structure rather than intrinsic disadvantage. Historical median taxpayer-income values remain explicitly 2020. These do not fully characterize demographic inequality.

## 2.3 Indicator suitability and governance implications

The three primary indicators offer complementary restricted economic perspectives; high unemployment–receipt overlap requires attention in Section 4 without assigning weights here. Maps retain all 88 units and original tertiles; 65/79 (82.28%) paired observations share a tertile. Missingness is visible: 79 complete areas, five missing two indicators and four missing all three. These are evidence gaps, not favorable conditions or official risk classes. Geography, reference-day and denominator limitations remain explicit; land area is not affected population. The offline explorer exposes these caveats transparently. Composite indices, TOPSIS, clustering, architecture and resource-allocation decisions belong outside Section 2.
'''
    return body,integration

def qmd(body):
    return '''---
title: "Section 2: Data and Indicator Analysis — Bremen 2024"
subtitle: "Independent robustness, contextual evidence and geographic transparency"
format:
  html:
    embed-resources: true
    theme: none
    toc: true
    html-math-method: plain
execute:
  enabled: false
lang: en
---

'''+body

def render_quarto(rstage):
    if QUARTO is None:return dict(status='BLOCKED',reason='Quarto unavailable on PATH; set SECTION2_QUARTO. QMD source supplied.'),[]
    version=subprocess.check_output([str(QUARTO),'--version'],stdin=subprocess.DEVNULL).decode().strip()
    result=subprocess.run([str(QUARTO),'render','section2_enhanced.qmd','--to','html','--output','section2_enhanced.html'],
                          cwd=rstage,stdin=subprocess.DEVNULL,capture_output=True,timeout=55)
    if result.returncode:
        # No claim of rendering success if the installed program cannot render.
        return dict(status='BLOCKED',version=version,reason=(result.stderr.decode('utf-8',errors='replace')[-3000:]).replace(str(rstage),'<temporary report directory>')),[]
    path=rstage/'section2_enhanced.html'
    require(path.is_file(),'Quarto did not produce HTML')
    text=path.read_text(encoding='utf-8')
    require('2.1 Data Sources' in text and '0.972837' in text,'Rendered report lacks validated content')
    # Hyperlinks may be external; render-time scripts/styles/images must be embedded.
    external=re.findall(r'<(?:script|img|link)\b[^>]*\b(?:src|href)=["\']((?:https?:)?//[^"\']+)',text)
    require(not external,'Rendered HTML requires network resources: '+str(external))
    return dict(status='PASS',version=version,standalone_html=True,external_render_resources=0,
                pdf_report_status='Not rendered: no installed LaTeX toolchain; vector PDF figures are supplied. Bundled Typst availability is audited separately.'),[path]

def check_explorer(path):
    text=path.read_text(encoding='utf-8')
    require(len(re.findall(r'<path id="geo-',text))==88,'Explorer path count differs')
    require(not re.search(r'<script[^>]+src=|<link[^>]+href=|fetch\(|XMLHttpRequest|<iframe',text),'Explorer has external execution/resource dependency')
    data=json.loads(re.search(r'<script id="evidence-data" type="application/json">(.*?)</script>',text,re.S).group(1))
    require(len(data['rows'])==88 and len({r['code'] for r in data['rows']})==88,'Explorer records invalid')
    require(sum(r['complete'] for r in data['rows'])==79,'Explorer completeness invalid')
    if BROWSER is None:return dict(static_checks='PASS',browser_status='BLOCKED',reason='No Chromium browser on PATH; set SECTION2_BROWSER. Static checks passed; browser tests not run.')
    with tempfile.TemporaryDirectory(prefix='bremen-explorer-browser-') as profile:
        command=[str(BROWSER),'--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check',
                 '--disable-background-networking','--disable-component-update','--disable-sync',
                 '--disable-extensions','--disable-component-extensions-with-background-pages',
                 '--user-data-dir='+profile,'--dump-dom',path.as_uri()+'#selftest']
        result=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,timeout=45,
                              creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        output=result.stdout.decode('utf-8',errors='replace')
        require(result.returncode==0 and 'data-test-status="PASS"' in output,'Browser explorer self-test failed: '+result.stderr.decode('utf-8',errors='replace')[-1000:])
        test=re.search(r'<pre id="browser-selftest-result">(.*?)</pre>',output,re.S)
        require(test is not None,'Browser did not return test evidence')
        import html
        status=json.loads(html.unescape(test.group(1)))
        return dict(static_checks='PASS',browser_status='PASS',self_tests=status,
                    browser='Discovered Chromium browser, isolated temporary profile, headless; no browser installation.',
                    user_validation_limit='Automated selectors/click/keyboard/value/coverage tests; no universal accessibility certification.')

def support_documents(classes,summary):
    recommendations='''# Figure selection recommendations

For the main group report, choose three visual contributions: (1) enhanced_atlas_economic_maps_side_by_side_2024.png for RQ1 economic geography; (2) fig03_economic_indicator_relationships_2024.png for RQ2 overlap, with robustness ranges in text; (3) contextual_distributions_separate_periods.png to keep demographic context and 2020 income distinct. If space is limited, use two and move contextual distributions to the supplement.

For the presentation, evidence cards and the missingness map show contrasting observations and evidence gaps clearly. Keep the bivariate map supplementary unless numerical cutpoints and sample-relative categories can be explained. All figures have PNG/PDF/SVG copies; PNG is 300 DPI, PDF/SVG preserve vector paths/text. Statistical, missingness and omission-sensitivity details belong in the supplement.

Every map caption must retain statistical year 2024, geographic scope, distinct denominators, official boundary attribution/license and dataset revision 11 December 2024. Large geographic area is not affected population. Selected cards are not representative. Single-parent share is not intrinsic deprivation; taxpayer income remains 2020.
'''
    handover=f'''# Handover to Sections 1, 3 and 4

Section 1: use verified economic contrasts and contextual variation; do not treat household composition as deprivation or historical income as current. The 88 represented mainland units include the explicit Oberneuland exception.

Section 3: expose definitions, original labels, reference periods, missingness and provenance. The offline explorer is a university research prototype, not a deployed municipal service or shared architecture implementation. No external tiles or invented coordinates are used. Source/license and limitations remain visible.

Section 4: authoritative shared data and the 79-case economic sample remain unchanged. Spearman/Kendall and omission sensitivity show indicator overlap, not agreement among composite methods. Unemployment–SGB II rho={summary['baseline_rho']:.10f}, tau-b={summary['baseline_tau_b']:.10f}; strongest single omission changes rho by {summary['largest_abs_delta_rho']:.10f}. Tertile agreement remains 65/79, a descriptive indicator comparison. Do not automatically add child receipt or family structure as independent deprivation components; preserve the 2020 income distinction. Weights, normalization, composite methods, TOPSIS, clustering and method comparisons remain Section 4's work.

Existing validated files were preserved. Enhanced reports provide separate source/correlation/missingness/distribution/suitability evidence. Prior broad inventory guards may refuse old generator reruns after additive files appear; their source and output hashes remain unchanged. Use the enhanced manifest for this additive contribution.
'''
    checklist='''# Final quality-review checklist

- [x] Shared datasets and all original V2/atlas artifacts verified against frozen hashes.
- [x] Geographic string codes, 88 represented records, 79 complete cases and contextual counts checked.
- [x] Exact worksheet labels, annual periods and 9,152 original cells reverified.
- [x] Statistical calculations independently checked; available/complete samples explicit.
- [x] Kendall tau-b concordance/tie denominator and Spearman rank covariance checked.
- [x] All 79 omission checks retained; review flags explicitly descriptive.
- [x] Missing observations never imputed; observed zero child receipt retained.
- [x] All outliers/extrema retained with workbook coordinates and verification.
- [x] Original geographic crosswalk, vertices and bivariate categories preserved.
- [x] Figure inputs checked; PNG/PDF/SVG exports preserve observations.
- [x] Contextual indicators and historical income separated; no intrinsic household-deprivation claim.
- [x] Offline explorer static structure and browser interaction results recorded.
- [x] QMD figure references validated; Quarto render status recorded honestly.
- [x] Pipeline built twice; byte hashes compared before publication.
- [x] Existing-file preservation and absence of shared tracked edits checked.
- [ ] Exact municipal reference days and denominator counts verified — unresolved.
- [ ] Full GIS topology and legal boundary-validity day certified — unresolved.
- [ ] Comprehensive demographic inequality measured — unsupported by selected indicators.
- [ ] Universal accessibility certification — not claimed.

Executable validations, render/browser outcomes and deterministic hashes are in enhancement_validation.json and reproducibility_manifest.json. No causal, allocation, composite-score, TOPSIS or clustering claims are made.
'''
    return recommendations,handover,checklist

def build(stage,inputs,protected):
    from enhanced_figures import render
    from evidence_explorer import create
    frame,long,definitions,context,coords,sourceval,polygons,join,geoval,geo_source,extent=inputs
    rstage=stage/'reports/section2_enhanced';fstage=stage/'figures/section2_enhanced'
    rstage.mkdir(parents=True);fstage.mkdir(parents=True)
    master,complete,tables,summary=analyze(frame,context,definitions,coords)
    biv,counts,miss,cards,classes=atlas.build_tables(frame)
    # Preserve original classifications exactly, including boundaries and missing classes.
    existing=pd.read_csv(ROOT/'reports/section2_v2/atlas/bivariate_classification_2024.csv',dtype={'geo_code':str},float_precision='round_trip')
    for key in ['geo_code','unemployment_class','benefit_receipt_class','combined_bivariate_category','missingness_status']:
        if key.endswith('_class'):
            require(np.allclose(existing[key].to_numpy(dtype=float),biv[key].to_numpy(dtype=float,na_value=np.nan),rtol=0,atol=0,equal_nan=True),'Bivariate categories changed: '+key)
        else:
            require(existing[key].fillna('').astype(str).tolist()==biv[key].fillna('').astype(str).tolist(),'Bivariate categories changed: '+key)
    suitability=assessment(definitions,tables);tables['indicator_suitability_framework.csv']=suitability
    tables['contextual_coverage.csv']=suitability[suitability.feature.isin(CONTEXT)][['feature','reporting_year','unit','valid_n','missing_n','missing_pct','source_worksheet','definition_and_denominator']]
    tables['neighborhood_card_data_2024.csv']=cards
    tables['bivariate_classification_2024.csv']=biv
    tables['spatial_missingness_2024.csv']=miss
    tables['geographic_join_validation.csv']=join
    audit_table,audit_text=audit(protected,sourceval,geoval);tables['audit_findings.csv']=audit_table
    tables['preservation_inventory.csv']=pd.DataFrame([dict(path=n,sha256=h,bytes=(ROOT/n).stat().st_size) for n,h in protected.items()])
    for name,table in tables.items():csv(table,rstage/name)
    for name,obj in [('correlation_sensitivity_summary.json',summary),('geographic_join_validation.json',geoval),
                     ('source_validation.json',sourceval),('classification_breaks.json',classes)]:
        (rstage/name).write_text(json_text(obj),encoding='utf-8')
    print('Generating enhanced PNG/PDF/SVG figures...',flush=True)
    artifacts,mapvalid,selected,grid=render(fstage,frame,complete,context,polygons,extent,biv,miss,cards,classes,tables['correlation_robustness.csv'],tables['correlation_leave_one_out.csv'],summary)
    csv(selected,rstage/'selected_comparison_observations.csv')
    explorer=create(frame,definitions,polygons,extent);(rstage/'evidence_explorer.html').write_text(explorer,encoding='utf-8')
    print('Checking offline explorer in installed browser...',flush=True)
    browserv=check_explorer(rstage/'evidence_explorer.html')
    body,integration=report_text(master,tables,summary,suitability,classes)
    (rstage/'section2_enhanced.qmd').write_text(qmd(body),encoding='utf-8')
    (rstage/'methods_results.md').write_text('# Enhanced Section 2 evidence\n\n'+body,encoding='utf-8')
    (rstage/'integration_ready_section2.md').write_text(integration,encoding='utf-8')
    (rstage/'quality_audit.md').write_text(audit_text,encoding='utf-8')
    recommendations,handover,checklist=support_documents(classes,summary)
    for name,text in [('figure_selection_recommendations.md',recommendations),('teammate_handover.md',handover),('final_quality_review_checklist.md',checklist)]:
        (rstage/name).write_text(text,encoding='utf-8')
    figmeta={}
    for n in sorted(artifacts):
        if n.endswith('.png'):
            with Image.open(fstage/n) as im:
                require(all(v>=299 for v in im.info['dpi']),'Insufficient DPI')
                figmeta[n]=dict(pixels=list(im.size),dpi=list(im.info['dpi']))
            with Image.open(fstage/n) as im:im.verify()
        elif n.endswith('.pdf'):require((fstage/n).read_bytes().startswith(b'%PDF'),'Invalid PDF figure')
        elif n.endswith('.svg'):require('<svg' in (fstage/n).read_text(encoding='utf-8'),'Invalid SVG figure')
    require(len(figmeta)==13 and len(artifacts)==39,'Unexpected refined figure count')
    for path in re.findall(r'!\[[^\]]*\]\(([^)]+)\)',body):
        require((rstage/path).resolve().is_file(),'QMD image reference missing: '+path)
    for name,table in tables.items():
        back=pd.read_csv(rstage/name,dtype={'geo_code':str,'excluded_geo_code':str},float_precision='round_trip')
        require(len(back)==len(table),'CSV row count changed')
        for f in ['geo_code','excluded_geo_code']:
            if f in table:require(back[f].tolist()==table[f].tolist(),'CSV string identifiers changed')
        for f in FEATURES:
            if f in table and pd.api.types.is_numeric_dtype(table[f]):
                require(np.allclose(back[f],table[f],rtol=0,atol=1e-13,equal_nan=True),'CSV data changed')
    print('Rendering standalone Quarto HTML...',flush=True)
    quartov,rendered=render_quarto(rstage)
    validation=dict(baseline_commit=atlas.BASELINE,branch='analysis/section-2-v2',source_validation=sourceval,geography=geoval,
                    primary_n=79,primary_pairwise_n_identical=True,contextual_coverage=[84,83,84],historical_income_year=2020,
                    independent_spearman_and_tau_b_checks=True,independent_skewness_check=True,correlation_leave_one_out=summary,
                    original_bivariate_classes_preserved=True,original_outputs_and_protected_hashes_unchanged=True,
                    tracked_files_unchanged=True,map_validation=mapvalid,figure_count_png=13,vector_versions=26,
                    figure_metadata=figmeta,csv_roundtrip=True,qmd_relative_figure_references=True,explorer=browserv,quarto=quartov)
    (rstage/'render_and_browser_validation.json').write_text(json_text(dict(explorer=browserv,quarto=quartov)),encoding='utf-8')
    # Remove no files from the user's workspace; ignore temporary Quarto support files in publication.
    allowed_reports=set(tables)|{'selected_comparison_observations.csv','correlation_sensitivity_summary.json','geographic_join_validation.json',
       'source_validation.json','classification_breaks.json','evidence_explorer.html','section2_enhanced.qmd','methods_results.md',
       'integration_ready_section2.md','quality_audit.md','figure_selection_recommendations.md','teammate_handover.md',
       'final_quality_review_checklist.md','render_and_browser_validation.json'}|{p.name for p in rendered}
    files={('reports/section2_enhanced/'+n):rstage/n for n in sorted(allowed_reports)}
    files.update({('figures/section2_enhanced/'+n):fstage/n for n in sorted(artifacts)})
    return files,validation,summary

def main():
    protected=protected_files();inputs=verify_existing()
    codehashes={relative(p):sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))}
    with tempfile.TemporaryDirectory(prefix='bremen-section2-enhanced-') as tmp:
        root=Path(tmp)
        print('Build 1 of 2: independent calculations, figures, explorer and report.',flush=True)
        first,valid1,summary=build(root/'run1',inputs,protected)
        hashes1={n:sha(p) for n,p in first.items()}
        print('Build 2 of 2: verifying byte-identical artifacts.',flush=True)
        second,valid2,_=build(root/'run2',inputs,protected)
        hashes2={n:sha(p) for n,p in second.items()}
        differences=[n for n in hashes1 if hashes1[n]!=hashes2.get(n)]
        require(set(first)==set(second) and not differences,'Non-deterministic outputs: '+str(differences))
        require(valid1==valid2,'Validation evidence changed between builds')
        if '--validate-only' in sys.argv:
            compared=[]
            for name,path in first.items():
                # Inventory/administrative metadata intentionally changes after
                # a normal commit. Scientific tables and figures must not.
                if name.endswith(('.csv','.png','.svg','.pdf')) and Path(name).name not in {'audit_findings.csv','preservation_inventory.csv'} and (ROOT/name).exists():
                    require(sha(ROOT/name)==sha(path),'Scientific artifact differs: '+name)
                    compared.append(name)
            require(protected=={n:sha(ROOT/n) for n in protected},'Existing file changed during validation')
            print(json_text(dict(status='PASS',mode='validate-only',baseline_commit=atlas.BASELINE,
                execution_commit=atlas.git('rev-parse','HEAD'),execution_branch=atlas.git('branch','--show-current'),
                deterministic_artifacts=len(first),scientific_artifacts_compared=len(compared),
                validation=valid1,existing_outputs_preserved=True)))
            return
        valid1['deterministic_pipeline_builds']=2;valid1['byte_identical_artifacts']=len(first)
        valid1['preserved_non_enhancement_file_count']=len(protected)
        validationpath=root/'enhancement_validation.json';validationpath.write_text(json_text(valid1),encoding='utf-8')
        first['reports/section2_enhanced/enhancement_validation.json']=validationpath
        manifest=dict(generator=relative(Path(__file__)),baseline_commit=atlas.BASELINE,
                      versions=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,scipy=scipy.__version__,matplotlib=matplotlib.__version__),
                      enhancement_source_hashes=codehashes,protected_input_hashes=protected,
                      outputs={n:sha(p) for n,p in sorted(first.items())},validation=valid1,
                      command='.\\.venv-section2\\Scripts\\python.exe -B src\\section2_enhanced\\build_enhancement.py')
        manifestpath=root/'reproducibility_manifest.json';manifestpath.write_text(json_text(manifest),encoding='utf-8')
        first['reports/section2_enhanced/reproducibility_manifest.json']=manifestpath
        for n,p in first.items():
            require(not (ROOT/n).exists() or sha(ROOT/n)==sha(p),'Refusing to overwrite existing enhancement output: '+n)
        require(protected=={n:sha(ROOT/n) for n in protected},'Pre-existing file changed before publication')
        require(codehashes=={n:sha(ROOT/n) for n in codehashes},'Enhancement code changed during execution')
        for n,p in first.items():
            target=ROOT/n;target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():
                with target.open('xb') as dest,p.open('rb') as src:shutil.copyfileobj(src,dest)
        require(protected=={n:sha(ROOT/n) for n in protected},'Pre-existing file changed after publication')
        require(not atlas.git('diff','--name-only','HEAD'),'Tracked files changed')
        require(all(sha(ROOT/n)==sha(p) for n,p in first.items()),'Published output mismatch')
    print('PASS: two byte-identical builds; sources and existing outputs unchanged.',flush=True)
    print(json_text(summary));print('Published new enhancement artifacts:',len(first),'plus',len(codehashes),'new scripts.')

if __name__=='__main__':
    # The entry point is completed below; --inspect-stats performs read-only recalculation.
    if '--inspect-stats' in sys.argv:
        args=verify_existing();master,complete,tables,summary=analyze(args[0],args[3],args[2],args[4])
        print(json_text(summary))
        for n in ['missingness_sensitivity.csv','contextual_associations_2024.csv','distribution_robustness.csv','correlation_robustness.csv']:
            print(n);print(tables[n].to_string(index=False))
    else:main()
