import hashlib
import json
import numpy as np
import pandas as pd
from prepare_data import process_excel, process_csv_files, process_json_catalog, build_excel_geography_lookup
from analysis_common import ROOT, YEAR, FEATURES, LABELS, DIRECTIONS, save_csv, write_doc

DEFINITIONS = [
    ('unemployment', 'Erwerbstätigkeit, Arbeitslosig', 'Anteil der Arbeitslosen an den sozialversicherungspflichtig Beschäftigten zuzüglich Arbeitslose (%)', 'primary',
     'Registered unemployed / (social-insurance employees + registered unemployed). Not the official all-civilian-labour-force unemployment rate.'),
    ('employment', 'Erwerbstätigkeit, Arbeitslosig', 'Anteil der sozialversicherungspflichtig Beschäftigten an der Bevölkerung im Alter von 15 bis unter 65 Jahren (%)', 'primary',
     'Social-insurance employees at residence / population aged 15 to under 65. Excludes self-employment and civil servants; low values are an imperfect labour-market disadvantage proxy.'),
    ('benefit_receipt', 'Sozialleistungen', 'Anteil der Leistungsberechtigten (Grundsicherung für Arbeitsuchende, SGB II) an der Bevölkerung unter 65 Jahren (%)', 'primary',
     'SGB II entitled recipients / population under 65. Measures receipt, not all poverty or unmet need; includes employed recipients.'),
    ('child_benefits', 'Sozialleistungen', 'Anteil der Leistungsberechtigten (Grundsicherung für Arbeitsuchende, SGB II) an der Bevölkerung unter 15 Jahren (%)', 'sensitivity',
     'SGB II entitled recipients under 15 / population under 15. Overlaps overall benefit receipt; not independent evidence.'),
    ('income_median', 'Lohn- und Einkommensteuer', 'Gesamtbetrag der Einkünfte je Steuerpflichtigen (1000 EUR): Median', 'historical_context',
     'Median total income per taxpayer, thousand EUR. Taxpayer unit differs from person/household; not disposable income. Latest year 2020.'),
    ('single_parents', 'Privathaushalte', 'Anteil der Alleinerziehenden an den Privathaushalten mit Hauptwohnsitz mit Kind(ern) (%)', 'context_only',
     'Single-parent households / main-residence households with children. Family structure is not intrinsic disadvantage; not scored.')]

LIMITATIONS = ('Workbook export has no exact reference-date, revision or complete boundary-history metadata. '
               'Same year is an annual comparison, not proof of an identical observation day. '
               'No causal or individual-level conclusions. Missing values are not imputed.')

