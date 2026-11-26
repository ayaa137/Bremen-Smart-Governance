"""Validate benchmark inputs, run three local feasibility probes, and rescore the matrix."""

import argparse
from contextlib import closing
import csv
from decimal import Decimal
from hashlib import sha256
from html import escape
from importlib import metadata, util
import json
from pathlib import Path
import platform
import sqlite3
import struct
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET


HERE = Path(__file__).resolve().parent
RELEASE = HERE / "releases" / "2024-v1"
PNG = HERE.parents[1] / "figures" / "part2" / "housing_benchmark.png"
PROFILES = {
    "Prototype": "prototype_weight_pct",
    "Equal weight": None,
    "Interaction stress": "interaction_stress_weight_pct",
    "API and scale stress": "api_scale_stress_weight_pct",
}


def check(condition, message):
    if not condition:
        raise ValueError(message)


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_release():
    manifest = json.loads((RELEASE / "manifest.json").read_text(encoding="utf-8"))
    for filename, expected in manifest["outputs_sha256"].items():
        actual = sha256((RELEASE / filename).read_bytes()).hexdigest()
        check(actual == expected, f"Release hash mismatch for {filename}")
    neighborhoods = read_csv(RELEASE / "neighborhoods.csv")
    spatial = read_csv(RELEASE / "spatial_summary.csv")
    keys = {(row["geo_code"], row["year"]) for row in neighborhoods}
    counts = {
        "neighborhoods": len(neighborhoods),
        "eligible": sum(row["scoring_eligible"] == "True" for row in neighborhoods),
        "excluded": sum(bool(row["exclusion_reason"]) for row in neighborhoods),
        "housing_benchmark": sum(bool(row["floor_area_m2_per_resident"]) for row in neighborhoods),
        "fieldwork_candidates": sum(row["fieldwork_status"] == "proposed_not_visited"
                                    for row in neighborhoods),
        "spatial_summary": len(spatial),
    }
    check(len(keys) == len(neighborhoods) and counts == manifest["row_counts"] and
          {row["k"] for row in spatial} == {"4", "6"} and "morans_i" not in neighborhoods[0],
          "Unexpected release counts, keys, or spatial scope")
    assets = [RELEASE / name for name in ("neighborhoods.csv", "spatial_summary.csv", "manifest.json")]
    print(f"Release {manifest['release']} {manifest['source_git_commit']}: {counts}")
    print("Input artifact sizes (bytes): " +
          ", ".join(f"{path.name}={path.stat().st_size}" for path in [*assets, PNG]))
    return neighborhoods


def display_rank(row):
    return row["composite_rank"] or "Missing"


def static_probe(rows):
    def render():
        cells = "".join(
            f'<tr><th scope="row">{escape(row["geo_code"])}</th>'
            f'<td>{escape(row["geo_name"])}</td><td>{escape(display_rank(row))}</td></tr>'
            for row in rows
        )
        return ('<table><caption>2024 Bremen neighborhoods</caption><thead><tr>'
                '<th scope="col">Code</th><th scope="col">Neighborhood</th>'
                '<th scope="col">Composite rank</th></tr></thead>'
                f'<tbody>{cells}</tbody></table>').encode("utf-8")

    fragment = render()
    table = ET.fromstring(fragment)
    saved = [[row["geo_code"], row["geo_name"], display_rank(row)] for row in rows]
    roundtrip = [[cell.text for cell in row] for row in table.findall("./tbody/tr")]
    check(fragment == render() and saved == roundtrip and table.find("caption") is not None and
          all(cell.attrib.get("scope") == "col" for cell in table.findall("./thead/tr/th")),
          "Static table content, header structure, or deterministic build failed")
    png = PNG.read_bytes()
    check(png[:8] == b"\x89PNG\r\n\x1a\n" and png[12:16] == b"IHDR", "Invalid housing PNG header")
    width, height = struct.unpack(">II", png[16:24])
    check(width > 0 and height > 0, "Invalid housing PNG dimensions")
    print(f"A PASS: {len(roundtrip)} table rows, {len(fragment)} UTF-8 bytes, "
          f"identical on two builds, housing PNG header {width}x{height}")


