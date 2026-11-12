"""Global Moran's I of saved 2024 scores; no causal or fieldwork inference.

From the repository root: python -B analysis/part2/spatial_autocorrelation.py
Two-sided p = (1 + count(|I_perm - E[I]| >= |I_obs - E[I]|)) / 10000,
where E[I] = -1/(n-1). Conditional on fixed scores, sample and spatial weights.
P-values are Monte Carlo estimates with simulation uncertainty; minimum 0.0001
for 9999 permutations. Centroid/area checks do not certify full polygon topology,
overlaps or hole containment.
"""
from hashlib import sha256
from io import StringIO
from itertools import permutations
from pathlib import Path
import platform
import sys
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import scipy
from scipy.sparse.csgraph import connected_components
from scipy.spatial.distance import cdist

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from build_section2_atlas import NS, PINS, parse_geometry, require

ATLAS = ROOT / "reports/section2_v2/atlas"
SEED, PERMUTATIONS = 2024, 9999


def read(path):
    return pd.read_csv(ROOT / path, dtype={"geo_code": str, "official_code": str},
                       float_precision="round_trip")


def centroid(parts):
    """Signed shoelace areas: add exteriors, subtract holes, combine all parts."""
    area, moment = 0.0, np.zeros(2)
    for rings in parts:
        for index, ring in enumerate(rings):
            origin = ring[0]
            q = ring - origin  # local coordinates avoid large-coordinate cancellation
            cross = q[:-1, 0] * q[1:, 1] - q[1:, 0] * q[:-1, 1]
            signed_area = cross.sum() / 2
            require(signed_area != 0 and (signed_area > 0) == (index == 0),
                    "Invalid exterior/hole orientation")
            center = ((q[:-1] + q[1:]) * cross[:, None]).sum(axis=0) / (6 * signed_area) + origin
            # Independent signed triangle-moment calculation.
            triangles = (q[:-1] + q[1:]) / 3 + origin
            np.testing.assert_allclose(center, (triangles * cross[:, None]).sum(axis=0) / cross.sum(),
                                       atol=1e-8, rtol=0)
            area += signed_area
            moment += signed_area * center
    require(area > 0 and np.isfinite(moment / area).all(), "Invalid centroid/area")
    return area, moment / area


def geometry():
    features = {}
    for filename, layer, key in [
        ("ortsteile_bremen_epsg25832.gml", "Ortsteile_Bremen", "sch_ot"),
        ("stadtteile_bremen_epsg25832.gml", "Stadtteile_Bremen", "sch_st"),
    ]:
        path = ATLAS / "sources" / filename
        require(sha256(path.read_bytes()).hexdigest() == PINS[filename], "Boundary hash mismatch")
        members = ET.parse(path).findall("wfs:member/app:" + layer, NS)
        require(len(members) == (87 if key == "sch_ot" else 19), "Unexpected boundary feature count")
        for feature in members:
            official = feature.find("app:" + key, NS).text
            if key == "sch_st" and official != "04011360":
                continue
            code = official[-3:] if key == "sch_ot" else "361"
            require(code not in features, "Duplicate geographic code")
            require(feature.find("app:sch_ks", NS).text == "04011000", "Wrong municipality")
            if key == "sch_ot":
                require(feature.find("app:sch_ot_ags", NS).text == "040110000" + code,
                        "Official code fields disagree")
            features[code] = (official, feature)
    lookup = read("reports/section2_v2/atlas/geographic_join_validation.csv")
    require(len(lookup) == 88 and lookup.geo_code.is_unique and
            set(lookup.geo_code) == set(features), "Boundary lookup mismatch")
    rows = []
    max_error = 0.0
    for row in lookup.itertuples():
        official, feature = features[row.geo_code]
        require(official == row.official_code and row.crs == "EPSG:25832", "Mapping/CRS mismatch")
        require(feature.find("app:" + ("bez_ot" if row.geo_code != "361" else "bez_st"), NS).text == row.boundary_name, "Boundary name mismatch")
        parts = parse_geometry(feature)  # existing ring/CRS/finite-coordinate checks
        require(len(parts) == row.geometry_parts and sum(map(len, parts)) == row.geometry_rings,
                "Part/ring count mismatch")
        area, center = centroid(parts)
        error = abs(area / 1e6 - row.official_area_km2)
        max_error = max(max_error, error)
        require(error < 1e-7 and abs(area / 1e6 - row.coordinate_area_km2) < 1e-7,
                "Official/recorded area mismatch")
        rows.append((row.geo_code, row.geo_name, *center))
    return pd.DataFrame(rows, columns=["geo_code", "geo_name", "x_m", "y_m"]), max_error


