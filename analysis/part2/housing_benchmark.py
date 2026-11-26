"""Read-only inputs; descriptive housing association, not external validation.

Run from any directory: python <repository>/analysis/part2/housing_benchmark.py
Existing dependencies: pandas, numpy and matplotlib. No p-values are computed.
"""
from io import BytesIO
from itertools import combinations
from pathlib import Path
import hashlib
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
LABEL = "Durchschnittliche Wohnfl\u00e4che je Einwohner:innen in m2"
MEASURE = "Atlas-reported residential floor area per resident, 2024"
CAVEAT = ("Numerator stock scope, population basis, exact reference date and boundary vintage are unverified.\n"
          "Household size, vacancies, urban form and housing structure may affect interpretation.\n"
          "Not occupied living space, overcrowding, housing adequacy or independent external validation.")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def spearman(frame):
    ranks = frame[["composite_score", "floor_area_m2_per_resident"]].rank(method="average")
    return float(ranks.iloc[:, 0].corr(ranks.iloc[:, 1], method="pearson"))


def independent_spearman(frame):
    # Independently assign average ranks using Python sorting, then use the
    # pairwise-difference identity for correlation (valid with tied ranks).
    def ranks(values):
        ordered = sorted(enumerate(values), key=lambda item: item[1])
        result = [0.0] * len(values)
        start = 0
        while start < len(values):
            end = start + 1
            while end < len(values) and ordered[end][1] == ordered[start][1]:
                end += 1
            for index, _ in ordered[start:end]:
                result[index] = (start + 1 + end) / 2
            start = end
        return result
    x = ranks(frame.composite_score.tolist())
    y = ranks(frame.floor_area_m2_per_resident.tolist())
    differences = [(x[i] - x[j], y[i] - y[j]) for i, j in combinations(range(len(x)), 2)]
    return math.fsum(a*b for a, b in differences) / math.sqrt(
        math.fsum(a*a for a, _ in differences) * math.fsum(b*b for _, b in differences))


