"""Reproduce Section 2 from existing observations; never rerun preparation.

Run from any directory: python src/analyze_section2.py
Only this script's unchanged, manifest-tracked outputs may be overwritten.
"""
from __future__ import annotations

import csv
import hashlib
import json
import platform
import re
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
from scipy.stats import spearmanr
import xlrd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed"
REPORT = ROOT / "reports/section2_data_indicator_analysis"
FIGURES = ROOT / "figures/section2"
YEAR = 2024
SOURCE = "Datentabelle.xls"
MANIFEST = REPORT / "reproducibility_manifest.json"
INDICATORS = [
    dict(id="unemployment_pct", sheet="Erwerbstätigkeit, Arbeitslosig",
         label="Anteil der Arbeitslosen an den sozialversicherungspflichtig Beschäftigten zuzüglich Arbeitslose (%)",
         english="Unemployed share of socially insured employees plus unemployed people",
         unit="%", stored_unit="%", expected_n=79,
         definition="100 × unemployed people / (socially insured employees + unemployed people).",
         direction="Higher values indicate greater labor-market disadvantage.",
         limitations="Denominator excludes other labor-force groups; not a general unemployment rate. Exact reference date and residence basis are not stated in the worksheet header.",
         recommendation="Economic disadvantage measure; retain alongside SGB II receipt, checking redundancy."),
    dict(id="sgb_ii_under65_pct", sheet="Sozialleistungen",
         label="Anteil der Leistungsberechtigten (Grundsicherung für Arbeitsuchende, SGB II) an der Bevölkerung unter 65 Jahren (%)",
         english="SGB II benefit recipients as a share of residents under 65",
         unit="%", stored_unit="%", expected_n=84,
         definition="100 × SGB II benefit recipients / population under 65, as described by the header.",
         direction="Higher values indicate greater benefit reliance and potential material disadvantage.",
         limitations="Not a comprehensive poverty rate. The header does not explicitly specify the numerator age restriction, reference date, eligibility details or non-take-up.",
         recommendation="Economic disadvantage measure; strongest direct material-disadvantage proxy in this shortlist, subject to definition verification."),
    dict(id="single_parent_pct", sheet="Privathaushalte",
         label="Anteil der Alleinerziehenden an den Privathaushalten mit Hauptwohnsitz mit Kind(ern) (%)",
         english="Single-parent share of main-residence private households with children",
         unit="%", stored_unit="%", expected_n=83,
         definition="Single-parent share among main-residence private households with children; denominator is households with children, not all households. An adjacent header defines children as unmarried, childless persons under 18; its applicability here needs confirmation.",
         direction="No intrinsic disadvantage direction; describes household composition and possible service needs.",
         limitations="Does not measure household income, resources or support. Household classification and reference date are not fully documented in the worksheet.",
         recommendation="Contextual indicator; do not classify single parents as disadvantaged solely on this measure."),
    dict(id="floor_area_m2_per_resident", sheet="Wohnungswesen I",
         label="Durchschnittliche Wohnfläche je Einwohner:innen in m2",
         english="Average residential floor area per resident",
         unit="m²/person", stored_unit="", expected_n=85,
         definition="Residential floor area per resident (m²/person), as described by the header; exact housing-stock and population universes are not stated.",
         direction="Lower values can indicate less space per resident; no unambiguous disadvantage direction.",
         limitations="Not affordability or household crowding. Vacancies and mismatched stock/population universes may affect the ratio, especially in small or industrial areas.",
         recommendation="Contextual housing indicator; inspect extreme ratios before substantive use."),
    dict(id="age65plus_pct", sheet="Altersstruktur I",
         label="Anteil der Bevölkerung ab 65 Jahren an der Gesamtbevölkerung (%)",
         english="Residents aged 65 or older as a share of the total population",
         unit="%", stored_unit="%", expected_n=84,
         definition="100 × residents aged 65 or older / total population.",
         direction="No intrinsic disadvantage direction; indicates age structure and possible service needs.",
         limitations="Age composition does not measure poverty, health, dependency or access to services. Exact population universe and reference date need documentation.",
         recommendation="Demographic context; never treat older age alone as disadvantage."),
]
IDS = [i["id"] for i in INDICATORS]
EXCLUDED = {"122", "124", "125", "271", "411", "424", "436", "444", "512"}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def clean(value) -> str:
    return re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()


