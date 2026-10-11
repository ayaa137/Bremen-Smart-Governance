"""Independent Section 2 V2 evidence from the shared 20b79ae baseline.

Run with Python -B. Only new V2 files are created; existing files are never
overwritten. Identical reruns validate outputs without writing them again.
No composite indices, disadvantage rankings, clustering or architecture.
"""
from __future__ import annotations

import hashlib
import json
import math
import platform
import subprocess
import tempfile
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

from analysis_common import ROOT, YEAR, FEATURES

REPORT = ROOT / "reports/section2_v2"
FIGURES = ROOT / "figures/section2_v2"
BASELINE = "20b79ae817c5d7c7b80e1d93c79d415d47037be7"
ALL_FEATURES = FEATURES + ["child_benefits", "single_parents", "income_median"]
EXPECTED_VALID = dict(unemployment=79, employment=79, benefit_receipt=84,
                      child_benefits=84, single_parents=83, income_median=84)
EXCLUDED = {"122", "124", "125", "271", "411", "424", "436", "444", "512"}
LABELS = {"unemployment": "Unemployment quotient", "employment": "Social-insurance employment participation",
          "benefit_receipt": "SGB II receipt: population under 65",
          "child_benefits": "SGB II receipt: population under 15",
          "single_parents": "Single-parent households", "income_median": "Median total income per taxpayer"}
AXIS_LABELS = {"unemployment": "Unemployed / (insured employees\n+ unemployed) (%)",
               "employment": "Insured employees / population\naged 15–<65 (%)",
               "benefit_receipt": "SGB II recipients / population\nunder 65 (%)"}
SOURCE = "Source: supplied Datentabelle.xls; shared ortsteil_analysis_ready.csv and selected_indicators_long.csv."


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def git(*args):
    return subprocess.check_output(["git", "--no-pager", *args], cwd=ROOT, timeout=30).decode("utf-8").strip()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def relative(path):
    return Path(path).relative_to(ROOT).as_posix()