def main():
    panel = pd.read_csv(ROOT / "data/processed/ortsteil_analysis_ready.csv", dtype={"geo_code": str})
    scores = pd.read_csv(ROOT / "results/composite_index_results.csv", dtype={"geo_code": str})
    atlas = pd.read_csv(ROOT / "data/processed/excel_ortsteilatlas_long.csv", dtype={"geo_code": str}, low_memory=False)
    metadata = pd.read_csv(ROOT / "data/processed/section2_indicator_metadata.csv")
    require({"geo_code", "geo_name", "year", "geo_level", "scoring_eligible", "exclusion_reason"} <= set(panel), "Panel schema changed.")
    require({"geo_code", "geo_name", "year", "composite_score"} <= set(scores), "Score schema changed.")
    require({"geo_code", "geo_name", "year", "year_start", "year_end", "reporting_period", "indicator", "source_sheet", "source_file", "geo_level", "value", "value_status"} <= set(atlas), "Atlas schema changed.")
    require(panel.scoring_eligible.isin([True, False]).all(), "Invalid eligibility flag.")
    eligible = panel.loc[panel.scoring_eligible].copy()
    require(len(panel) == 88 and panel.geo_code.is_unique, "Unexpected panel geography.")
    require(len(eligible) == 79 and eligible.year.eq(2024).all() and eligible.geo_level.eq("Ortsteil").all(), "Unexpected eligible sample/year/level.")
    require(eligible.exclusion_reason.fillna("").eq("").all(), "Eligible rows contain exclusions.")
    require(len(scores) == 79 and scores.geo_code.is_unique and scores.year.eq(2024).all(), "Unexpected score sample/year.")
    housing = atlas.loc[atlas.indicator.eq(LABEL) & atlas.source_sheet.eq("Wohnungswesen I") & atlas.geo_level.eq("Ortsteil") & atlas.year.eq(2024)].copy()
    require(len(housing) == 88 and housing.geo_code.is_unique, "Housing selection is incomplete or duplicated.")
    require(housing.source_file.eq("Datentabelle.xls").all() and housing.year_start.eq(2024).all() and housing.year_end.eq(2024).all() and housing.reporting_period.astype(str).eq("2024").all(), "Unexpected housing provenance/period.")
    meta = metadata.loc[metadata.id.eq("floor_area_m2_per_resident")]
    require(len(meta) == 1, "Missing or duplicated housing metadata.")
    m = meta.iloc[0]
    require(m.label == LABEL and m.sheet == "Wohnungswesen I" and m.source_file == "Datentabelle.xls" and m.geo_level == "Ortsteil" and m.year_start == m.year_end == m.reporting_period == 2024, "Metadata mismatch.")
    for table in [eligible, scores, housing]:
        require(table.geo_code.str.fullmatch(r"\d{3}").all(), "Codes must be unchanged three-character strings.")
    require(set(eligible.geo_code) == set(scores.geo_code), "Score/eligibility code mismatch.")
    require(set(eligible.geo_code) <= set(housing.geo_code), "Housing codes missing.")
    joined = eligible[["geo_code", "geo_name"]].merge(scores[["geo_code", "geo_name", "composite_score"]], on="geo_code", validate="one_to_one", suffixes=("", "_score"))
    joined = joined.merge(housing[["geo_code", "geo_name", "value", "value_status"]], on="geo_code", validate="one_to_one", suffixes=("", "_housing"))
    require(len(joined) == 79 and joined.geo_name.eq(joined.geo_name_score).all() and joined.geo_name.eq(joined.geo_name_housing).all(), "Join loss or name mismatch.")
    require(joined.value_status.eq("ok").all(), "Missing/suppressed housing observations.")
    frame = joined[["geo_code", "geo_name", "composite_score", "value"]].rename(columns={"value": "floor_area_m2_per_resident"}).sort_values("geo_code").reset_index(drop=True)
    require(np.isfinite(frame[["composite_score", "floor_area_m2_per_resident"]].to_numpy(dtype=float)).all(), "Nonfinite observations.")
    require(frame.composite_score.between(0, 1).all() and frame.floor_area_m2_per_resident.gt(0).all(), "Unexpected value ranges.")
    require(frame.composite_score.nunique() > 1 and frame.floor_area_m2_per_resident.nunique() > 1, "Constant variable.")
    # Every essential data gate has passed before calculation.
    rho = spearman(frame)
    require(math.isclose(rho, independent_spearman(frame), abs_tol=1e-12), "Independent Spearman check failed.")
    loo = []
    for index in frame.index:
        omitted = frame.drop(index)
        value = spearman(omitted)
        require(math.isclose(value, independent_spearman(omitted), abs_tol=1e-12), "Independent leave-one-out check failed.")
        loo.append(value)
    reverse = [spearman(frame.iloc[::-1].drop(index)) for index in reversed(frame.index)]
    require(np.allclose(loo, reverse[::-1], rtol=0, atol=1e-12), "Leave-one-out order reproducibility failed.")
    frame["year"] = 2024
    frame["full_sample_spearman_rho"] = rho
    frame["spearman_rho_if_omitted"] = loo
    frame["rho_change_if_omitted"] = frame.spearman_rho_if_omitted - rho

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11})
    fig, ax = plt.subplots(figsize=(11, 7))
    fig.subplots_adjust(left=0.12, right=0.96, bottom=0.30, top=0.78)
    fig.text(0.07, 0.95, "Housing context and measured disadvantage", fontsize=19, weight="bold", va="top")
    fig.text(0.07, 0.89, f"Exploratory Ortsteil comparison | n = 79 | Spearman rho = {rho:.4f}", fontsize=12)
    ax.scatter(frame.composite_score, frame.floor_area_m2_per_resident, s=42, color="#0072B2", alpha=0.8, edgecolors="white", linewidths=0.5)
    ax.set(xlim=(0, 1), xlabel="Fixed 2024 composite score (higher = greater measured disadvantage)", ylabel="Residential floor area per resident (m\u00b2/person)")
    ax.grid(color="#E2E8F0", linewidth=0.7); ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    fig.text(0.07, 0.18, MEASURE, fontsize=11, weight="bold")
    fig.text(0.07, 0.14, CAVEAT, fontsize=9, va="top", linespacing=1.5)
    fig.text(0.07, 0.025, "Source: Statistisches Landesamt Bremen, supplied Ortsteilatlas export; project fixed composite scores.", fontsize=9)
    png = BytesIO(); fig.savefig(png, format="png", dpi=300, metadata={"Software": "Bremen housing-context benchmark"}); plt.close(fig)
    outputs = {
        ROOT / "results/part2/housing_benchmark.csv": frame.to_csv(index=False, float_format="%.17g", lineterminator="\n").encode("utf-8"),
        ROOT / "figures/part2/housing_benchmark.png": png.getvalue(),
    }
    # Preflight both files before writing either: never overwrite different bytes.
    for path, content in outputs.items():
        require(not path.exists() or path.read_bytes() == content, f"Different existing output; explicit approval required: {path}")
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with path.open("xb") as handle:
                handle.write(content)
        print(path.relative_to(ROOT), hashlib.sha256(content).hexdigest())
    print(f"n=79; Spearman rho={rho:.17g}; leave-one-out=[{min(loo):.17g}, {max(loo):.17g}]")
    print("Descriptive statistics (unweighted; SD uses ddof=1):")
    print(frame[["composite_score", "floor_area_m2_per_resident"]].describe().to_string())
    print("Most influential omissions by absolute change (relative influence, not a significance threshold):")
    influence = frame.reindex(frame.rho_change_if_omitted.abs().sort_values(ascending=False).index)
    print(influence[["geo_code", "geo_name", "spearman_rho_if_omitted", "rho_change_if_omitted"]].head(3).to_string(index=False))
    print("PASS: data gates; independent full-sample and 79 leave-one-out checks; reversed-order reproducibility.")
    print(MEASURE + "\n" + CAVEAT)


if __name__ == "__main__":
    main()