def moran(values, weights):
    z = np.asarray(values, dtype=float) - np.mean(values)
    require(np.isfinite(z).all() and z @ z > 0, "Scores must be finite and nonconstant")
    return len(z) / weights.sum() * (z @ weights @ z) / (z @ z)


def self_test():
    square = np.array([[0., 0.], [4., 0.], [4., 4.], [0., 4.], [0., 0.]])
    hole = np.array([[.5, .5], [.5, 1.5], [1.5, 1.5], [1.5, .5], [.5, .5]])
    other = np.array([[10., 0.], [12., 0.], [12., 2.], [10., 2.], [10., 0.]])
    area, center = centroid([[square, hole], [other]])
    np.testing.assert_allclose(area, 19)
    np.testing.assert_allclose(center, [75 / 19, 35 / 19])
    weights = np.array([[0., 1., 0.], [.5, 0., .5], [0., 1., 0.]])
    x = np.array([0., 1., 3.])
    z = x - x.mean()
    numerator = sum(weights[i, j] * z[i] * z[j] for i in range(3) for j in range(3))
    independent = 3 / weights.sum() * numerator / sum(v * v for v in z)
    np.testing.assert_allclose(moran(x, weights), independent)
    np.testing.assert_allclose(moran([1., 3.], np.array([[0., 1.], [1., 0.]])), -1)
    exact_null = [moran(np.array(p), weights) for p in permutations(x)]
    np.testing.assert_allclose(np.mean(exact_null), -.5)