def protected_files():
    output = subprocess.check_output(["git", "--no-pager", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT)
    names = {n.decode("utf-8") for n in output.split(b"\0") if n}
    return {n: sha(ROOT / n) for n in sorted(names)
            if not n.startswith(("reports/section2_v2/", "figures/section2_v2/")) and (ROOT/n).is_file()}


def read_csv(name, numeric=True):
    return pd.read_csv(ROOT/name, encoding="utf-8-sig", dtype={"geo_code": str}, keep_default_na=numeric,
                       float_precision="round_trip")


def md(frame):
    def cell(v):
        if pd.isna(v):
            return "—"
        if isinstance(v, (float, np.floating)):
            return f"{v:.4f}"
        return str(v).replace("|", "\\|").replace("\n", " ")
    rows = [list(frame.columns), ["---"] * len(frame.columns)]
    rows += [[cell(v) for v in row] for row in frame.itertuples(index=False, name=None)]
    return "\n".join("| " + " | ".join(map(str, row)) + " |" for row in rows)


def load_validate(validate_git=True):
    # The original entry point retains its historical Git guard. The enhanced
    # workflow verifies immutable inputs independently and supports descendants
    # of the baseline without pretending their HEAD is the original commit.
    if validate_git:
        require(git("branch", "--show-current") == "analysis/section-2-v2", "Wrong branch")
        require(git("rev-parse", "HEAD") == git("rev-parse", "origin/main") == BASELINE, "Baseline differs from approved fetched main")
        require(git("diff", "--name-only", "HEAD") == "", "Tracked teammate files have edits")
    require(YEAR == 2024 and FEATURES == ["unemployment", "employment", "benefit_receipt"], "Shared configuration changed")
    frame = read_csv("data/processed/ortsteil_analysis_ready.csv")
    definitions = read_csv("analysis/indicator_selection.csv", numeric=False)
    dictionary = read_csv("analysis/data_dictionary.csv", numeric=False)
    pd.testing.assert_frame_equal(definitions, dictionary)
    require(set(definitions.feature) == set(ALL_FEATURES) and definitions.feature.is_unique, "Definition catalog mismatch")
    long = read_csv("data/processed/selected_indicators_long.csv")
    require(len(frame) == 88 and frame.geo_code.is_unique and frame.geo_code.str.fullmatch(r"\d{3}").all(), "Master geographic keys invalid")
    require(frame.geo_level.eq("Ortsteil").all() and frame.year.eq(YEAR).all(), "Wrong level/year")
    lookup = read_csv("data/processed/geography_lookup.csv", numeric=False)
    geo = lookup[lookup.geo_level.eq("Ortsteil")][["geo_code", "geo_name"]].sort_values("geo_code").reset_index(drop=True)
    pd.testing.assert_frame_equal(frame[["geo_code", "geo_name"]].sort_values("geo_code").reset_index(drop=True), geo)
    require(not long.duplicated(["geo_code", "year", "feature"]).any(), "Duplicate selected keys")
    require(len(long) == 9152 and set(long.feature) == set(ALL_FEATURES), "Selected input schema/coverage changed")
    require(long.geo_level.eq("Ortsteil").all() and long.indicator_block.eq(1).all(), "Invalid selected level/block")
    require(long.year.eq(long.year_start).all() and long.year.eq(long.year_end).all(), "Pooled period in selected observations")
    require(pd.to_numeric(long.reporting_period).eq(long.year).all(), "Reporting period mismatch")
    require(set(long.value_status) <= {"ok", "missing"}, "Invalid or suppressed selected values")
    require(long.value.notna().equals(long.value_status.eq("ok")), "Value/status mismatch")
    require(long.raw_value.isna().equals(long.value.isna()), "Raw/parsed missingness mismatch")
    require(np.allclose(pd.to_numeric(long.loc[long.value.notna(), "raw_value"]), long.loc[long.value.notna(), "value"], rtol=0, atol=1e-12), "Raw/parsed numbers mismatch")
    require(np.isfinite(long.value.dropna()).all() and long.value.dropna().ge(0).all(), "Invalid selected number")
    require(long.loc[~long.feature.eq("income_median"), "value"].dropna().le(100).all(), "Invalid percentage")
    book = xlrd.open_workbook(ROOT/"Datentabelle.xls", on_demand=True)
    workbook_coordinates = {}
    for d in definitions.itertuples(index=False):
        observations = long[long.feature.eq(d.feature)]
        require(observations.source_file.eq(d.source_file).all() and observations.source_sheet.eq(d.source_sheet).all()
                and observations.indicator.eq(d.original_german_name).all(), "Exact source definition mismatch")
        require(observations.analysis_unit.eq(d.unit).all(), "Analysis unit mismatch")
        require(observations.unit.fillna("").eq(d.original_inferred_unit).all(), "Stored source unit mismatch")
        require(int(d.indicator_block) == 1 and d.geo_level == "Ortsteil", "Catalog block/level mismatch")
        sheet = book.sheet_by_name(d.source_sheet)
        current, blocks = "", Counter()
        original = {}
        for col in range(2, sheet.ncols):
            text = " ".join(str(sheet.cell_value(1, col)).split())
            if text:
                current = text
                blocks[text] += 1
            if current != d.original_german_name or blocks[current] != 1:
                continue
            year = int(sheet.cell_value(2, col))
            for row in range(3, sheet.nrows):
                c = sheet.cell_value(row, 0)
                c = str(int(c)) if isinstance(c, (int, float)) and c else str(c).strip()
                if c not in set(frame.geo_code):
                    continue
                value = sheet.cell_value(row, col)
                original[(c, year)] = (np.nan if value == "" else float(value), row+1, col+1,
                                       " ".join(str(sheet.cell_value(row, 1)).split()))
        require(len(original) == len(observations), "Workbook selection cardinality mismatch")
        for r in observations.itertuples(index=False):
            value, row, col, name = original[(r.geo_code, r.year)]
            require(name == r.geo_name, "Workbook geographic name mismatch")
            require((pd.isna(value) and pd.isna(r.value)) or value == r.value, "Workbook cell mismatch")
            workbook_coordinates[(r.geo_code, int(r.year), d.feature)] = (row, col)
    book.release_resources()
    require(len(workbook_coordinates) == 9152, "Wrong verified-cell count")
    for feature in FEATURES:
        require(frame[feature+"_year"].eq(YEAR).all() and frame[feature+"_unit"].eq("%").all(), "Primary metadata mismatch")
        rows = long[long.feature.eq(feature) & long.year.eq(YEAR)].set_index("geo_code")
        require(len(rows) == 88 and set(rows.index) == set(frame.geo_code), "Primary provenance coverage mismatch")
        require(np.allclose(frame[feature], frame.geo_code.map(rows.value), rtol=0, atol=0, equal_nan=True), "Primary values differ from provenance")
    eligible = frame[FEATURES].notna().all(axis=1)
    require(frame.scoring_eligible.equals(eligible), "Eligibility flag mismatch")
    require(int(eligible.sum()) == 79 and set(frame.loc[~eligible, "geo_code"]) == EXCLUDED, "Unexpected exclusions")
    expected_reason = frame.apply(lambda r: ";".join(f+":missing" for f in FEATURES if pd.isna(r[f])), axis=1)
    require(frame.exclusion_reason.fillna("").equals(expected_reason), "Exclusion reason mismatch")
    supplementary = {}
    for feature in ["child_benefits", "single_parents", "income_median"]:
        year = 2020 if feature == "income_median" else YEAR
        s = long[long.feature.eq(feature) & long.year.eq(year)][["geo_code", "geo_name", "value"]].copy()
        require(len(s) == 88 and s.geo_code.is_unique, "Context coverage mismatch")
        s["year"] = year
        supplementary[feature] = s
    for feature in ALL_FEATURES:
        count = frame[feature].notna().sum() if feature in FEATURES else supplementary[feature].value.notna().sum()
        require(count == EXPECTED_VALID[feature], "Unexpected observed coverage")
    with (ROOT/"analysis/source_manifest.csv").open(encoding="utf-8-sig") as f:
        source_manifest = pd.read_csv(f)
    require(len(source_manifest) == 24 and all(sha(ROOT/r.file) == r.sha256 for r in source_manifest.itertuples()), "Shared source hash mismatch")
    validation = dict(branch=git("branch", "--show-current"), commit=BASELINE, reporting_year=YEAR,
                      geographic_level="Ortsteil", master_rows=88, complete_rows=79,
                      selected_rows=9152, workbook_cells_verified=9152, duplicate_keys=0,
                      invalid_selected_values=0, source_hashes_verified=24,
                      input_schemas={"master":list(frame.columns),"selected_long":list(long.columns),"definitions":list(definitions.columns)},
                      guide_status="The specifically titled five-page Section 2 Guide was not located; implementation follows the user's pasted requirements and shared project documents.",
                      exact_reference_dates_verified=False, historical_comparability_verified=False)
    return frame.sort_values("geo_code").reset_index(drop=True), long, definitions, supplementary, workbook_coordinates, validation


def statistics(frame, features, sample, master_n=88, year=YEAR):
    rows = []
    for feature in features:
        valid = frame[frame[feature].notna()]
        x = valid[feature]
        q1, q3 = x.quantile([.25, .75], interpolation="linear")
        rows.append(dict(feature=feature, sample=sample, year=year,
                         unit="1000 EUR" if feature=="income_median" else "%", sample_n=len(frame),
                         valid_n=len(x), missing_n=len(frame)-len(x), missing_pct=(len(frame)-len(x))/len(frame)*100,
                         represented_master_n=master_n, mean=x.mean(), median=x.median(),
                         minimum=x.min(), minimum_names="; ".join(valid.loc[x.eq(x.min()),"geo_name"]),
                         maximum=x.max(), maximum_names="; ".join(valid.loc[x.eq(x.max()),"geo_name"]),
                         sd_sample=x.std(ddof=1), q1=q1,q3=q3,iqr=q3-q1,
                         p10=x.quantile(.1),p90=x.quantile(.9),range=x.max()-x.min(),
                         range_unit="1000 EUR" if feature=="income_median" else "percentage points"))
    return pd.DataFrame(rows)


def correlations(complete):
    rows = []
    for i, first in enumerate(FEATURES):
        for second in FEATURES[i+1:]:
            rho = float(spearmanr(complete[first],complete[second]).statistic)
            independent = complete[[first,second]].rank(method="average").corr().iloc[0,1]
            require(np.isclose(rho,independent,rtol=0,atol=1e-14), "Independent rank-correlation check failed")
            rows.append(dict(first=first,second=second,n=len(complete),year=YEAR,spearman_rho=rho,
                             first_tied_values=len(complete)-complete[first].nunique(),second_tied_values=len(complete)-complete[second].nunique(),
                             interpretation="Raw indicator directions; descriptive ecological association, not causation or measurement agreement."))
    return pd.DataFrame(rows)


def quadrants(complete):
    xmed, ymed = complete.unemployment.median(),complete.benefit_receipt.median()
    frame = complete[["geo_code","geo_name","year","unemployment","benefit_receipt"]].copy()
    side = lambda s,m:np.where(s>m,"above",np.where(s<m,"below","equal"))
    frame["unemployment_side"] = side(frame.unemployment,xmed)
    frame["benefit_side"] = side(frame.benefit_receipt,ymed)
    frame["agreement_group"] = np.where((frame.unemployment_side=="equal")|(frame.benefit_side=="equal"),"median boundary",
        np.where(frame.unemployment_side==frame.benefit_side,"same side of both medians","opposite sides of medians"))
    frame["quadrant"] = frame.unemployment_side + " unemployment / " + frame.benefit_side + " SGB II"
    nonboundary = frame[frame.agreement_group.ne("median boundary")]
    summary = frame.groupby(["quadrant","agreement_group"],sort=True).size().reset_index(name="n")
    info = dict(n=79,unemployment_median=float(xmed),benefit_receipt_median=float(ymed),
                nonboundary_n=len(nonboundary),same_side_n=int(nonboundary.agreement_group.eq("same side of both medians").sum()),
                opposite_side_n=int(nonboundary.agreement_group.eq("opposite sides of medians").sum()),
                boundary_n=int(frame.agreement_group.eq("median boundary").sum()))
    info["same_side_pct_nonboundary"] = info["same_side_n"]/info["nonboundary_n"]*100
    require(int(summary.n.sum())==79 and sum([info["same_side_n"],info["opposite_side_n"],info["boundary_n"]])==79,"Quadrant counts inconsistent")
    return frame,summary,info


def outliers(frame, long, coords):
    records=[]
    for sample,part in [("available cases",frame),("shared complete cases",frame[frame.scoring_eligible])]:
        for feature in FEATURES:
            x=part[feature].dropna();q1,q3=x.quantile([.25,.75]);iqr=q3-q1
            for r in part[part[feature].notna()].itertuples():
                value=getattr(r,feature);flag=value<q1-1.5*iqr or value>q3+1.5*iqr
                if flag or value in [x.min(),x.max()]:
                    row,col=coords[(r.geo_code,YEAR,feature)]
                    records.append(dict(sample=sample,feature=feature,geo_code=r.geo_code,geo_name=r.geo_name,year=YEAR,
                                        value=value,tukey_flag=flag,is_minimum=value==x.min(),is_maximum=value==x.max(),
                                        lower_fence=q1-1.5*iqr,upper_fence=q3+1.5*iqr,workbook_row=row,workbook_column=col,
                                        raw_workbook_verified=True,decision="Retained; transcription verified, denominator uncertainty unresolved."))
    return pd.DataFrame(records)


def draw_figures(stage, complete, frame, context, corr, quadrant, qinfo):
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10,"axes.spines.top":False,
                         "axes.spines.right":False,"savefig.dpi":300})
    files=[]
    def save(fig,name,caption):
        fig.text(.04,.025,SOURCE+"\n"+caption,fontsize=8)
        path=stage/name;fig.savefig(path,dpi=300);plt.close(fig);files.append(name)
    fig,axes=plt.subplots(1,3,figsize=(13,5))
    for ax,feature,color in zip(axes,FEATURES,["#176b91","#287d68","#bc593a"]):
        x=complete[feature];counts,edges=np.histogram(x,bins="fd")
        hist,_,_=ax.hist(x,bins=edges,color=color,edgecolor="white")
        require(np.array_equal(hist,counts) and counts.sum()==79,"Histogram figure data mismatch")
        ax.axvline(x.median(),color="#303030",linestyle="--",label=f"Median {x.median():.2f}%")
        title=LABELS[feature].replace("employment participation","employment\nparticipation").replace(": population",":\npopulation")
        ax.set(title=title,xlabel=AXIS_LABELS[feature],ylabel="Ortsteile (count)")
        ax.legend(fontsize=8);ax.grid(axis="y",alpha=.15)
    fig.suptitle("Economic indicator distributions · Bremen · 2024 · Ortsteil · n = 79",x=.04,ha="left",fontsize=14)
    fig.subplots_adjust(left=.05,right=.98,wspace=.35,top=.8,bottom=.28)
    save(fig,"fig01_economic_distributions_2024.png","Shared complete cases; unweighted neighborhoods; percentages have distinct denominators. No population-weighted city rates.")

    ordered=complete.sort_values(["unemployment","geo_code"])
    selected=pd.concat([ordered.tail(5).iloc[::-1],ordered.head(5)])
    require(selected.geo_code.nunique()==10,"Compact comparison selection overlap")
    require(ordered.iloc[4].unemployment<ordered.iloc[5].unemployment and ordered.iloc[-6].unemployment<ordered.iloc[-5].unemployment,"Selection boundary ties require explicit handling")
    fig,axes=plt.subplots(1,3,figsize=(13,5.8),sharey=True)
    y=np.arange(10)
    for ax,feature,color in zip(axes,FEATURES,["#176b91","#287d68","#bc593a"]):
        ax.scatter(selected[feature],y,color=color,s=40)
        np.testing.assert_array_equal(ax.collections[0].get_offsets()[:,0],selected[feature].to_numpy())
        title=LABELS[feature].replace("employment participation","employment\nparticipation").replace(": population",":\npopulation")
        ax.set(title=title,xlabel="Observed share (%)",xlim=(0,100))
        ax.axhline(4.5,color="#94a3b8",ls="--",lw=.8);ax.grid(axis="x",alpha=.15)
    axes[0].set_yticks(y,selected.geo_name+" ("+selected.geo_code+")",fontsize=9)
    axes[0].set_ylim(9.6,-.6)
    fig.suptitle("Selected neighborhood contrasts · Bremen · 2024 · Ortsteil",x=.04,ha="left",fontsize=14)
    fig.subplots_adjust(left=.18,right=.98,top=.83,bottom=.27,wspace=.2)
    save(fig,"fig02_selected_neighborhood_comparison_2024.png",
         "Five highest then five lowest unemployment values among 79 complete cases; selection is not representative and is not a disadvantage ranking.\n"
         "Denominators: unemployed/(insured employees + unemployed); insured employees/population 15–<65; SGB II recipients/population under 65.")

    fig,axes=plt.subplots(1,3,figsize=(13,5))
    for ax,r in zip(axes,corr.itertuples()):
        ax.scatter(complete[r.first],complete[r.second],s=28,color="#176b91",alpha=.8,edgecolor="white",linewidth=.3)
        np.testing.assert_array_equal(ax.collections[0].get_offsets(),complete[[r.first,r.second]].to_numpy())
        ax.set(xlabel=AXIS_LABELS[r.first],ylabel=AXIS_LABELS[r.second],title=f"Spearman ρ = {r.spearman_rho:.3f}; n = {r.n}")
        ax.grid(alpha=.15)
    fig.suptitle("Economic indicator relationships · Bremen · 2024 · Ortsteil",x=.04,ha="left",fontsize=14)
    fig.subplots_adjust(left=.07,right=.98,wspace=.43,top=.8,bottom=.28)
    save(fig,"fig03_economic_indicator_relationships_2024.png","Same 79 observations in every panel; raw directions and distinct denominators. Correlation is descriptive, not causal or external validation.")

    colors={"same side of both medians":"#176b91","opposite sides of medians":"#c07a23","median boundary":"#64748b"}
    fig,ax=plt.subplots(figsize=(8,6.4))
    for label,color in colors.items():
        s=quadrant[quadrant.agreement_group.eq(label)]
        ax.scatter(s.unemployment,s.benefit_receipt,s=38,color=color,label=f"{label} (n={len(s)})",edgecolor="white",linewidth=.4)
    require(sum(len(c.get_offsets()) for c in ax.collections)==79,"Quadrant figure count mismatch")
    ax.axvline(qinfo["unemployment_median"],ls="--",color="#64748b",lw=1)
    ax.axhline(qinfo["benefit_receipt_median"],ls="--",color="#64748b",lw=1)
    ax.set(xlabel=AXIS_LABELS["unemployment"],ylabel=AXIS_LABELS["benefit_receipt"])
    ax.set_title("Exploratory median-quadrant concordance\nBremen · 2024 · Ortsteil · n = 79",loc="left")
    ax.legend(loc="upper left",fontsize=8);ax.grid(alpha=.12)
    fig.subplots_adjust(left=.13,right=.97,top=.83,bottom=.27)
    save(fig,"fig04_unemployment_sgbii_median_quadrants_2024.png",
         f"Sample medians: unemployment {qinfo['unemployment_median']:.4f}%; SGB II {qinfo['benefit_receipt_median']:.4f}%. Equality kept separately.\n"
         "Above/below are sample-relative comparisons, not poverty thresholds, policy classes, an index or a ranking.")

    missing=frame.set_index("geo_code")[FEATURES].isna()
    for feature in ["child_benefits","single_parents","income_median"]:
        missing[feature]=missing.index.map(context[feature].set_index("geo_code").value.isna())
    fig,ax=plt.subplots(figsize=(11,18))
    from matplotlib.colors import ListedColormap
    ax.imshow(missing.to_numpy(dtype=int),aspect="auto",cmap=ListedColormap(["#e2edf2","#b65332"]),vmin=0,vmax=1)
    require(missing.shape==(88,6) and int(missing[FEATURES].sum().sum())==22,"Missingness figure input mismatch")
    ax.set_xticks(range(6),["Unemployment\n2024","Employment\n2024","SGB II <65\n2024","SGB II <15\n2024","Single parents\n2024","Taxpayer income\n2020"],fontsize=9)
    ax.set_yticks(range(88),frame.geo_name+" ("+frame.geo_code+")",fontsize=7.5)
    ax.set_title("Coverage and blind spots across all represented Ortsteile\nBremen · Ortsteil · 2024 indicators; income separately 2020",loc="left",pad=18)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color="#e2edf2",label="Observed"),Patch(color="#b65332",label="Missing")],loc="upper right",bbox_to_anchor=(1.0,1.065),ncol=2,frameon=False,fontsize=9)
    fig.subplots_adjust(left=.28,right=.98,top=.92,bottom=.105)
    save(fig,"fig05_missingness_all_88_ortsteile.png","Blue = observed; orange = missing. Code order; no imputation. Income is a separate 2020 context and is not merged into 2024 scoring.\nUnits: percentages for five indicators; €1,000 per taxpayer for income. Source cell reasons and denominator counts remain unavailable.")
    return files,selected,missing


