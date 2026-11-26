"""Build the self-contained Bremen dashboard from the verified 2024-v1 release."""

from base64 import b64encode
import csv
from decimal import Decimal
from hashlib import sha256
from html import escape
import io
import json
from pathlib import Path
import re
from string import Template
from uuid import uuid4


HERE = Path(__file__).resolve().parent
RELEASE = HERE / "releases" / "2024-v1"
FIGURE = HERE.parents[1] / "figures" / "part2" / "housing_benchmark.png"
FIGURE_SHA256 = "0f9e73737062b0073fab77080460a6c605789bd155c5654aa89ceacaa3f5ce34"
OUTPUT = HERE / "prototype" / "index.html"
YEAR = "2024"
COUNTS = {"neighborhoods": 88, "eligible": 79, "excluded": 9, "housing_benchmark": 79,
          "fieldwork_candidates": 5, "spatial_summary": 2}
INDICATORS = {
    "unemployment": ("Unemployment quotient", "Registered unemployed divided by registered unemployed plus employees covered by social insurance. The denominator differs from the conventional unemployment rate."),
    "employment": ("Social-insurance employment", "Residents in social-insurance employment divided by residents aged 15 to under 65. It excludes self-employment and civil servants."),
    "benefit_receipt": ("SGB II receipt", "People eligible for SGB II benefits divided by residents under 65. It measures benefit receipt; unmet need can extend beyond this group."),
}
SCORES = ("composite_score", "composite_rank", "topsis_score", "topsis_rank", "cluster")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def checked_bytes(path, expected):
    payload = path.read_bytes()
    require(sha256(payload).hexdigest() == expected, f"SHA-256 mismatch for {path.name}")
    return payload


def csv_rows(payload):
    return list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"), newline=""), strict=True))


def load_release(directory):
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    hashes = manifest["outputs_sha256"]
    require(manifest["release"] == "2024-v1" and manifest["year"] == int(YEAR) and
            manifest["schema_version"] == 1 and manifest["row_counts"] == COUNTS and
            re.fullmatch(r"[0-9a-f]{40}", manifest["source_git_commit"]) and
            set(hashes) == {"neighborhoods.csv", "spatial_summary.csv"}, "Unexpected release manifest")
    neighborhoods = csv_rows(checked_bytes(directory / "neighborhoods.csv", hashes["neighborhoods.csv"]))
    spatial = csv_rows(checked_bytes(directory / "spatial_summary.csv", hashes["spatial_summary.csv"]))

    keys = {row["geo_code"] for row in neighborhoods}
    require(len(keys) == len(neighborhoods) == COUNTS["neighborhoods"] and
            all(re.fullmatch(r"[0-9]{3}", row["geo_code"]) and row["year"] == YEAR and
                row["scoring_eligible"] in {"True", "False"} for row in neighborhoods),
            "Unexpected neighborhood identities, dates, or eligibility flags")
    eligible = [row for row in neighborhoods if row["scoring_eligible"] == "True"]
    excluded = [row for row in neighborhoods if row["scoring_eligible"] == "False"]
    require(len(eligible) == COUNTS["eligible"] and len(excluded) == COUNTS["excluded"] and
            all(all(row[key] for key in (*INDICATORS, *SCORES, "floor_area_m2_per_resident")) and
                not row["exclusion_reason"] for row in eligible) and
            all(not any(row[key] for key in (*SCORES, "floor_area_m2_per_resident")) and
                row["exclusion_reason"] for row in excluded), "Unexpected scoring or exclusion coverage")
    visits = [row for row in neighborhoods if row["fieldwork_status"]]
    require(len(visits) == COUNTS["fieldwork_candidates"] and
            {row["visit_priority"] for row in visits} == {"1", "2", "3", "4", "5"} and
            all(row["fieldwork_status"] == "proposed_not_visited" for row in visits),
            "Unexpected fieldwork candidates or visit status")
    require(len(spatial) == COUNTS["spatial_summary"] and {row["k"] for row in spatial} == {"4", "6"} and
            all(row["year"] == YEAR and row["n"] == str(COUNTS["eligible"]) for row in spatial) and
            "morans_i" not in neighborhoods[0], "Unexpected spatial summary coverage or grain")
    return manifest, neighborhoods, spatial


def display_value(row, key, places=None, unit=""):
    raw = row[key]
    if not raw:
        return '<span class="missing" data-missing="true">Unavailable</span>'
    text = format(Decimal(raw), f".{places}f") if places is not None else raw
    return f'<span data-saved="{escape(raw)}">{escape(text + unit)}</span>'


def reason(row):
    return ", ".join(INDICATORS[item.split(":")[0]][0] for item in row["exclusion_reason"].split(";"))


def neighborhood_label(row):
    return f'{escape(row["geo_name"])} <span class="code">{escape(row["geo_code"])}</span>'


def status(row):
    if row["scoring_eligible"] == "True":
        return '<span class="status scored">Scored</span>'
    return '<span class="status excluded">Excluded</span>'


def table_row(row):
    code = escape(row["geo_code"])
    return (f'<tr data-code="{code}" data-name="{escape(row["geo_name"])}" '
            f'data-eligible="{row["scoring_eligible"]}"><th scope="row">'
            f'<a href="#ortsteil-{code}" data-neighborhood="{code}">{escape(row["geo_name"])}</a>'
            f'</th><td class="code">{code}</td><td>{status(row)}</td></tr>')