def code(value) -> str:
    return str(int(value)) if isinstance(value, (int, float)) else clean(value)


def md_table(frame: pd.DataFrame) -> str:
    def cell(v):
        return (f"{v:.4f}" if isinstance(v, (float, np.floating)) else str(v)).replace("|", "\\|").replace("\n", " ")
    rows = [[cell(v) for v in frame.columns]] + [["---"] * len(frame.columns)]
    rows += [[cell(v) for v in row] for row in frame.itertuples(index=False, name=None)]
    return "\n".join("| " + " | ".join(row) + " |" for row in rows)


def select_and_verify():
    lookup = pd.read_csv(DATA / "geography_lookup.csv", dtype=str, keep_default_na=False)
    geo = lookup.loc[lookup.geo_level.eq("Ortsteil"), ["geo_code", "geo_name"]].copy()
    assert len(geo) == 88 and geo.geo_code.is_unique
    assert geo.geo_code.str.fullmatch(r"\d{3}").all()
    catalog = pd.read_csv(ROOT / "indicator_catalog.csv", dtype=str, keep_default_na=False)
    for indicator in INDICATORS:
        catalog_match = catalog.loc[
            catalog.source_file.eq(SOURCE) & catalog.source_section.eq(indicator["sheet"])
            & catalog.indicator.eq(indicator["label"]) & catalog.indicator_block.eq("1")]
        assert len(catalog_match) == 1
        assert catalog_match.iloc[0].unit == indicator["stored_unit"]
        assert str(YEAR) in catalog_match.iloc[0].years
    mapping = {(i["sheet"], i["label"]): i for i in INDICATORS}
    selected = []
    # A streaming reader retains only the 440 intended rows from the 95 MB file.
    with (DATA / "excel_ortsteilatlas_long.csv").open(encoding="utf-8", newline="") as f:
        for line, row in enumerate(csv.DictReader(f), start=2):
            indicator = mapping.get((row["source_sheet"], row["indicator"]))
            if indicator and row["geo_level"] == "Ortsteil" and row["year"] == str(YEAR):
                assert row["source_file"] == SOURCE
                assert row["indicator_block"] == "1"
                assert row["year_start"] == row["year_end"] == row["reporting_period"] == str(YEAR)
                assert row["unit"] == indicator["stored_unit"]
                assert row["value_status"] in {"ok", "missing"}
                assert (row["value"] == "") == (row["value_status"] == "missing")
                row.update(indicator_id=indicator["id"], processed_csv_line=line)
                selected.append(row)
    long = pd.DataFrame(selected)
    key = ["source_file", "source_sheet", "indicator", "indicator_block", "reporting_period", "geo_level", "geo_code"]
    assert len(long) == 440 and not long.duplicated(key).any()
    assert not long.duplicated(["indicator_id", "geo_code"]).any()
    book = xlrd.open_workbook(ROOT / SOURCE, on_demand=True)
    metadata = []
    for indicator in INDICATORS:
        part = long[long.indicator_id.eq(indicator["id"])]
        assert len(part) == 88 and set(part.geo_code) == set(geo.geo_code)
        sheet = book.sheet_by_name(indicator["sheet"])
        current = ""
        blocks = Counter()
        columns = []
        for col in range(2, sheet.ncols):
            header = clean(sheet.cell_value(1, col))
            if header:
                current = header
                blocks[current] += 1
            if current == indicator["label"] and blocks[current] == 1:
                if sheet.cell_value(2, col) in (YEAR, str(YEAR)):
                    columns.append(col)
        assert len(columns) == 1, (indicator["id"], columns)
        col = columns[0]
        raw_rows = {}
        for row in range(3, sheet.nrows):
            c = code(sheet.cell_value(row, 0))
            if c in set(geo.geo_code):
                assert c not in raw_rows
                raw_rows[c] = row
        assert set(raw_rows) == set(geo.geo_code)
        for idx, observation in part.iterrows():
            row = raw_rows[observation.geo_code]
            assert clean(sheet.cell_value(row, 1)) == observation.geo_name
            raw = sheet.cell_value(row, col)
            if observation.value_status == "missing":
                assert raw == "" and observation.raw_value == ""
            else:
                value = float(observation.value)
                assert np.isfinite(value) and value >= 0
                if indicator["unit"] == "%":
                    assert value <= 100
                assert isinstance(raw, (int, float)) and raw == value
                assert float(observation.raw_value) == value
            long.loc[idx, "workbook_row_1based"] = row + 1
            long.loc[idx, "workbook_column_1based"] = col + 1
            long.loc[idx, "workbook_value_verified"] = True
        assert (part.value_status == "ok").sum() == indicator["expected_n"]
        metadata.append({**indicator, "source_file": SOURCE, "indicator_block": 1,
                         "reporting_period": str(YEAR), "year_start": YEAR, "year_end": YEAR,
                         "geo_level": "Ortsteil", "represented_n": 88,
                         "valid_n": indicator["expected_n"],
                         "missing_n": 88 - indicator["expected_n"],
                         "missing_pct": (88 - indicator["expected_n"]) / 88 * 100,
                         "definition_evidence": "Original worksheet header; no additional definitions or footnotes in the five selected worksheets.",
                         "workbook_column_1based": col + 1,
                         "header_row_1based": 2, "period_row_1based": 3})
    book.release_resources()
    long["value"] = pd.to_numeric(long["value"], errors="raise")
    wide = long.pivot(index="geo_code", columns="indicator_id", values="value").reset_index()
    master = geo.merge(wide, on="geo_code", how="left", validate="one_to_one")
    master.insert(2, "reporting_year", YEAR)
    master = master[["geo_code", "geo_name", "reporting_year"] + IDS]
    master["complete_case"] = master[IDS].notna().all(axis=1)
    master["missing_indicator_count"] = master[IDS].isna().sum(axis=1)
    master["missing_indicators"] = master.apply(lambda r: ";".join(i for i in IDS if pd.isna(r[i])), axis=1)
    master = master.sort_values("geo_code").reset_index(drop=True)
    assert master.complete_case.sum() == 79
    assert set(master.loc[~master.complete_case, "geo_code"]) == EXCLUDED
    return master, long, pd.DataFrame(metadata)


