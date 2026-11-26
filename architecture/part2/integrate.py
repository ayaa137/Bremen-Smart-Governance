"""Assemble the saved 2024 analyses into a versioned, read-only data release."""

import csv
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import subprocess
from uuid import uuid4


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
YEAR = "2024"
RELEASE = "2024-v1"
AREAS, SCORED, VISITS = 88, 79, 5
FEATURES = ("unemployment", "employment", "benefit_receipt")
KEY_COLUMNS = ("geo_code", "geo_name", "year")
HOUSING_COLUMNS = (
    "floor_area_m2_per_resident", "full_sample_spearman_rho",
    "spearman_rho_if_omitted", "rho_change_if_omitted",
)
VISIT_COLUMNS = (
    "composite_weight_rank_min", "composite_weight_rank_max", "composite_weight_rank_span",
    "topsis_weight_rank_min", "topsis_weight_rank_max", "topsis_weight_rank_span",
    "absolute_rank_gap", "max_weight_rank_span", "visit_priority", "visit_role",
    "selection_criterion", "selection_reason", "fieldwork_status", "sampling_scope",
)
SPATIAL_NUMBERS = (
    "k n morans_i theoretical_null_expectation permutation_null_mean p_two_sided "
    "extreme_permutations permutations seed components isolates undirected_edges degree_min "
    "degree_mean degree_max link_distance_min_m link_distance_median_m link_distance_mean_m "
    "link_distance_max_m max_area_error_km2 p_minimum"
).split()
INPUTS = {
    "spine": "data/processed/ortsteil_analysis_ready.csv",
    "composite": "results/composite_index_results.csv",
    "topsis": "results/topsis_results.csv",
    "clusters": "results/kmeans_results.csv",
    "housing": "results/part2/housing_benchmark.csv",
    "fieldwork": "results/part2/fieldwork_shortlist.csv",
    "spatial": "results/part2/spatial_autocorrelation.csv",
}
SCHEMAS = {
    "spine": (*KEY_COLUMNS, *FEATURES, "geo_level", "scoring_eligible", "exclusion_reason",
              *(f"{feature}_{suffix}" for feature in FEATURES for suffix in ("year", "unit"))),
    "composite": (*KEY_COLUMNS, "composite_score", "rank"),
    "topsis": (*KEY_COLUMNS, "topsis_score", "rank", "distance_to_disadvantage_ideal",
               "distance_to_advantage_ideal"),
    "clusters": (*KEY_COLUMNS, *FEATURES, "cluster"),
    "housing": (*KEY_COLUMNS, "composite_score", *HOUSING_COLUMNS),
    "fieldwork": (*KEY_COLUMNS, *FEATURES, "composite_score", "composite_rank",
                  "topsis_score", "topsis_rank", "cluster", *VISIT_COLUMNS),
    "spatial": (*SPATIAL_NUMBERS, *(
        "year weights p_definition component_sizes sample_scores_sha256 crs software_versions "
        "centroids_sha256 weights_sha256 fingerprint_format geometry_validation permutation_caveat scope"
    ).split()),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    require(result.returncode == 0, result.stderr.decode(errors="replace").strip())
    return result.stdout


def read_csv(payload, table):
    path = INPUTS[table]
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig"), newline=""), strict=True)
    fields = reader.fieldnames or []
    require(len(fields) == len(SCHEMAS[table]) and set(fields) == set(SCHEMAS[table]),
            f"{path}: unexpected CSV columns")
    rows = []
    for row in reader:
        require(None not in row and None not in row.values(),
                f"{path}: malformed row at line {reader.line_num}")
        rows.append(row)
    return rows


def load_inputs(root):
    # Pin a single source tree while ignoring commits unrelated to these inputs.
    source_commit = git(root, "log", "-1", "--format=%H", "HEAD", "--", *INPUTS.values()).decode().strip()
    require(source_commit, "No Git commit found for the integration inputs")
    tables, hashes = {}, {}
    for table, path in INPUTS.items():
        saved = git(root, "show", f"{source_commit}:{path}")
        working = (root / path).read_bytes()
        require(working.replace(b"\r\n", b"\n") == saved.replace(b"\r\n", b"\n"),
                f"{path}: working copy differs from source Git commit {source_commit}")
        tables[table] = read_csv(saved, table)
        hashes[path] = sha256(saved).hexdigest()
    return tables, source_commit, hashes


def number(row, field, context, minimum=None, maximum=None):
    try:
        value = Decimal(row[field])
    except InvalidOperation:
        raise ValueError(f"{context}: {field} is not a number") from None
    require(value.is_finite(), f"{context}: {field} must be finite")
    require((minimum is None or value >= minimum) and (maximum is None or value <= maximum),
            f"{context}: {field} is outside its valid range")
    return value


def matches_number(row, field, saved, source_field, context):
    # The saved housing export and shortlist use different float serialization.
    actual = number(row, field, context)
    expected = number(saved, source_field, context)
    require(abs(actual - expected) <= Decimal("1e-15"),
            f"{context}: {field} disagrees with saved {source_field}")


def neighborhood_index(rows, table, count, spine=None):
    path = INPUTS[table]
    result = {}
    for row in rows:
        code, year = row["geo_code"], row["year"]
        key = (code, year)
        require(re.fullmatch(r"[0-9]{3}", code) and year == YEAR and row["geo_name"].strip(),
                f"{path}: invalid neighborhood identity {key}")
        require(key not in result, f"{path}: duplicate neighborhood key {key}")
        if spine is not None:
            require(key in spine, f"{path}: unmatched or ineligible neighborhood {key}")
            require(row["geo_name"] == spine[key]["geo_name"], f"{path}: name mismatch for {key}")
        result[key] = row
    require(len(result) == count, f"{path}: expected {count} rows, found {len(result)}")
    return result


def validate_spine(spine):
    eligible = {}
    for key, row in spine.items():
        context = f"spine {key}"
        require(row["geo_level"] == "Ortsteil", f"{context}: expected Ortsteil")
        missing = []
        for field in FEATURES:
            require(row[f"{field}_year"] == YEAR and row[f"{field}_unit"] == "%",
                    f"{context}: unexpected period or unit for {field}")
            if row[field] == "":
                missing.append(f"{field}:missing")
            else:
                number(row, field, context, 0, 100)
        require(row["scoring_eligible"] == str(not missing) and
                row["exclusion_reason"] == ";".join(missing),
                f"{context}: eligibility or reason disagrees with missing indicators")
        if not missing:
            eligible[key] = row
    require(len(eligible) == SCORED, f"spine: expected {SCORED} eligible rows, found {len(eligible)}")
    return eligible


def validate_ranking(rows, method):
    scores = [(number(row, f"{method}_score", f"{method} {key}", 0, 1), key)
              for key, row in rows.items()]
    last_score = None
    for position, (score, key) in enumerate(sorted(scores, reverse=True), start=1):
        if score != last_score:
            expected_rank = position
        row = rows[key]
        require(row["rank"] == str(expected_rank), f"{method} {key}: inconsistent saved rank")
        last_score = score
        if method == "topsis":
            for field in ("distance_to_disadvantage_ideal", "distance_to_advantage_ideal"):
                number(row, field, f"{method} {key}", 0)


def validate_neighborhood_evidence(eligible, composite, topsis, clusters, housing, visits):
    require({row["cluster"] for row in clusters.values()} == {"Profile A", "Profile B"},
            "K-means: expected both saved nominal profiles")
    housing_rho = set()
    for key, row in housing.items():
        context = f"housing {key}"
        matches_number(row, "composite_score", composite[key], "composite_score", context)
        require(number(row, HOUSING_COLUMNS[0], context) > 0, f"{context}: nonpositive floor area")
        rho = number(row, HOUSING_COLUMNS[1], context, -1, 1)
        omitted = number(row, HOUSING_COLUMNS[2], context, -1, 1)
        delta = number(row, HOUSING_COLUMNS[3], context, -2, 2)
        require(abs(omitted - rho - delta) <= Decimal("1e-15"), f"{context}: inconsistent rho change")
        housing_rho.add(rho)
        for field in FEATURES:
            matches_number(clusters[key], field, eligible[key], field, f"K-means {key}")
    require(len(housing_rho) == 1, "housing: inconsistent full-sample rho")

    priorities = set()
    for key, row in visits.items():
        context = f"fieldwork {key}"
        for field in FEATURES:
            matches_number(row, field, eligible[key], field, context)
        for method, ranking in (("composite", composite), ("topsis", topsis)):
            matches_number(row, f"{method}_score", ranking[key], f"{method}_score", context)
            require(row[f"{method}_rank"] == ranking[key]["rank"], f"{context}: {method} rank mismatch")
        require(row["cluster"] == clusters[key]["cluster"], f"{context}: cluster label mismatch")
        for field in VISIT_COLUMNS[:8]:
            number(row, field, context, 0, SCORED)
        priority = row["visit_priority"]
        require(priority in {"1", "2", "3", "4", "5"} and priority not in priorities,
                f"{context}: invalid or duplicate visit priority")
        priorities.add(priority)
        role = "recommended" if priority in {"1", "2", "3"} else "reserve"
        require(row["visit_role"] == role and row["fieldwork_status"] == "proposed_not_visited",
                f"{context}: unexpected fieldwork role or status")
        require(all(row[field].strip() for field in ("selection_criterion", "selection_reason", "sampling_scope")),
                f"{context}: missing fieldwork metadata")


def validate_spatial(rows, composite):
    require(len(rows) == 2 and {row["k"] for row in rows} == {"4", "6"},
            "spatial: expected one summary row for k=4 and one for k=6")
    for row in rows:
        context = f"spatial k={row['k']}"
        require(all(value.strip() for value in row.values()), f"{context}: missing summary field")
        require(row["year"] == YEAR and row["n"] == str(SCORED),
                f"{context}: unexpected year or sample size")
        for field in SPATIAL_NUMBERS:
            number(row, field, context)
        require(0 < number(row, "p_two_sided", context) <= 1, f"{context}: invalid p-value")
        for field in ("sample_scores_sha256", "centroids_sha256", "weights_sha256"):
            require(re.fullmatch(r"[0-9a-f]{64}", row[field]), f"{context}: malformed {field}")
    scores = csv_bytes([{"geo_code": key[0], "composite_score": composite[key]["composite_score"]}
                        for key in sorted(composite)])
    # The original pandas fingerprint used the platform's line endings.
    sample_hashes = {sha256(scores).hexdigest(), sha256(scores.replace(b"\n", b"\r\n")).hexdigest()}
    fingerprints = {row["sample_scores_sha256"] for row in rows}
    require(len(fingerprints) == 1 and fingerprints <= sample_hashes,
            "spatial: score sample fingerprint disagrees with the saved composite")
    return sorted(rows, key=lambda row: int(row["k"]))


def integrate(tables):
    spine = neighborhood_index(tables["spine"], "spine", AREAS)
    eligible = validate_spine(spine)
    composite, topsis, clusters, housing = (
        neighborhood_index(tables[name], name, SCORED, eligible)
        for name in ("composite", "topsis", "clusters", "housing")
    )
    visits = neighborhood_index(tables["fieldwork"], "fieldwork", VISITS, eligible)
    validate_ranking(composite, "composite")
    validate_ranking(topsis, "topsis")
    validate_neighborhood_evidence(eligible, composite, topsis, clusters, housing, visits)
    spatial = validate_spatial(tables["spatial"], composite)

    neighborhoods = []
    for key, row in sorted(spine.items()):
        joined = dict(row)
        for method, ranking in (("composite", composite), ("topsis", topsis)):
            saved = ranking.get(key, {})
            joined[f"{method}_score"] = saved.get(f"{method}_score", "")
            joined[f"{method}_rank"] = saved.get("rank", "")
        joined["cluster"] = clusters.get(key, {}).get("cluster", "")
        joined.update({field: housing.get(key, {}).get(field, "") for field in HOUSING_COLUMNS})
        joined.update({field: visits.get(key, {}).get(field, "") for field in VISIT_COLUMNS})
        neighborhoods.append(joined)
    return neighborhoods, spatial


def csv_bytes(rows):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def release_files(neighborhoods, spatial, source_commit, hashes):
    outputs = {"neighborhoods.csv": csv_bytes(neighborhoods),
               "spatial_summary.csv": csv_bytes(spatial)}
    manifest = {
        "release": RELEASE,
        "schema_version": 1,
        "year": int(YEAR),
        "source_git_commit": source_commit,
        "inputs_sha256": hashes,
        "outputs_sha256": {name: sha256(payload).hexdigest() for name, payload in outputs.items()},
        "row_counts": {
            "neighborhoods": len(neighborhoods),
            "eligible": sum(row["scoring_eligible"] == "True" for row in neighborhoods),
            "excluded": sum(row["scoring_eligible"] == "False" for row in neighborhoods),
            "housing_benchmark": sum(bool(row[HOUSING_COLUMNS[0]]) for row in neighborhoods),
            "fieldwork_candidates": sum(bool(row["fieldwork_status"]) for row in neighborhoods),
            "spatial_summary": len(spatial),
        },
    }
    outputs["manifest.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    return outputs


def publish(destination, outputs):
    require(not destination.is_symlink(), f"Release path is a symbolic link: {destination}")
    if destination.exists():
        require(destination.is_dir() and {p.name for p in destination.iterdir()} == set(outputs) and
                all((destination / name).is_file() and not (destination / name).is_symlink() and
                    (destination / name).read_bytes() == payload for name, payload in outputs.items()),
                f"Existing release differs; choose a new release version: {destination}")
        return "Verified existing"

    destination.parent.mkdir(parents=True, exist_ok=True)
    # A direct sibling inherits the release parent's Windows ACL before rename.
    staging = destination.with_name(f".{destination.name}-{uuid4().hex}.tmp")
    staging.mkdir()
    try:
        for name, payload in outputs.items():
            (staging / name).write_bytes(payload)
        staging.rename(destination)
    except BaseException:
        for name in outputs:
            (staging / name).unlink(missing_ok=True)
        staging.rmdir()
        raise
    return "Created"


def main():
    tables, commit, hashes = load_inputs(ROOT)
    neighborhoods, spatial = integrate(tables)
    outputs = release_files(neighborhoods, spatial, commit, hashes)
    destination = HERE / "releases" / RELEASE
    status = publish(destination, outputs)
    counts = json.loads(outputs["manifest.json"])["row_counts"]
    print(f"{status} {destination.relative_to(ROOT).as_posix()} from {commit}")
    print("Validated " + ", ".join(f"{label}={count}" for label, count in counts.items()))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, csv.Error) as error:
        raise SystemExit(f"Integration failed: {error}") from None