def detail_panel(row):
    code = escape(row["geo_code"])
    measures = "".join(f'<div><dt>{label}</dt><dd data-field="{key}">'
                       f'{display_value(row, key, 4, "%")}</dd></div>'
                       for key, (label, _) in INDICATORS.items())
    note = (f'      <p class="notice exclusion-note"><strong>Scoring exclusion.</strong> Missing source '
            f'indicators: {escape(reason(row))}. Available source values are shown below.</p>\n'
            if row["exclusion_reason"] else "")
    ranks = "".join(
        f'<div class="readout"><dt>{label}</dt><dd data-field="{key}_score">'
        f'{display_value(row, key + "_score", 4)}</dd><dd class="rank" data-field="{key}_rank">'
        f'<span>Rank</span> {display_value(row, key + "_rank")}</dd></div>'
        for key, label in (("composite", "Composite Index"), ("topsis", "TOPSIS"))
    )
    return f"""<article class="detail" id="ortsteil-{code}" aria-labelledby="heading-{code}">
      <div class="detail-title">
        <div><h3 id="heading-{code}" tabindex="-1">{escape(row["geo_name"])}</h3>
          <p class="detail-meta">Ortsteil {code} · {YEAR}</p></div>
        {status(row)}
      </div>
{note}      <h4>Socioeconomic indicators</h4><dl class="measures">{measures}</dl>
      <h4>Saved analytical results</h4><dl class="rank-grid">{ranks}</dl>
      <dl class="context"><div><dt>K-means profile</dt><dd data-field="cluster">{display_value(row, "cluster")}</dd></div>
        <div><dt>Housing floor area per resident</dt>
          <dd data-field="floor_area_m2_per_resident">{display_value(row, "floor_area_m2_per_resident", 2, " m²")}</dd></div></dl>
      <p class="detail-foot">Rank 1 indicates the highest measured disadvantage in the scored sample.
        K-means profiles are nominal. <a href="#definitions">Indicator definitions</a></p>
    </article>"""


def fieldwork_row(row):
    code = escape(row["geo_code"])
    return (f'<tr class="fieldwork-row"><th scope="row">{escape(row["visit_priority"])}</th>'
            f'<td><a href="#ortsteil-{code}" data-neighborhood="{code}">{neighborhood_label(row)}</a></td>'
            f'<td>{escape(row["visit_role"].capitalize())}</td><td>{escape(row["selection_reason"])}</td>'
            f'<td><code>{escape(row["fieldwork_status"])}</code></td></tr>')


def spatial_row(row):
    return (f'<tr><th scope="row">{escape(row["k"])}</th><td>{escape(row["n"])}</td>'
            f'<td>{display_value(row, "morans_i", 6)}</td>'
            f'<td>{display_value(row, "p_two_sided", 4)}</td>'
            f'<td>{escape(row["permutations"])}</td></tr>')


def build_page(directory=RELEASE, figure=FIGURE):
    manifest, neighborhoods, spatial = load_release(directory)
    picture = b64encode(checked_bytes(figure, FIGURE_SHA256)).decode("ascii")
    template = Template((HERE / "dashboard_template.html").read_text(encoding="utf-8"))
    rows = sorted(neighborhoods, key=lambda row: row["geo_code"])
    candidates = sorted((row for row in rows if row["fieldwork_status"]), key=lambda row: int(row["visit_priority"]))
    excluded = (row for row in rows if row["exclusion_reason"])
    definitions = (f'<div><dt>{label}</dt><dd>{definition}</dd></div>'
                   for label, definition in INDICATORS.values())
    housing = next(row for row in rows if row["floor_area_m2_per_resident"])
    hashes = manifest["outputs_sha256"]
    html = template.substitute(
        year=YEAR, release=manifest["release"], source_commit=manifest["source_git_commit"],
        represented=COUNTS["neighborhoods"], scored=COUNTS["eligible"], excluded=COUNTS["excluded"],
        table_rows="".join(map(table_row, rows)), panels="\n".join(map(detail_panel, rows)),
        exclusion_rows="".join(f'<li><a href="#ortsteil-{row["geo_code"]}" data-neighborhood="{row["geo_code"]}">'
                               f'{neighborhood_label(row)}</a><span>{escape(reason(row))}</span></li>'
                               for row in excluded),
        definitions="".join(definitions), fieldwork_rows="".join(map(fieldwork_row, candidates)),
        spatial_rows="".join(map(spatial_row, sorted(spatial, key=lambda row: int(row["k"])))),
        spatial_seed=escape(spatial[0]["seed"]), housing_png=picture,
        housing_rho=display_value(housing, "full_sample_spearman_rho", 4),
        neighborhoods_hash=hashes["neighborhoods.csv"], spatial_hash=hashes["spatial_summary.csv"],
        housing_hash=FIGURE_SHA256,
    )
    return html.encode("utf-8")


def main():
    try:
        html = build_page()
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        # Stage beside the output so a Windows browser can inherit the workspace ACL.
        staged = OUTPUT.with_name(f".{OUTPUT.name}-{uuid4().hex}.tmp")
        stream = staged.open("xb")
        try:
            with stream:
                stream.write(html)
            staged.replace(OUTPUT)
        finally:
            staged.unlink(missing_ok=True)
    except (OSError, ValueError, KeyError, csv.Error, ArithmeticError) as error:
        raise SystemExit(f"Dashboard build failed: {error}") from None
    print(f"Built {OUTPUT.relative_to(HERE.parents[1]).as_posix()} ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