def audit_sources():
    paths = sorted(ROOT.glob('ST*.csv')) + [ROOT / 'Datentabelle.xls', ROOT / 'bremen_data.json']
    manifest = [{'file': p.name, 'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]
    save_csv(pd.DataFrame(manifest), 'analysis/source_manifest.csv')
    excel, _, _ = process_excel(ROOT / 'Datentabelle.xls')
    workbook = pd.ExcelFile(ROOT / 'Datentabelle.xls')
    geography = build_excel_geography_lookup(workbook)
    csv_data, _, _ = process_csv_files(sorted(ROOT.glob('ST*.csv')), geography)
    catalogue, _ = process_json_catalog(ROOT / 'bremen_data.json')
    checks = []
    for fresh, filename in [(excel, 'excel_ortsteilatlas_long.csv'), (csv_data, 'csv_district_statistics_long.csv')]:
        existing = pd.read_csv(ROOT / 'data/processed' / filename, keep_default_na=False, low_memory=False)
        pd.testing.assert_frame_equal(existing.fillna('').astype(str).reset_index(drop=True),
                                      fresh.fillna('').astype(str).reset_index(drop=True), check_dtype=False)
        checks.append({'check': 'raw reconstruction equals existing processed output', 'source': filename,
                       'passed': True, 'records': len(fresh), 'missing': fresh.value.isna().sum()})
    checks.append({'check': 'JSON metadata records readable separately', 'source': 'bremen_data.json',
                   'passed': True, 'records': len(catalogue), 'missing': None})
    save_csv(pd.DataFrame(checks), 'analysis/source_audit.csv')
    # A verified name alias only; do not merge historical and newer statistical values.
    unresolved = csv_data[csv_data.geo_level == 'unknown'].copy()
    unresolved['resolved_geo_code'] = np.where(unresolved.geo_name.eq('Überseestadt'), '437', '')
    unresolved['workbook_geo_name'] = np.where(unresolved.geo_name.eq('Überseestadt'), 'Ueberseestadt', '')
    unresolved['decision'] = 'Name alias only; historical boundary compatibility not established'
    save_csv(unresolved, 'analysis/geographic_alias_audit.csv')
    return excel, geography

def run():
    excel, geography = audit_sources()
    ortsteile = geography[geography.geo_level == 'Ortsteil'][['geo_code', 'geo_name']].copy()
    assert ortsteile.geo_code.is_unique and ortsteile.geo_code.str.fullmatch(r'\d{3}').all()
    catalog, coverage, selected = [], [], []
    for key, sheet, german, role, definition in DEFINITIONS:
        rows = excel[(excel.geo_level == 'Ortsteil') & (excel.source_sheet == sheet) & (excel.indicator == german)].copy()
        assert len(rows) and not rows.duplicated(['geo_code', 'year', 'indicator_block']).any()
        assert rows.indicator_block.eq(1).all() and rows.year_start.eq(rows.year_end).all()
        expected_unit = '1000 EUR' if key == 'income_median' else '%'
        if key != 'income_median':
            assert rows.unit.eq('%').all()
            assert rows.value.dropna().between(0, 100).all()
        else:
            assert rows.value.dropna().ge(0).all()
        rows['feature'] = key
        rows['analysis_unit'] = expected_unit
        selected.append(rows)
        years = sorted(rows.year.unique())
        for year, group in rows.groupby('year'):
            covered = int(group.value.notna().sum())
            coverage.append({'feature': key, 'year': int(year), 'total_ortsteile': len(ortsteile),
                             'observed': covered, 'coverage_proportion': covered / len(ortsteile),
                             'missing': len(ortsteile) - covered, 'missing_rate': 1 - covered / len(ortsteile)})
        latest = rows[rows.year == max(years)]
        catalog.append({'feature': key, 'original_german_name': german, 'english_name': LABELS[key],
                        'source_file': 'Datentabelle.xls', 'source_sheet': sheet, 'indicator_block': 1,
                        'unit': expected_unit, 'original_inferred_unit': rows.unit.iloc[0], 'geo_level': 'Ortsteil',
                        'available_years': ';'.join(map(str, years)), 'latest_year': int(max(years)),
                        'latest_covered': int(latest.value.notna().sum()), 'total_ortsteile': len(ortsteile),
                        'latest_coverage_proportion': latest.value.notna().sum() / len(ortsteile),
                        'latest_missing_rate': latest.value.isna().mean(), 'role': role,
                        'disadvantage_direction': ('higher' if DIRECTIONS.get(key, 0) > 0 else 'lower') if key in DIRECTIONS else 'not_scored',
                        'definition': definition, 'comparability_limitations': LIMITATIONS})
    cat = pd.DataFrame(catalog)
    save_csv(cat, 'analysis/indicator_selection.csv')
    save_csv(cat, 'analysis/data_dictionary.csv')
    save_csv(pd.DataFrame(coverage), 'analysis/coverage_summary.csv')
    long = pd.concat(selected, ignore_index=True)
    save_csv(long, 'data/processed/selected_indicators_long.csv')
    primary = long[(long.feature.isin(FEATURES)) & (long.year == YEAR)]
    assert not primary.duplicated(['geo_code', 'year', 'feature']).any()
    wide = primary.pivot(index='geo_code', columns='feature', values='value').reset_index()
    frame = ortsteile.merge(wide, on='geo_code', how='left', validate='one_to_one')
    frame['year'] = YEAR
    frame['geo_level'] = 'Ortsteil'
    for f in FEATURES:
        frame[f + '_year'] = YEAR
        frame[f + '_unit'] = '%'
    frame['scoring_eligible'] = frame[FEATURES].notna().all(axis=1)
    frame['exclusion_reason'] = frame.apply(lambda r: ';'.join(f + ':missing' for f in FEATURES if pd.isna(r[f])), axis=1)
    assert frame.scoring_eligible.sum() / len(frame) >= .8, 'Coverage gate below 80%'
    assert len(FEATURES) >= 3
    save_csv(frame, 'data/processed/ortsteil_analysis_ready.csv')
    save_csv(frame[~frame.scoring_eligible], 'analysis/excluded_neighborhoods.csv')
    # Preserve synchronized historical observations, but block change claims without metadata.
    hist = long[long.feature.isin(FEATURES + ['income_median'])]
    panel = hist.pivot(index=['geo_code', 'geo_name', 'year'], columns='feature', values='value').reset_index()
    panel['boundary_compatibility_verified'] = False
    panel['definition_stability_verified'] = False
    save_csv(panel, 'data/processed/ortsteil_historical_observations.csv')
    income = panel[panel.year == 2020].copy()
    income['complete_four_indicators'] = income[FEATURES + ['income_median']].notna().all(axis=1)
    save_csv(income, 'data/processed/ortsteil_2020_income_context.csv')
    checks = {'at_least_three_defensible_indicators': True, 'unique_ortsteil_ids': True,
              'primary_one_reporting_year': True, 'units_and_ranges': True, 'coverage_at_least_80_percent': True,
              'same_export_geographic_schema': True, 'exact_reference_dates_verified': False,
              'historical_boundaries_and_definitions_verified': False,
              'primary_scoring_gate': 'PASS for exploratory annual cross-section; not validated for operational allocation',
              'historical_change_gate': 'BLOCKED: no validated time-stable boundary and definition crosswalk'}
    write_doc('analysis/validation_checks.json', json.dumps(checks, indent=2))
    write_doc('analysis/dataset_validation.md', f'''# Dataset validation

Primary reporting year: {YEAR}. Workbook geography contains {len(frame)} Ortsteile; {frame.scoring_eligible.sum()} have all three baseline indicators ({frame.scoring_eligible.mean():.1%}).
The 80% coverage gate is a declared pragmatic threshold, not a statistical guarantee. Exclusions remain explicit in the dataset and exclusion table.

PASS: raw reconstruction matches every stored observation, unique geographic IDs, three credible rate indicators, no aggregate rows, no duplicate geographic-year-feature records, percent units and [0,100] ranges, one reporting year, complete-case scoring with no imputation.
The current workbook schema provides defensible within-export geographic identity for this annual exploratory cross-section. No claim of equal within-year reference dates is made.

BLOCKED: longitudinal change estimates and historical rankings. Consistent names/codes do not prove unchanged boundaries or definitions. Historical observations are exported for review only. No mixed-year income value enters the 2024 score. The 2020 income context remains a separate annual table.

Nine or other excluded neighborhoods are listed in `excluded_neighborhoods.csv`; reasons for unavailable source values are unknown, not assumed suppression or zero. Small denominators and missingness may bias coverage. The baseline covers labour-market exclusion and benefit receipt, not all dimensions of socioeconomic disadvantage.

{LIMITATIONS}
'''.replace('Nine or other excluded neighborhoods', 'Excluded neighborhoods'))
    write_doc('analysis/indicator_audit.md', '''# Indicator audit and selection decisions

Six candidates are audited in indicator_selection.csv; per-year counts and missingness appear in coverage_summary.csv. Three enter the 2024 baseline: unemployment quotient (higher), social-insurance employment participation (lower), and SGB II receipt under 65 (higher). These measure related but distinct labour-market and material-support conditions. They are correlated; equal weights assign two-thirds of baseline weight to labour-market measures. Domain-balanced weights and indicator-removal scenarios test that decision.

Child benefit receipt is an optional sensitivity variable, not independent baseline evidence. Median taxable income is useful for 2020 context only. Single parenthood describes service needs but is not a defensible intrinsic disadvantage score. Age composition, nationality, migration status, car ownership, housing tenure and rent are not scored: their disadvantage direction is ambiguous or their populations/years are incompatible. School transition indicators need residence/denominator and reference-period checks before inclusion. No demographic identity is treated as deprivation.

Income unit inference in Phase 1 missed the parenthesized unit because the title ends with ': Median'; this analysis explicitly uses 1000 EUR from the original heading. Other six candidate units are verified against headings. Source headings establish denominators; exact observation dates and revisions remain unavailable.

All 24 sources were independently reread; source_audit.csv records equality against the existing cleaned statistical files. The JSON catalogue is separate. Historical CSVs are not joined to Excel measurements. Überseestadt / Ueberseestadt is a name alias for code 437, documented in geographic_alias_audit.csv; this does not establish historical compatibility. The official 2011 yearbook documents conversion of Handelshäfen to code 437 in 2009. Full boundary history remains unverified.

Sources and checked external context: see docs/source_notes.md. The latest municipal atlas web page could not be opened (403), so current detailed definitions were not silently assumed verified.
''')
    return frame

if __name__ == '__main__':
    print(run()[['geo_code', 'geo_name', 'scoring_eligible']].to_string(index=False))
