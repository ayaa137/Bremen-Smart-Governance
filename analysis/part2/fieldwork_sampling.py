"""Purposive future fieldwork candidates; not representative or observed fieldwork.

From the repository root: python -B analysis/part2/fieldwork_sampling.py
After reviewing a reported difference, explicitly approve replacement with --replace.
Uses saved 2024 results only; scenario ranges are not confidence intervals.
"""
import argparse
from difflib import unified_diff
from io import StringIO
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
KEY = ["geo_code", "geo_name", "year"]
FEATURES = ["unemployment", "employment", "benefit_receipt"]


def read(relative):
    frame = pd.read_csv(ROOT / relative, dtype={"geo_code": str})
    if frame["geo_code"].isna().any() or not frame["geo_code"].str.fullmatch(r"\d{3}").all():
        raise ValueError(f"Invalid geographic codes: {relative}")
    return frame


def main(replace=False):
    base = read("data/processed/ortsteil_analysis_ready.csv")
    if len(base) != 88 or base["geo_code"].duplicated().any():
        raise ValueError("Expected 88 unique master areas")
    eligible = base[FEATURES].notna().all(axis=1)
    if not base["scoring_eligible"].isin([True, False]).all() or not eligible.equals(base["scoring_eligible"]):
        raise ValueError("Eligibility does not match complete economic observations")
    sample = base.loc[eligible, KEY + FEATURES].copy()
    if len(sample) != 79 or not sample["year"].eq(2024).all():
        raise ValueError("Expected 79 complete 2024 areas")

    inputs = [
        ("results/composite_index_results.csv", ["composite_score", "rank"], {"rank": "composite_rank"}),
        ("results/topsis_results.csv", ["topsis_score", "rank"], {"rank": "topsis_rank"}),
        ("results/kmeans_results.csv", FEATURES + ["cluster"], {}),
    ]
    for relative, columns, renames in inputs:
        frame = read(relative)
        if len(frame) != 79 or frame["geo_code"].duplicated().any():
            raise ValueError(f"Expected 79 unique result areas: {relative}")
        sample = sample.merge(frame[KEY + columns].rename(columns=renames),
                              on=KEY, how="left", validate="one_to_one",
                              indicator=True, suffixes=("", "_saved"))
        if not sample.pop("_merge").eq("both").all():
            raise ValueError(f"Code/name/year coverage mismatch: {relative}")
        if relative.endswith("kmeans_results.csv"):
            for feature in FEATURES:
                if not sample[feature].equals(sample.pop(feature + "_saved")):
                    raise ValueError("Cluster inputs differ from master observations")

    ranges = read("results/weight_rank_ranges.csv")
    if len(ranges) != 158 or ranges.duplicated(["method", "geo_code"]).any():
        raise ValueError("Expected two methods x 79 unique weight ranges")
    if set(ranges["method"]) != {"composite", "topsis"}:
        raise ValueError("Unexpected sensitivity methods")
    for method in ["composite", "topsis"]:
        frame = ranges.loc[ranges["method"].eq(method), ["geo_code", "geo_name", "min", "max"]]
        sample = sample.merge(
            frame.rename(columns={"min": method + "_weight_rank_min",
                                  "max": method + "_weight_rank_max"}),
            on=["geo_code", "geo_name"], how="left", validate="one_to_one",
            indicator=True)
        if not sample.pop("_merge").eq("both").all():
            raise ValueError("Sensitivity coverage/name mismatch")
        low, high = sample[method + "_weight_rank_min"], sample[method + "_weight_rank_max"]
        if not (low.between(1, 79) & high.between(1, 79) & low.le(high)).all():
            raise ValueError("Invalid sensitivity rank bounds")
        if not sample[method + "_rank"].between(low, high).all():
            raise ValueError(f"{method} sensitivity ranges exclude baseline ranks")
        sample[method + "_weight_rank_span"] = high - low

    if sample.isna().any().any() or not sample[FEATURES].apply(lambda x: x.between(0, 100)).all().all():
        raise ValueError("Missing evidence or invalid percentages")
    if sample["cluster"].nunique() != 2:
        raise ValueError("Expected two nominal K-means profiles")
    for method in ["composite", "topsis"]:
        if not sample[method + "_score"].between(0, 1).all() or not sample[method + "_rank"].between(1, 79).all():
            raise ValueError("Invalid baseline scores/ranks")
        expected = sample[method + "_score"].rank(ascending=False, method="min")
        if not sample[method + "_rank"].eq(expected).all():
            raise ValueError(f"{method} ranks disagree with scores")
    sample["absolute_rank_gap"] = (sample["composite_rank"] - sample["topsis_rank"]).abs()
    sample["max_weight_rank_span"] = sample[["composite_weight_rank_span", "topsis_weight_rank_span"]].max(axis=1)
    # Sequential selection without replacement; geo_code breaks all ties.
    rules = [
        ("recommended", "high_composite", "composite_rank", True,
         "Highest baseline composite score; higher measured economic disadvantage."),
        ("recommended", "low_composite_contrast", "composite_rank", False,
         "Lowest baseline composite score; contrasting measured economic profile."),
        ("recommended", "method_disagreement", "absolute_rank_gap", False,
         "Largest remaining absolute composite-TOPSIS rank gap."),
        ("reserve", "weight_sensitivity", "max_weight_rank_span", False,
         "Sensitivity-focused reserve: largest remaining rank span across 200 saved weight scenarios; not a confidence interval or a substitute for every visit role."),
        ("reserve", "high_composite_alternative", "composite_rank", True,
         "Alternative high-disadvantage candidate: highest remaining composite score; reserve for the high-composite visit, not interchangeable with the sensitivity reserve."),
    ]
    chosen = []
    for priority, (role, criterion, column, ascending, reason) in enumerate(rules, start=1):
        pool = sample.loc[~sample["geo_code"].isin([row["geo_code"] for row in chosen])]
        row = pool.sort_values([column, "geo_code"], ascending=[ascending, True]).iloc[0].to_dict()
        row.update(visit_priority=priority, visit_role=role, selection_criterion=criterion,
                   selection_reason=reason, fieldwork_status="proposed_not_visited",
                   sampling_scope="Purposive 2024 complete-case neighbourhood sample; not statistically representative")
        chosen.append(row)
    output = pd.DataFrame(chosen)
    if len(output) != 5 or output["geo_code"].nunique() != 5 or output.isna().any().any():
        raise ValueError("Expected five unique complete candidates")
    if output.loc[output["visit_role"].eq("recommended"), "cluster"].nunique() != 2:
        raise ValueError("Recommended visits must cover both nominal profiles")
    destination = ROOT / "results/part2/fieldwork_shortlist.csv"
    content = output.to_csv(index=False, lineterminator="\n")
    restored = pd.read_csv(StringIO(content), dtype={"geo_code": str})
    pd.testing.assert_frame_equal(output, restored, check_dtype=False)
    payload = content.encode("utf-8")
    existing = destination.read_bytes() if destination.exists() else None
    if existing is not None and existing != payload:
        print("".join(unified_diff(existing.decode("utf-8").splitlines(True),
                                   content.splitlines(True), fromfile="existing CSV",
                                   tofile="proposed CSV")), end="")
        if not replace:
            raise SystemExit("CSV unchanged. Review the difference; explicit replacement approval requires --replace.")
    if existing != payload:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
    print(output[["geo_code", "geo_name", "visit_role", "selection_criterion",
                  "cluster", "composite_rank", "topsis_rank", "max_weight_rank_span"]].to_string(index=False))
    print("PASS: joins, eligibility, missing values, rank bounds, five rows, both profiles and CSV round-trip")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replace", action="store_true", help="Explicitly approve replacing a differing CSV")
    main(replace=parser.parse_args().replace)