def describe(master):
    result, checks = [], []
    for indicator in INDICATORS:
        ident = indicator["id"]
        valid = master.loc[master[ident].notna()]
        x = valid[ident]
        low, high = x.min(), x.max()
        p10, q1, q3, p90 = x.quantile([.1, .25, .75, .9], interpolation="linear")
        iqr = q3 - q1
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        result.append(dict(indicator_id=ident, unit=indicator["unit"], reporting_year=YEAR,
                           valid_n=len(x), missing_n=88-len(x), missing_pct=(88-len(x))/88*100,
                           minimum=low, minimum_neighborhoods="; ".join(valid.loc[x.eq(low), "geo_name"]),
                           maximum=high, maximum_neighborhoods="; ".join(valid.loc[x.eq(high), "geo_name"]),
                           mean=x.mean(), median=x.median(), sd_sample=x.std(ddof=1),
                           q1=q1, q3=q3, iqr=iqr, p10=p10, p90=p90,
                           max_minus_min=high-low, max_min_ratio=high/low if low>0 else np.nan,
                           max_vs_min_relative_pct=(high-low)/low*100 if low>0 else np.nan,
                           p90_minus_p10=p90-p10, p90_p10_ratio=p90/p10 if p10>0 else np.nan,
                           difference_unit="percentage points" if indicator["unit"]=="%" else "m²/person",
                           tukey_lower_fence=lower, tukey_upper_fence=upper,
                           tukey_outlier_n=int(((x<lower)|(x>upper)).sum())))
        for _, r in valid.iterrows():
            outlier = r[ident]<lower or r[ident]>upper
            if outlier or r[ident] in (low, high):
                checks.append(dict(indicator_id=ident, geo_code=r.geo_code, geo_name=r.geo_name,
                                   reporting_year=YEAR, value=r[ident], tukey_outlier=outlier,
                                   is_minimum=r[ident]==low, is_maximum=r[ident]==high,
                                   workbook_value_verified=True,
                                   action="Retained; matches original workbook. Source agreement does not establish substantive validity."))
    stats = pd.DataFrame(result)
    assert stats.valid_n.tolist() == [79,84,83,85,84]
    pair = master.dropna(subset=IDS[:2])
    rho, p = spearmanr(pair[IDS[0]], pair[IDS[1]])
    assert len(pair) == 79 and np.isfinite(rho)
    # Independent check: Spearman equals Pearson correlation of average ranks.
    assert np.isclose(rho, pair[IDS[:2]].rank(method="average").corr().iloc[0,1])
    correlation = dict(reporting_year=YEAR, geo_level="Ortsteil", sample="Pairwise observed unemployment and SGB II; equals five-indicator complete sample",
                       n=len(pair), spearman_rho=float(rho), p_value_asymptotic_two_sided=float(p),
                       caveat="Descriptive ecological association; no causality. Asymptotic p assumes independent observations and is not spatially adjusted; treat as supplementary.")
    return stats, pd.DataFrame(checks), correlation