def streamlit_probe(rows):
    if util.find_spec("streamlit") is None:
        print("B SKIP: Streamlit is unavailable in this Python environment")
        return
    from streamlit.testing.v1 import AppTest

    sample = {row["geo_code"]: display_rank(row) for row in rows}
    eligible = next(code for code, rank in sample.items() if rank != "Missing")
    excluded = next(code for code, rank in sample.items() if rank == "Missing")
    program = f"""import csv
import streamlit as st
with open({str(RELEASE / 'neighborhoods.csv')!r}, encoding="utf-8-sig", newline="") as data:
    ranks = {{row["geo_code"]: row["composite_rank"] or "Missing" for row in csv.DictReader(data)}}
code = st.selectbox("Neighborhood code", list(ranks))
st.text(ranks[code])
"""
    with TemporaryDirectory(prefix="bremen-streamlit-probe-") as temporary:
        script = Path(temporary) / "probe.py"
        script.write_text(program, encoding="utf-8")
        app = AppTest.from_file(str(script)).run()
        check(not app.exception and len(app.selectbox[0].options) == len(rows),
              "Streamlit selector did not load the saved rows")
        for code in (eligible, excluded):
            app.selectbox[0].select(code).run()
            check(not app.exception and app.text[0].value == sample[code],
                  f"Streamlit rank display differed for {code}")
    print(f"B PASS: Streamlit {metadata.version('streamlit')} AppTest, {len(sample)} choices, "
          f"{eligible}={sample[eligible]}, {excluded}={sample[excluded]}")


def database_probe(rows):
    fields = [(row["geo_code"], row["year"],
               int(row["composite_rank"]) if row["composite_rank"] else None,
               row["exclusion_reason"] or None) for row in rows]
    excluded = next(row for row in fields if row[2] is None)
    with closing(sqlite3.connect(":memory:")) as db:
        db.execute("CREATE TABLE neighborhood (code TEXT, year TEXT, rank INTEGER, reason TEXT, "
                   "PRIMARY KEY (code, year))")
        db.executemany("INSERT INTO neighborhood VALUES (?, ?, ?, ?)", fields)
        result = db.execute("SELECT * FROM neighborhood ORDER BY code, year").fetchall()
        check(result == sorted(fields), "Database rows differed from saved release")
        rank, reason = db.execute("SELECT rank, reason FROM neighborhood WHERE code=? AND year=?",
                                  excluded[:2]).fetchone()
        record = json.loads(json.dumps({"geo_code": excluded[0], "rank": rank, "reason": reason}))
        check((record["geo_code"], record["rank"], record["reason"]) ==
              (excluded[0], excluded[2], excluded[3]), "JSON changed missingness or identifier")
        try:
            db.execute("INSERT INTO neighborhood VALUES (?, ?, ?, ?)", excluded)
        except sqlite3.IntegrityError:
            pass
        else:
            raise ValueError("Database accepted a duplicate neighborhood and year")
    print(f"C PARTIAL PASS: SQLite {sqlite3.sqlite_version}, {len(result)} rows, "
          "keyed lookup preserved JSON null and exclusion reason, duplicate key rejected")


def score_matrix():
    matrix = read_csv(HERE / "technical_benchmark_matrix.csv")
    check(len(matrix) == len({row["criterion"] for row in matrix}) == 12,
          "Expected 12 unique criteria")
    ratings = {option: [int(row[f"{option}_score"]) for row in matrix] for option in "abc"}
    check(all(1 <= score <= 5 for values in ratings.values() for score in values),
          "Matrix scores must be between 1 and 5")
    for profile, field in PROFILES.items():
        weights = [int(row[field]) for row in matrix] if field else [1] * len(matrix)
        check(all(weight > 0 for weight in weights) and (not field or sum(weights) == 100),
              f"Invalid weights for {profile}")
        scores = {option: Decimal(sum(w * s for w, s in zip(weights, values))) / sum(weights)
                  for option, values in ratings.items()}
        print(f"{profile}: " + ", ".join(f"{option.upper()}={score:.2f}" for option, score in scores.items()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-streamlit", action="store_true", help="Run standard-library checks only.")
    args = parser.parse_args()
    print(f"Python {platform.python_version()}, {platform.system()} {platform.release()}")
    rows = load_release()
    static_probe(rows)
    if args.skip_streamlit:
        print("B SKIP: excluded by --skip-streamlit")
    else:
        streamlit_probe(rows)
    database_probe(rows)
    score_matrix()


if __name__ == "__main__":
    main()