def main():
    protected=protected_files()
    frame,long,definitions,context,coords,validation=load_validate()
    complete=frame[frame.scoring_eligible].copy()
    available=statistics(frame,FEATURES,"available cases")
    common=statistics(complete,FEATURES,"shared complete cases")
    supplemental=pd.concat([statistics(s.rename(columns={"value":f}),[f],"available contextual cases",year=2020 if f=="income_median" else YEAR) for f,s in context.items()],ignore_index=True)
    corr=correlations(complete)
    quadrant,qcounts,qinfo=quadrants(complete)
    checks=outliers(frame,long,coords)
    excluded=frame.loc[~frame.scoring_eligible,["geo_code","geo_name","year","exclusion_reason"]]
    assessment=definitions.copy()
    evidence=pd.concat([available,supplemental]).set_index("feature")
    recommendations={"unemployment":"Primary economic measure; restricted denominator, not official unemployment rate.",
      "employment":"Primary economic measure; lower indicates reduced insured-employment participation, not all employment.",
      "benefit_receipt":"Primary material-support proxy; receipt is not all poverty and may coexist with employment.",
      "child_benefits":"Supplementary child-focused benefit reliance; overlaps under-65 receipt, not independent corroboration.",
      "single_parents":"Context only; household composition is not intrinsic deprivation or an allocation rule.",
      "income_median":"Separate 2020 context; taxpayer unit, not household disposable income; never carried forward to 2024."}
    for col in ["valid_n","missing_pct","mean","sd_sample","iqr","p10","p90","range"]:
        assessment[col]=assessment.feature.map(evidence[col])
    assessment["use_recommendation"]=assessment.feature.map(recommendations)
    assessment["definition_evidence"]="Exact local workbook headings and shared catalog; full current municipal definitions and reference dates unverified."
    assessment["statistical_sample"]="Available cases in each feature's own reporting year; primary correlations use 79 shared complete cases."
    assessment["overlap_evidence"]=assessment.feature.map({
        f:"; ".join(f"Spearman with {r.second if r.first==f else r.first}: {r.spearman_rho:.6f}, n={r.n}"
                    for r in corr.itertuples() if f in [r.first,r.second]) for f in FEATURES})
    assessment.loc[assessment.feature.eq("single_parents"),"overlap_evidence"]="Household composition context; no automatic economic disadvantage direction."
    assessment.loc[assessment.feature.eq("income_median"),"overlap_evidence"]="Different year and taxpayer denominator; excluded from primary 2024 association."
    overlap=[]
    child=context["child_benefits"].set_index("geo_code").value
    paired=complete.assign(child_benefits=complete.geo_code.map(child)).dropna(subset=["child_benefits"])
    overlap.append(dict(first="benefit_receipt",second="child_benefits",n=len(paired),year=2024,
                        spearman_rho=float(spearmanr(paired.benefit_receipt,paired.child_benefits).statistic),
                        note="Supplementary overlapping age-subgroup measure; not an additional independent baseline indicator."))
    assessment.loc[assessment.feature.eq("child_benefits"),"overlap_evidence"]=f"Spearman with under-65 receipt {overlap[0]['spearman_rho']:.6f}, n={overlap[0]['n']}; overlapping age population."
    geometry=[n for n in protected if Path(n).suffix.lower() in {".geojson",".shp",".gpkg"}]
    require(not geometry,"Boundary files now present: inspect compatibility before changing map decision")
    validation.update(quadrant=qinfo,source_status_counts=long.value_status.value_counts().to_dict(),
                      primary_missing_counts={f:int(frame[f].isna().sum()) for f in FEATURES},
                      geometry_status="No authoritative Ortsteil polygon file present; no maps generated.",protected_file_count=len(protected))
    with tempfile.TemporaryDirectory(prefix="bremen-section2-v2-") as temporary:
        stage=Path(temporary);report=stage/"reports";figures=stage/"figures";report.mkdir();figures.mkdir()
        def csv_out(name,data):data.to_csv(report/name,index=False,encoding="utf-8-sig",na_rep="")
        csv_out("descriptive_available_cases.csv",available)
        csv_out("descriptive_complete_cases.csv",common)
        csv_out("supplementary_context_statistics.csv",supplemental)
        csv_out("indicator_assessment.csv",assessment)
        csv_out("economic_indicator_correlations.csv",corr)
        csv_out("supplementary_indicator_overlap.csv",pd.DataFrame(overlap))
        csv_out("median_quadrant_observations.csv",quadrant)
        csv_out("median_quadrant_counts.csv",qcounts)
        csv_out("outlier_source_review.csv",checks)
        csv_out("excluded_ortsteile.csv",excluded)
        figure_names,selection,missing=draw_figures(figures,complete,frame,context,corr,quadrant,qinfo)
        csv_out("figure02_selected_observations.csv",selection[["geo_code","geo_name","year"]+FEATURES])
        coverage=pd.DataFrame([dict(feature=f,year=2020 if f=="income_median" else YEAR,represented_n=88,observed_n=EXPECTED_VALID[f],missing_n=88-EXPECTED_VALID[f],missing_pct=(88-EXPECTED_VALID[f])/88*100) for f in ALL_FEATURES])
        csv_out("coverage_summary.csv",coverage)
        missing_table=missing.reset_index().merge(frame[["geo_code","geo_name","scoring_eligible"]],on="geo_code",validate="one_to_one")
        csv_out("missingness_all_88.csv",missing_table)
        validation["figure_validation"]={"distribution_count_each":79,"selected_comparison_n":10,"scatter_n_each":79,"quadrant_count":79,"missingness_shape":[88,6],"histograms_and_scatter_inputs_verified":True}
        (report/"input_validation.json").write_text(json.dumps(validation,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        captions=f"""# Section 2 V2 figure captions

All figures: supplied Datentabelle.xls and the shared selected/analysis-ready CSVs; Ortsteil level. PNGs are 300 dpi. Values are unweighted neighborhood observations, not population-weighted city rates.

1. **fig01_economic_distributions_2024.png** — Three economic percentages for the shared 79 complete cases in 2024. Freedman–Diaconis bin edges; median lines. Denominators differ and panels are independent.
2. **fig02_selected_neighborhood_comparison_2024.png** — Five highest and five lowest unemployment values among the same 79 complete cases; geographic code breaks sorting ties, with no boundary ties present. Three panels show original percentages on a common 0–100 scale with distinct denominators. Selected contrasts are not a representative sample, composite score or disadvantage ranking. Exact plotted data: figure02_selected_observations.csv.
3. **fig03_economic_indicator_relationships_2024.png** — Pairwise scatterplots and Spearman coefficients for the same 79 observations. Raw employment direction is retained; negative association is not disagreement with the economic interpretation. Descriptive ecological association, not causality or external validation.
4. **fig04_unemployment_sgbii_median_quadrants_2024.png** — Unemployment/SGB II relationships relative to sample medians {qinfo['unemployment_median']:.4f}% and {qinfo['benefit_receipt_median']:.4f}%. Above/below use strict comparisons, with equal-to-median observations kept separately. Counts describe sample-relative concordance, not poverty thresholds, deprivation classes, an index or an allocation rule.
5. **fig05_missingness_all_88_ortsteile.png** — All 88 areas in code order; observed/missing cells for five 2024 indicators and separate 2020 taxpayer income. Units are % except income (€1,000 per taxpayer). These years are not pooled into one score. Absence of data is not absence of disadvantage.

Recommended report selection: Figures 1 and 3, plus Figure 4 if exploratory agreement is central. Presentation: Figures 2 and 4, plus a coverage summary. Keep Figure 5 and exact selection/coverage tables supplementary. Do not use all five large figures in a short report.
"""
        (report/"figure_captions.md").write_text(captions,encoding="utf-8")
        blind="""# Data blind spots and mapping decision

No authoritative Ortsteil polygons (.geojson, .shp or .gpkg) were found in the project. Existing geography_lookup.csv supplies identifiers/names, not boundaries or coordinates. Maps were not generated. Future mapping requires a documented official source, licence, boundary reference year, valid geometry/CRS and a verified code-based join including all represented areas. Do not treat absent polygons as zero-valued observations or use guessed coordinates.

The 2024 complete sample excludes nine small/industrial/rural-coded areas with missing labor-market observations; names alone do not explain missingness. Source reasons remain unknown. Four lack all three economic values and five retain SGB II values. Available-case summaries expose the latter information rather than deleting these records.

Reference dates, release/revision dates, numerator restrictions and denominator counts are incompletely documented. Registered unemployment, insured employment and benefit receipt represent different populations. A common year does not establish simultaneous measurement. No sampling uncertainty, population-weighted city rates or operational allocation validity can be inferred from the rates alone.

Housing affordability, wealth, education, health, accessibility, mobility, environmental exposure and resident experience are not represented by the three economic indicators. Single-parent prevalence adds limited household composition, not an age structure or comprehensive demographic profile. No demographic identity is treated as deprivation. Income context is 2020 and taxpayer-based, not current disposable household income. Historical boundary/definition flags remain unverified, so no trends or historical rankings are produced. The 80% coverage gate is pragmatic, not a statistical validity guarantee.

No ISO certification, exact ISO indicator correspondence, causal effect, policy intervention outcome or externally validated 'best indicator' is claimed. The specifically titled five-page guide was not located; the user's explicit implementation requirements and shared RQs/definitions govern this package.
"""
        (report/"data_blind_spots.md").write_text(blind,encoding="utf-8")
        note=f"""# Section 2 V2 — Data and Indicator Analysis

## Scope and authoritative baseline

Branch analysis/section-2-v2; fetched baseline {BASELINE}. RQ1: What socioeconomic and demographic differences exist across Bremen's neighborhoods? RQ2: Which indicators are most useful for identifying neighborhood disadvantage?

This independently recalculated evidence package reads the shared ortsteil_analysis_ready.csv, selected_indicators_long.csv, indicator_selection.csv and data_dictionary.csv. It does not read old Section 2 statistical outputs or modify shared files. The specifically titled five-page 'Bremen Smart Governance — Section 2 Guide' was not located; available shared evidence guides are not claimed to be that document. Implementation follows the supplied detailed requirements and group_results/OVERVIEW.md. No composite indices, TOPSIS, clustering, disadvantage ranking or architecture are implemented.

## Data selection and quality

Master coverage: 88 Ortsteile, 2024. Comparison: shared 79-row scoring_eligible sample, used here only as a completeness flag. Codes remain strings; no Stadtteil/Stadtbezirk/city aggregates enter. Eligibility was independently checked against all three nonmissing values. No missing values were replaced with zero or imputed. Exact source worksheet, German label, block=1, units and annual reporting periods were checked. All 9,152 selected observations, including blanks, match original workbook cells; all 24 original-source hashes match the shared source manifest. Geographic-year-feature keys are unique, and selected observations have no invalid statuses or out-of-range percentages. The income analysis unit is explicitly 1000 EUR from its original heading; its original inferred unit is blank.

{md(coverage)}

{md(excluded)}

These nine areas remain in coverage evidence. Source reasons for missingness are unknown; concentrated exclusions can distort coverage. The 79-area sample is not all Bremen neighborhoods. Validation reports in the shared baseline document source reconstruction and an exploratory annual gate; exact observation dates and historical comparability remain unverified.

## Methods

Both complete-case and available-case descriptive tables report valid n, missingness, extrema with names, mean/median, ddof=1 sample SD, linear-interpolation quartiles/IQR/P10/P90 and percentage-point range. Complete-case tables show zero within-sample missingness; exclusion coverage is reported separately against 88 master records. All neighborhood means give each area equal weight, not each resident. Context uses available observations in its own year; income is never carried forward.

Spearman coefficients use average ranks on the fixed 79-case economic sample, independently checked against Pearson correlation of average ranks. No p-values, confidence intervals, causal effects or spatial independence claims are asserted. Correlation measures monotone association, not numerical interchangeability, external validity or predictive performance. Employment's raw direction is retained. The child-benefit overlap calculation is supplementary and explicitly overlapping, not a fourth independent baseline criterion.

Median quadrants are exploratory: strict above/below comparisons, equality kept as a boundary category. No indicator is aggregated and no deprivation label or neighborhood rank is assigned. Thresholds depend on the sample; they are not official poverty standards. Tukey fences (Q1−1.5×IQR, Q3+1.5×IQR) flag extremes separately by sample. Flags and extrema were checked against workbook coordinates and retained; transcription agreement does not resolve small-denominator uncertainty.

## RQ1 — observed differences

Shared complete-case descriptions:

{md(common[['feature','valid_n','mean','median','minimum','minimum_names','maximum','maximum_names','sd_sample','iqr','p10','p90','range']])}

Available-case descriptions:

{md(available[['feature','valid_n','mean','median','minimum','minimum_names','maximum','maximum_names','range']])}

The SGB II available-case and complete-case summaries differ because five areas outside the common sample retain observed benefit values. This is a sample-composition effect, not a change in their measurements. Large neighborhood contrasts support investigation of differing labor-market/material-support conditions; they do not establish individual poverty or intervention needs.

Supplementary/contextual evidence:

{md(supplemental[['feature','year','valid_n','mean','median','minimum','minimum_names','maximum','maximum_names']])}

Single-parent share describes household composition and cannot establish disadvantage by itself. Child benefit receipt reflects a narrower, overlapping recipient population. Median taxpayer income is historical 2020 context only. The current data do not adequately answer broad age, migration, health or other demographic dimensions of RQ1; this is a substantive limitation rather than a reason to import old indicators automatically.

## RQ2 — usefulness and overlap

{md(corr[['first','second','n','spearman_rho']])}

Unemployment and benefit receipt describe strongly associated but differently defined economic conditions. Employment adds participation information with a reversed disadvantage direction, while excluding self-employment and civil servants. The three have credible directional interpretations for partial economic disadvantage; none is a universal deprivation measure. Correlation/redundancy should be handed to Section 4 without selecting weights here. Definition clarity, coverage, dispersion and timeliness are assessed in indicator_assessment.csv; no indicator is declared objectively best without an external criterion.

Supplementary under-65 versus child-benefit Spearman rho is {overlap[0]['spearman_rho']:.6f}, n={overlap[0]['n']}. This overlap does not provide independent validation.

Median-quadrant result: {qinfo['same_side_n']} same-side and {qinfo['opposite_side_n']} opposite-side observations among {qinfo['nonboundary_n']} strictly off-boundary cases ({qinfo['same_side_pct_nonboundary']:.2f}% same-side); {qinfo['boundary_n']} equal at least one median. All 79 observations remain in the plotted/table evidence. Exact medians and group identities are exported. This sample-relative concordance is descriptive, not a deprivation index, policy threshold or resource-allocation rule.

## Figures, maps and interpretation

Five 300-dpi figures cover distributions, transparent selected contrasts, economic relationships, exploratory quadrant concordance and all-88 missingness. Each identifies year, level, units and sources. Exact plotted inputs, selection rules and captions are retained. No boundary polygon file is available; maps are not defensible and were not generated. Geographic inequality is therefore presented as differences across named Ortsteile, not spatial-autocorrelation or location effects. See figure_captions.md and data_blind_spots.md.

For the final report use Figures 1 and 3, optionally 4; keep the full missingness view supplementary. A presentation can use Figures 2 and 4 plus a coverage summary. Contextual household characteristics do not automatically indicate deprivation. Ecological rates cannot identify individual disadvantage, and different reference dates may affect comparison. Historical changes, current-2026 claims and causal/resource-allocation conclusions remain unsupported.

## Reproduction and handover

From the repository root, using the existing Section 2 environment:

```powershell
.\\.venv-section2\\Scripts\\python.exe -B src/analyze_section2_v2.py
```

The script reads shared utilities for ROOT/YEAR/FEATURES only; it never runs the shared pipeline or its output-writing helpers. Required runtime packages are pandas, numpy, scipy, matplotlib and xlrd already available in that environment. Exact runtime versions and input/output hashes are recorded in reproduction_manifest.json. Reproduction in another environment requires those packages; no package installation is part of this task.

Existing outputs are never overwritten: an identical rerun checks equality and leaves files untouched; differing existing V2 outputs cause failure. All tracked and pre-existing untracked non-V2 files are hashed before and after execution. New outputs are staged, schema/count/figure inputs and correlation calculations are checked, and published only after validation. Source and output hashes plus baseline commit allow review without trusting notebook state. No commits or pushes are made. This is technical evidence, not a substitute for the group's literature review or verified municipal metadata. See handover_sections_1_3_4.md for section boundaries.
"""
        (report/"methods_results.md").write_text(note,encoding="utf-8")
        handover="""# Section 2 V2 handover

Section 1: use computed neighborhood contrasts and context to motivate the urban inequality problem. Describe 2024 rates and their distinct populations; no causal or individual-poverty claims. Household composition is contextual. Do not imply these observations describe current 2026 conditions.

Section 3: use the input schema, commit/hashes, source definitions, 88/79 coverage, missingness flags and validation failures as evidence requirements for transparent governance. Publication must expose exclusions and denominator limitations. Section 2 supplies these contracts, not architecture or a dashboard.

Section 4: primary shared columns are unemployment, employment and benefit_receipt, with exactly the same 79 scoring_eligible codes. Unemployment/benefits point toward higher measured disadvantage; employment toward lower. Indicator correlations flag conceptual overlap, not weights or external validation. Child benefits overlap the baseline and belong to sensitivity discussion if used. Section 2 has not computed composites, TOPSIS, clustering, ranking agreement or disadvantage ranks. Keep method agreement distinct from economic-indicator association.

Shared files remain authoritative and unchanged. All V2 evidence is separately named under reports/section2_v2 and figures/section2_v2. Income remains 2020; historical changes remain blocked. Exact source dates, denominator counts and boundary history require further municipal verification. The five-page named guide was not located; obtain it before claiming document-specific compliance beyond the supplied requirements.
"""
        (report/"handover_sections_1_3_4.md").write_text(handover,encoding="utf-8")
        # Validate persisted tables and staged image metadata before publishing.
        for name,n in [("descriptive_available_cases.csv",3),("descriptive_complete_cases.csv",3),
                       ("economic_indicator_correlations.csv",3),("median_quadrant_observations.csv",79),
                       ("excluded_ortsteile.csv",9),("missingness_all_88.csv",88),("indicator_assessment.csv",6)]:
            require(len(pd.read_csv(report/name,encoding="utf-8-sig",dtype={"geo_code":str}))==n,"Output table cardinality failed")
        from PIL import Image
        for name in figure_names:
            with Image.open(figures/name) as image:
                require(abs(image.info["dpi"][0]-300)<.1 and min(image.size)>1000,"Figure resolution failed")
        require(protected=={n:sha(ROOT/n) for n in protected},"Protected/shared file changed during execution")
        outputs={}
        staged=[]
        for source,target_dir in [(report,REPORT),(figures,FIGURES)]:
            for path in sorted(source.iterdir()):
                target=target_dir/path.name
                outputs[relative(target)]=sha(path)
                staged.append((path,target))
        manifest=dict(generator="src/analyze_section2_v2.py",script_sha256=sha(Path(__file__)),baseline_commit=BASELINE,
                      branch="analysis/section-2-v2",versions=dict(python=platform.python_version(),pandas=pd.__version__,numpy=np.__version__,
                      scipy=scipy.__version__,matplotlib=matplotlib.__version__,xlrd=xlrd.__version__),
                      protected_input_hashes=protected,validation=validation,outputs=outputs)
        manifest_text=json.dumps(manifest,indent=2,ensure_ascii=False)+"\n"
        manifest_path=REPORT/"reproduction_manifest.json"
        # Check every collision first: no file is published if an existing output differs.
        for source,target in staged:
            require(not target.exists() or sha(target)==sha(source),f"Refusing to overwrite existing output: {target}")
        require(not manifest_path.exists() or manifest_path.read_text(encoding="utf-8")==manifest_text,"Refusing to overwrite changed manifest")
        for source,target in staged:
            target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():
                with target.open("xb") as f:f.write(source.read_bytes())
        if not manifest_path.exists():
            with manifest_path.open("x",encoding="utf-8") as f:f.write(manifest_text)
        require(protected=={n:sha(ROOT/n) for n in protected},"Protected files changed after publication")
        require(all(sha(ROOT/n)==h for n,h in outputs.items()),"Published hashes differ from validated staging")
    print(available.to_string(index=False))
    print(common.to_string(index=False))
    print(supplemental.to_string(index=False))
    print(corr.to_string(index=False))
    print(json.dumps(qinfo,indent=2))
    print("PASS: source cells, hashes, schemas, periods, keys, eligibility, missingness, correlations, quadrants, figures and protected files.")


if __name__ == "__main__":
    main()