def figures(master, correlation):
    plt.rcParams.update({"font.family":"DejaVu Sans", "font.size":10,
                         "axes.spines.top":False, "axes.spines.right":False,
                         "savefig.dpi":300})
    source = "Source: Datentabelle.xls; existing excel_ortsteilatlas_long.csv; original workbook cells verified."
    pair = master.dropna(subset=IDS[:2]).sort_values([IDS[0], "geo_code"])
    fig, ax = plt.subplots(figsize=(11, 19))
    y = np.arange(len(pair))
    ax.hlines(y, pair[IDS[0]], pair[IDS[1]], color="#cbd5e1", linewidth=1)
    ax.scatter(pair[IDS[0]], y, color="#176b91", label="Unemployed / (insured employees + unemployed)", s=27, zorder=3)
    ax.scatter(pair[IDS[1]], y, color="#bd5938", marker="D", label="SGB II recipients / population under 65", s=22, zorder=3)
    ax.set_yticks(y, pair.geo_name + " (" + pair.geo_code + ")", fontsize=8)
    ax.set(xlabel="Rate (%) — distinct denominators", ylim=(-1,len(pair)), xlim=(0,None))
    ax.grid(axis="x", alpha=.2)
    ax.set_title("Unemployment and SGB II receipt across Bremen neighborhoods\n2024 · Ortsteil · n = 79 with both rates", loc="left", pad=18)
    ax.legend(loc="lower right", frameon=True, fontsize=9)
    fig.subplots_adjust(left=.30,right=.97,top=.94,bottom=.06)
    fig.text(.03,.015,source+"\nOrdered by unemployment rate; nine Ortsteile lack that rate. Separate measures, no composite score.",fontsize=8)
    fig.savefig(FIGURES / "figure1_neighborhood_rates.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8,6))
    ax.scatter(pair[IDS[0]],pair[IDS[1]],s=42,color="#176b91",alpha=.8,edgecolor="white",linewidth=.5)
    for idx in {pair[IDS[0]].idxmin(),pair[IDS[0]].idxmax(),pair[IDS[1]].idxmax()}:
        r=pair.loc[idx]
        high = r[IDS[0]] == pair[IDS[0]].max()
        ax.annotate(r.geo_name,(r[IDS[0]],r[IDS[1]]),xytext=(-5 if high else 5,5),
                    ha="right" if high else "left", textcoords="offset points",fontsize=8)
    ax.set(xlabel="Unemployed / (insured employees + unemployed) (%)",
           ylabel="SGB II recipients / population under 65 (%)")
    ax.set_title(f"Unemployment and SGB II receipt\n2024 · Ortsteil · Spearman ρ = {correlation['spearman_rho']:.3f} · n = {len(pair)}",loc="left")
    ax.grid(alpha=.18)
    fig.subplots_adjust(left=.12,right=.97,top=.84,bottom=.21)
    fig.text(.04,.035,source+"\nWorksheets: Erwerbstätigkeit, Arbeitslosig; Sozialleistungen.\nPairwise observed values; neighborhood association does not imply causation.",fontsize=8)
    fig.savefig(FIGURES / "figure2_unemployment_sgbii_scatter.png")
    plt.close(fig)

    fig, axes = plt.subplots(1,3,figsize=(13,5))
    titles=["Single-parent households","Residential floor area","Population aged 65+"]
    xlabels=["Share of households with children (%)","Floor area per resident (m²/person)","Share of total population (%)"]
    for ax, ident,title,xlabel in zip(axes,IDS[2:],titles,xlabels):
        x=master[ident].dropna()
        ax.hist(x,bins="fd",color="#176b91",edgecolor="white",alpha=.85)
        ax.axvline(x.median(),color="#bd5938",linestyle="--",label=f"Median = {x.median():.2f}")
        ax.set(title=f"{title}\nn = {len(x)}; missing = {88-len(x)}",xlabel=xlabel,ylabel="Ortsteile (count)")
        ax.legend(fontsize=8)
        ax.grid(axis="y",alpha=.15)
    fig.suptitle("Bremen neighborhood distributions · 2024 · Ortsteil",x=.06,ha="left",fontsize=14)
    fig.subplots_adjust(left=.06,right=.98,wspace=.35,top=.79,bottom=.27)
    fig.text(.04,.035,source+"\nWorksheets: Privathaushalte; Wohnungswesen I; Altersstruktur I. Each panel uses all valid observations.\nSeparate axes; full observed ranges retained, including extreme floor-area values.",fontsize=8)
    fig.savefig(FIGURES / "figure3_context_distributions.png")
    plt.close(fig)


def main():
    inputs=[ROOT/SOURCE, DATA/"excel_ortsteilatlas_long.csv", DATA/"geography_lookup.csv",
            ROOT/"indicator_catalog.csv", ROOT/"data_quality_report.md", DATA/"validation_summary.csv", ROOT/"src/prepare_data.py"]
    hashes={str(p.relative_to(ROOT)):digest(p) for p in inputs}
    output_paths=[DATA/"section2_2024_ortsteil_analysis.csv", DATA/"section2_indicator_metadata.csv",
                  DATA/"section2_selected_observation_provenance.csv", REPORT/"descriptive_statistics.csv",
                  REPORT/"complete_case_descriptive_statistics.csv", REPORT/"excluded_ortsteile.csv",
                  REPORT/"outlier_source_checks.csv", REPORT/"indicator_assessment.csv",
                  REPORT/"correlation_results.json", REPORT/"methods_results.md",
                  FIGURES/"figure1_neighborhood_rates.png", FIGURES/"figure2_unemployment_sgbii_scatter.png",
                  FIGURES/"figure3_context_distributions.png"]
    previous=json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    for path in output_paths:
        if path.exists():
            assert previous.get("generator")=="src/analyze_section2.py"
            assert previous.get("outputs",{}).get(str(path.relative_to(ROOT)))==digest(path), f"Refusing to overwrite untracked or edited output: {path}"
    master,long,metadata=select_and_verify()
    stats,outliers,correlation=describe(master)
    for path in [DATA,REPORT,FIGURES]:path.mkdir(parents=True,exist_ok=True)
    master.to_csv(output_paths[0],index=False,encoding="utf-8",na_rep="")
    metadata.to_csv(output_paths[1],index=False,encoding="utf-8")
    long.to_csv(output_paths[2],index=False,encoding="utf-8",na_rep="")
    stats.to_csv(REPORT/"descriptive_statistics.csv",index=False)
    complete=master[master.complete_case]
    cc=[]
    for ident in IDS:
        x=complete[ident]
        cc.append(dict(indicator_id=ident,n=len(x),mean=x.mean(),median=x.median(),minimum=x.min(),maximum=x.max(),sd_sample=x.std(ddof=1)))
    pd.DataFrame(cc).to_csv(REPORT/"complete_case_descriptive_statistics.csv",index=False)
    excluded=master.loc[~master.complete_case,["geo_code","geo_name","missing_indicator_count","missing_indicators"]]
    excluded.to_csv(REPORT/"excluded_ortsteile.csv",index=False)
    provenance_columns=["indicator_id","geo_code","workbook_row_1based","workbook_column_1based","raw_value"]
    outliers=outliers.merge(long[provenance_columns],on=["indicator_id","geo_code"],validate="one_to_one")
    outliers.to_csv(REPORT/"outlier_source_checks.csv",index=False)
    metadata.to_csv(REPORT/"indicator_assessment.csv",index=False,encoding="utf-8")
    (REPORT/"correlation_results.json").write_text(json.dumps(correlation,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    figures(master,correlation)
    findings=[]
    for row in stats.itertuples():
        findings.append(f"- **{row.indicator_id}**: {row.minimum:.4f} ({row.minimum_neighborhoods}) to {row.maximum:.4f} ({row.maximum_neighborhoods}); gap {row.max_minus_min:.4f} {row.difference_unit}; maximum/minimum {row.max_min_ratio:.4f}×. Mean {row.mean:.4f}, median {row.median:.4f}.")
    note=f"""# Section 2 — Data and Indicator Analysis

Generated by `src/analyze_section2.py`. This analysis addresses RQ1 (neighborhood differences) and RQ2 (indicator usefulness) without composite indices, clustering or causal claims.

## Selection and source validation

Primary comparison: 2024, Ortsteil. The existing long CSV is streamed; only 440 rows are retained. Exact worksheet, German label, indicator_block=1, unit and reporting_period=2024 are asserted. year_start=year_end=2024 excludes pooled periods. Geography codes remain strings. All five worksheets were opened with xlrd and all 440 values/blank cells, names and codes were matched to original workbook cells. All 415 numeric values agree exactly. The intended source/worksheet/label/block/period/level/code key is unique; there are no invalid statuses, nonfinite values, negative values or percentages outside [0,100] in the selected observations. Missing cells remain missing, never zero.

The initial audit's 79 complete cases are confirmed. The master table retains all 88 represented Ortsteile; 79 have all five indicators. This is file coverage, not an independent verification of administrative completeness. No city, Stadtbezirk or Stadtteil aggregates enter the analysis. 2025 election and pooled health observations are excluded.

Definitions below are based on literal workbook headers, not an external source manual. The five worksheets contain title/header/year rows and 112 geography rows, without additional explanatory footnotes. Exact reference dates, universe definitions, suppression rules and boundary history remain unresolved. Floor area's processed unit is blank; m²/person is recovered explicitly from its German header and documented, without changing source data.

## Statistical methods

Descriptive statistics use every observed Ortsteil value for each indicator (available-case analysis). Means and medians describe equally weighted neighborhoods, not resident-weighted city averages. Standard deviation uses ddof=1. Quartiles and percentiles use linear interpolation; IQR=Q3−Q1. Absolute high/low differences are max−min and P90−P10, expressed in percentage points for shares and m²/person for floor area. Relative differences are max/min and 100×(max−min)/min where min>0; they are contrasts in the measure, not differences in individual disadvantage. Full precision is retained in CSV outputs. An additional complete-case descriptive table makes sample dependence inspectable.

Spearman correlation uses the 79 Ortsteile observed on both economic indicators, which coincide with the five-indicator complete sample. Average ranks account for ties. The result is checked independently using Pearson correlation of average ranks. No linear model or causal effect is estimated.

## RQ1: observed differences

{chr(10).join(findings)}

{md_table(stats[['indicator_id','valid_n','missing_pct','mean','median','sd_sample','iqr','p10','p90']])}

Unemployment and SGB II receipt have Spearman rho **{correlation['spearman_rho']:.6f}**, **n={correlation['n']}**. The supplementary two-sided asymptotic p-value is {correlation['p_value_asymptotic_two_sided']:.6g}. This is an ecological cross-sectional association: shared economic conditions, overlapping populations and demographic composition may contribute. No causation is established. These represented neighborhoods are not a random sample; spatial dependence and source uncertainty are not modeled, and the p-value assumes independence. It does not establish external validity or an independent disadvantage criterion.

## Missingness and exclusions

{md_table(excluded)}

Missingness is geographically concentrated rather than assumed random. Each exclusion reflects at least missing unemployment; other missing indicators are listed explicitly. Excluded places can still contribute valid values to available-case descriptive summaries. No imputation or automatic deletion of extreme observations was performed.

## Outlier investigation

Tukey flags use values below Q1−1.5×IQR or above Q3+1.5×IQR, separately for each indicator. Flags are diagnostic, not errors. Every flagged value and every observed minimum/maximum was verified against the original workbook; coordinates and raw values are in `outlier_source_checks.csv`. All are retained. A workbook match verifies transcription only: unusual housing ratios may still reflect stock/population denominator differences, vacancy or small populations, which cannot be resolved from these headers. No robust or spatial uncertainty estimates are asserted.

{md_table(stats[['indicator_id','tukey_outlier_n','tukey_lower_fence','tukey_upper_fence']])}

## RQ2: usefulness assessment

Unemployment and SGB II receipt are the two measures with a defensible directional relationship to economic disadvantage. Their observed dispersion distinguishes neighborhoods, but the strong association indicates potential redundancy, not independent validation. SGB II has broader geographic completeness than unemployment. A judgment that one is more predictive cannot be made without an external criterion or outcome. Single-parent prevalence, floor area and older-age prevalence provide context; none automatically establishes disadvantage. Age, migration background and single-parent status should not be treated as deprivation by themselves.

The accompanying `indicator_assessment.csv` records exact German labels, English translations, header-based definitions and denominators, source worksheets, blocks, units, years, coverage, missingness, direction, limitations and use recommendations. Economic measures should be presented separately with contextual measures and explicit denominators.

## Figures and limitations

The revised figures are generated separately by `python src/refine_section2_figures.py` from the preserved validated dataset and stored correlation. This script never overwrites original figures or recalculates descriptive statistics.

**Main-report Figure 1** (`figures/section2/figure1_compact_extreme_unemployment_2024.png`) shows the five Ortsteile with the highest and five with the lowest observed unemployment values among the 79 neighborhoods with both economic indicators. Selection is solely by unemployment, with geographic code as a deterministic secondary sort; no boundary ties occur. Both unemployment (unemployed / socially insured employees plus unemployed) and SGB II receipt (recipients / population under 65) are shown as percentages with distinct denominators. This deliberately selected subset illustrates observed contrasts and is not representative of all neighborhoods. The original full comparison, `figures/section2/figure1_neighborhood_rates.png`, remains unchanged as **supplementary Figure S1**, showing all 79 pairwise-observed Ortsteile.

**Revised Figure 2** (`figures/section2/figure2_scatter_revised_annotation_2024.png`) retains the exact same 79 point coordinates and stored Spearman coefficient; only annotation placement and coefficient display are refined. Seehausen has an offset label and leader line. The original `figure2_unemployment_sgbii_scatter.png` is preserved. The association remains descriptive and does not imply causation.

**Revised Figure 3** (`figures/section2/figure3_context_distributions_revised_caption_2024.png`) preserves the original observed values, histogram bins, axes and scales, with available cases separately (83, 85 and 84). Caption: household composition, housing space and age structure are contextual indicators, not direct measures of deprivation. Neither single-parent status nor older age automatically implies disadvantage. The original `figure3_context_distributions.png` is preserved.

All original and revised PNGs are 300 dpi and include 2024, Ortsteil, measurement units and source information. `visualization_refinement_manifest.json` records the compact subset, revised output hashes and plotting validations; statistical findings above are unchanged.

Additional audit cautions: indicator_block cannot be dropped globally because business counts repeat across four blocks. The catalog's geographic coverage is hard-coded and year spans do not imply completeness. Two nonselected Strom foreign-resident SGB II rates exceed 100% in 2022; they do not enter this analysis. Older CSV snapshots are not mixed with 2024 workbook observations. Their Überseestadt/Ueberseestadt mismatch remains a separate preparation issue. No raw data or `src/prepare_data.py` is changed.

## Reproduction and validation

From the repository root:

```powershell
python -m venv --system-site-packages .venv-section2
.\\.venv-section2\\Scripts\\python.exe -m pip install -r requirements-section2.txt
.\\.venv-section2\\Scripts\\python.exe src/analyze_section2.py
```

For a clean environment omit `--system-site-packages` and install the same requirements. xlrd>=2.0 was already declared in requirements.txt; xlrd 2.0.2 was installed locally because it was absent. The first two restricted pip attempts found no package; an approved network-enabled attempt succeeded. No dependencies were upgraded in the shared environment. All statistical and workbook assertions passed. Output reload assertions verify 88 string-coded rows, 79 complete cases and preserved numeric values. Input SHA-256 hashes are checked before/after execution, and the manifest records input/output hashes and runtime versions. Reruns refuse to overwrite untracked or edited outputs, protecting other contributors' work.

Next steps: obtain the official source-definition manual and reference dates; clarify floor-area numerator/denominator coverage and extreme ratios; document geographic boundaries and missingness conventions; use external outcomes to assess predictive usefulness if required. Section 4 methods are outside this script.
"""
    (REPORT/"methods_results.md").write_text(note,encoding="utf-8")
    reloaded=pd.read_csv(output_paths[0],dtype={"geo_code":str})
    assert len(reloaded)==88 and reloaded.geo_code.equals(master.geo_code)
    assert reloaded.complete_case.sum()==79
    np.testing.assert_allclose(reloaded[IDS].to_numpy(),master[IDS].to_numpy(),equal_nan=True)
    assert hashes=={str(p.relative_to(ROOT)):digest(p) for p in inputs}, "An original input changed during execution"
    manifest=dict(generator="src/analyze_section2.py", inputs=hashes,
                  script_sha256=digest(Path(__file__)),
                  versions=dict(python=platform.python_version(),pandas=pd.__version__,numpy=np.__version__,scipy=scipy.__version__,matplotlib=matplotlib.__version__,xlrd=xlrd.__version__),
                  validation=dict(selected_rows=440,numeric_cells_verified=415,missing_cells_verified=25,duplicate_keys=0,invalid_selected_values=0,represented_ortsteile=88,complete_cases=79,inputs_unchanged=True),
                  outputs={str(p.relative_to(ROOT)):digest(p) for p in output_paths})
    MANIFEST.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(stats[["indicator_id","valid_n","minimum","minimum_neighborhoods","maximum","maximum_neighborhoods","mean","median","sd_sample","iqr","p10","p90"]].to_string(index=False))
    print(json.dumps(correlation,indent=2))
    print("PASS: workbook, keys, ranges, missingness, correlation, output reload and unchanged-input assertions.")


if __name__ == "__main__":
    main()