def calculate():
    self_test()
    centers, area_error = geometry()
    base = read("data/processed/ortsteil_analysis_ready.csv")
    geo = read("data/processed/geography_lookup.csv")
    require(geo.geo_code.is_unique, "Duplicate master lookup codes")
    geo = geo.loc[geo.geo_level.eq("Ortsteil")].copy()  # exclude city/district aggregates
    scores = read("results/composite_index_results.csv")
    for frame, n in [(base, 88), (geo, 88), (scores, 79)]:
        require(len(frame) == n and frame.geo_code.is_unique and
                frame.geo_code.str.fullmatch(r"\d{3}").all(), "Invalid geographic keys")
    eligible = base[["unemployment", "employment", "benefit_receipt"]].notna().all(axis=1)
    require(eligible.equals(base.scoring_eligible) and eligible.sum() == 79, "Eligibility mismatch")
    require(base.year.eq(2024).all() and scores.year.eq(2024).all(), "Wrong reporting year")
    master = base[["geo_code", "geo_name"]].merge(geo[["geo_code", "geo_name"]],
                on=["geo_code", "geo_name"], validate="one_to_one", how="inner")
    require(len(master) == 88 and set(scores.geo_code) == set(base.loc[eligible, "geo_code"]),
            "Lookup/sample mismatch")
    sample = scores.merge(master, on=["geo_code", "geo_name"], validate="one_to_one")
    sample = sample.merge(centers, on=["geo_code", "geo_name"], validate="one_to_one")
    sample = sample.sort_values("geo_code").reset_index(drop=True)
    require(len(sample) == 79 and not sample.isna().any().any(), "Incomplete spatial join")
    values = sample.composite_score.to_numpy()
    require(np.isfinite(values).all() and sample.composite_score.between(0, 1).all(),
            "Invalid saved scores")
    xy = sample[["x_m", "y_m"]].to_numpy()
    distances = cdist(xy, xy)
    np.fill_diagonal(distances, np.inf)
    require((distances > 0).all() and np.isfinite(xy).all(), "Coincident/invalid centroids")
    z = values - values.mean()
    rng = np.random.default_rng(SEED)
    shuffled = np.array([rng.permutation(z) for _ in range(PERMUTATIONS)])
    expected = -1 / (len(sample) - 1)
    sample_hash = sha256(sample[["geo_code", "composite_score"]].to_csv(index=False).encode()).hexdigest()
    code_order = (";".join(sample.geo_code) + "\0").encode("ascii")
    centroid_hash = sha256(code_order + xy.astype("<f8").tobytes(order="C")).hexdigest()
    versions = f"Python={platform.python_version()};numpy={np.__version__};pandas={pd.__version__};scipy={scipy.__version__}"
    results = []
    for k in [4, 6]:
        directed = np.zeros(distances.shape, dtype=bool)
        # Code-sorted rows + stable sort resolve equal distances deterministically.
        nearest = np.argsort(distances, axis=1, kind="stable")[:, :k]
        directed[np.arange(len(sample))[:, None], nearest] = True
        adjacency = directed | directed.T
        degree = adjacency.sum(axis=1)
        require(np.all(degree >= k) and not np.diag(adjacency).any() and
                np.array_equal(adjacency, adjacency.T), "Invalid symmetrized graph")
        weights = adjacency / degree[:, None]
        require(np.isfinite(weights).all() and (weights >= 0).all(), "Invalid weights")
        np.testing.assert_allclose(weights.sum(axis=1), 1)
        observed = moran(values, weights)
        null = len(z) / weights.sum() * ((shuffled @ weights) * shuffled).sum(axis=1) / (z @ z)
        # Independent scalar checks for the vectorized permutation calculation.
        for i in range(3):
            np.testing.assert_allclose(null[i], moran(shuffled[i], weights), atol=1e-14)
        require(np.isfinite(null).all(), "Invalid permutation statistics")
        extreme = int((np.abs(null - expected) >= abs(observed - expected)).sum())
        components, labels = connected_components(adjacency, directed=False)
        links = distances[np.triu(adjacency, 1)]
        results.append(dict(
            k=k, n=79, year=2024, weights="symmetrized_knn_row_standardized",
            morans_i=observed, theoretical_null_expectation=expected,
            permutation_null_mean=null.mean(), p_two_sided=(extreme + 1) / (PERMUTATIONS + 1),
            extreme_permutations=extreme, permutations=PERMUTATIONS, seed=SEED,
            p_definition="absolute deviation from -1/(n-1), plus-one correction",
            components=components, component_sizes=";".join(map(str, sorted(np.bincount(labels), reverse=True))),
            isolates=int((degree == 0).sum()), undirected_edges=len(links),
            degree_min=int(degree.min()), degree_mean=degree.mean(), degree_max=int(degree.max()),
            link_distance_min_m=links.min(), link_distance_median_m=np.median(links),
            link_distance_mean_m=links.mean(), link_distance_max_m=links.max(),
            max_area_error_km2=area_error, sample_scores_sha256=sample_hash,
            crs="EPSG:25832", software_versions=versions,
            centroids_sha256=centroid_hash,
            weights_sha256=sha256(code_order + weights.astype("<f8").tobytes(order="C")).hexdigest(),
            fingerprint_format="ASCII semicolon-separated code order + NUL + row-major little-endian float64; centroids x/y metres or row-standardized W",
            geometry_validation="Centroid moments and areas checked; full polygon topology, overlaps and hole containment unverified",
            p_minimum=1 / (PERMUTATIONS + 1),
            permutation_caveat="Monte Carlo p-value estimate; minimum 0.0001 at 9999 permutations; simulation uncertainty remains",
            scope="Conditional on 79 complete-case 2024 areas and chosen weights; no causal, accessibility or fieldwork validation"))
    output = pd.DataFrame(results)
    require(len(output) == 2 and not output.isna().any().any() and
            output.p_two_sided.between(1 / 10000, 1).all(), "Invalid results")
    return output


def main():
    output = calculate()
    repeated = calculate()
    pd.testing.assert_frame_equal(output, repeated, check_exact=True)
    content = output.to_csv(index=False, lineterminator="\n")
    pd.testing.assert_frame_equal(output, pd.read_csv(StringIO(content), dtype={"component_sizes": str}, float_precision="round_trip"), check_dtype=False)
    path = ROOT / "results/part2/spatial_autocorrelation.csv"
    payload = content.encode("utf-8")
    require(not path.exists() or path.read_bytes() == payload,
            "Existing results differ; review required before replacement")
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    print(output.to_string(index=False))
    print("PASS: centroid/area calculations (not full topology), unique joins, weights, independent formula tests, "
          "9999 permutations, exact two-run reproducibility; all checks before publication")


if __name__ == "__main__":
    main()
