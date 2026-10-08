from __future__ import annotations

import csv
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
CSV_ENCODING = "cp1252"
CSV_DELIMITER = ";"


MISSING_MARKERS = {
    "",
    "-",
    ".",
    "..",
    "...",
    "NA",
    "N/A",
    "n/a",
    "k.A.",
    "k. A.",
    "keine Angabe",
}


@dataclass(frozen=True)
class ParsedValue:
    raw_value: str
    value: float | None
    value_status: str


def clean_text(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    text = str(value).replace("\xa0", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return unicodedata.normalize("NFC", text)


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_value = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_value.lower()).strip("_")
    return ascii_value or "unknown"


def parse_number(value: Any, decimal_comma: bool) -> ParsedValue:
    raw = clean_text(value)
    if raw in MISSING_MARKERS:
        return ParsedValue(raw, None, "missing")

    candidate = raw
    if decimal_comma:
        candidate = candidate.replace(".", "").replace(",", ".")
    else:
        candidate = candidate.replace(",", "")

    try:
        return ParsedValue(raw, float(candidate), "ok")
    except ValueError:
        return ParsedValue(raw, None, "invalid_or_suppressed")


def extract_years(text: str) -> list[int]:
    return [int(year) for year in re.findall(r"\b(19\d{2}|20\d{2})\b", text)]


def parse_reporting_period(value: Any) -> tuple[int | None, int | None, str]:
    text = clean_text(value)
    if not text:
        return None, None, ""
    years = extract_years(text)
    if years:
        if len(years) == 1:
            return years[0], years[0], str(years[0])
        return years[0], years[-1], f"{years[0]}-{years[-1]}"
    try:
        year = int(float(text))
        if 1900 <= year <= 2100:
            return year, year, str(year)
    except ValueError:
        pass
    return None, None, text


def infer_unit(text: str) -> str:
    if "%" in text:
        return "%"
    match = re.search(r"\(([^()]*)\)\s*$", text)
    if match:
        return clean_text(match.group(1))
    if re.search(r"\bJahre?\b", text):
        return "Jahre"
    if re.search(r"\bje\s+\d+", text):
        return "rate"
    return ""


def normalize_geo_name(name: str) -> str:
    return clean_text(re.sub(r"^Stadtteil\s+", "", name))


def geo_level_from_code_name(code: str, name: str) -> str:
    clean_name = clean_text(name)
    clean_code = clean_text(code)
    if clean_name == "Stadt Bremen":
        return "Stadt"
    if clean_name.startswith("Stadtbezirk") or clean_code in {"1", "2", "3", "4", "5"}:
        return "Stadtbezirk"
    if clean_name.startswith("Stadtteil") or (clean_code.isdigit() and len(clean_code) == 2):
        return "Stadtteil"
    if clean_code.isdigit() and len(clean_code) == 3:
        return "Ortsteil"
    return "unknown"


def read_csv_source(path: Path) -> pd.DataFrame:
    return pd.read_csv(
        path,
        sep=CSV_DELIMITER,
        encoding=CSV_ENCODING,
        dtype=str,
        keep_default_na=False,
        engine="python",
    )


def build_excel_geography_lookup(workbook: pd.ExcelFile) -> pd.DataFrame:
    first_sheet = workbook.sheet_names[0]
    df = pd.read_excel(workbook, sheet_name=first_sheet, header=None, dtype=object)
    rows: list[dict[str, Any]] = []
    for _, row in df.iloc[3:].iterrows():
        code = clean_text(row.iloc[0])
        name = clean_text(row.iloc[1])
        if not name:
            continue
        level = geo_level_from_code_name(code, name)
        rows.append(
            {
                "geo_code": code,
                "geo_name": normalize_geo_name(name) if level in {"Stadtteil", "Stadtbezirk"} else name,
                "geo_label": name,
                "geo_level": level,
            }
        )
    lookup = pd.DataFrame(rows).drop_duplicates()
    return lookup


def process_excel(workbook_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    workbook = pd.ExcelFile(workbook_path)
    geography = build_excel_geography_lookup(workbook)
    records: list[dict[str, Any]] = []
    catalog_rows: list[dict[str, Any]] = []
    inventory_rows: list[dict[str, Any]] = []

    for sheet_name in workbook.sheet_names:
        df = pd.read_excel(workbook, sheet_name=sheet_name, header=None, dtype=object)
        raw_indicator_row = df.iloc[1]
        indicator_row = raw_indicator_row.ffill()
        indicator_block_by_col: dict[int, int] = {}
        block_counts: Counter[str] = Counter()
        current_indicator = ""
        current_block = 0
        for col in range(2, df.shape[1]):
            raw_indicator = clean_text(raw_indicator_row.iloc[col])
            if raw_indicator:
                current_indicator = raw_indicator
                block_counts[current_indicator] += 1
                current_block = block_counts[current_indicator]
            indicator_block_by_col[col] = current_block
        years = df.iloc[2]

        sheet_records_before = len(records)
        indicator_years: dict[tuple[str, int], set[int]] = defaultdict(set)
        indicator_units: dict[tuple[str, int], str] = {}

        for col in range(2, df.shape[1]):
            indicator = clean_text(indicator_row.iloc[col])
            year_raw = years.iloc[col]
            if not indicator or pd.isna(year_raw):
                continue
            year_start, year_end, reporting_period = parse_reporting_period(year_raw)
            if year_end is None:
                continue

            unit = infer_unit(indicator)
            indicator_block = indicator_block_by_col.get(col, 0)
            indicator_key = (indicator, indicator_block)
            indicator_units[indicator_key] = unit
            indicator_years[indicator_key].add(year_end)

            for _, row in df.iloc[3:].iterrows():
                geo_code = clean_text(row.iloc[0])
                geo_label = clean_text(row.iloc[1])
                if not geo_label:
                    continue
                parsed = parse_number(row.iloc[col], decimal_comma=False)
                geo_level = geo_level_from_code_name(geo_code, geo_label)
                records.append(
                    {
                        "source_file": workbook_path.name,
                        "source_sheet": sheet_name,
                        "indicator": indicator,
                        "indicator_slug": slugify(indicator),
                        "indicator_block": indicator_block,
                        "unit": unit,
                        "year": year_end,
                        "year_start": year_start,
                        "year_end": year_end,
                        "reporting_period": reporting_period,
                        "geo_code": geo_code,
                        "geo_name": normalize_geo_name(geo_label) if geo_level in {"Stadtteil", "Stadtbezirk"} else geo_label,
                        "geo_label": geo_label,
                        "geo_level": geo_level,
                        "raw_value": parsed.raw_value,
                        "value": parsed.value,
                        "value_status": parsed.value_status,
                    }
                )

        for (indicator, indicator_block), year_set in indicator_years.items():
            catalog_rows.append(
                {
                    "source_file": workbook_path.name,
                    "source_section": sheet_name,
                    "indicator": indicator,
                    "indicator_slug": slugify(indicator),
                    "indicator_block": indicator_block,
                    "unit": indicator_units.get((indicator, indicator_block), ""),
                    "years": year_range_label(year_set),
                    "year_count": len(year_set),
                    "geo_levels": "Ortsteil; Stadtteil; Stadtbezirk; Stadt",
                    "source_type": "Excel worksheet",
                }
            )

        sheet_records = len(records) - sheet_records_before
        inventory_rows.append(
            {
                "dataset_name": f"{workbook_path.name}::{sheet_name}",
                "source_file": workbook_path.name,
                "source_type": "Excel worksheet",
                "encoding": "BIFF .xls via xlrd",
                "delimiter": "",
                "decimal_format": "Excel numeric",
                "row_count_raw": df.shape[0],
                "column_count_raw": df.shape[1],
                "indicator_count": len(indicator_years),
                "years": year_range_label({y for ys in indicator_years.values() for y in ys}),
                "geographic_coverage": "Ortsteile, Stadtteile, Stadtbezirke, Stadt Bremen",
                "limitations": "Wide worksheet with repeated indicator/year header bands; boundary-change notes are not embedded in the sheet.",
                "processed_records": sheet_records,
            }
        )

    return pd.DataFrame(records), pd.DataFrame(catalog_rows), pd.DataFrame(inventory_rows)


def year_range_label(years: set[int] | list[int]) -> str:
    ordered = sorted(set(years))
    if not ordered:
        return ""
    if len(ordered) == 1:
        return str(ordered[0])
    return f"{ordered[0]}-{ordered[-1]} ({len(ordered)} reporting years)"


def process_csv_files(csv_paths: list[Path], geography: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    geo_by_name: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in geography.to_dict("records"):
        geo_by_name[row["geo_name"]].append(row)

    records: list[dict[str, Any]] = []
    catalog_rows: list[dict[str, Any]] = []
    inventory_rows: list[dict[str, Any]] = []

    for path in csv_paths:
        df = read_csv_source(path)
        df = df.loc[:, [col for col in df.columns if not str(col).startswith("Unnamed")]]
        df.columns = [clean_text(col) for col in df.columns]
        repeated_headers = int((df["Nr"].map(clean_text) == "Nr").sum()) if "Nr" in df else 0
        data = df[df["Nr"].map(clean_text) != "Nr"].copy()

        geo_columns = [col for col in data.columns if col not in {"Nr", "Titel", "Merkmal"}]
        source_records_before = len(records)
        indicators: set[str] = set()
        years: set[int] = set()
        geo_levels: set[str] = set()

        for source_index, row in data.iterrows():
            nr = clean_text(row.get("Nr", ""))
            title = clean_text(row.get("Titel", ""))
            indicator = clean_text(row.get("Merkmal", ""))
            if not indicator:
                continue
            row_years = extract_years(title)
            year_start = row_years[0] if row_years else None
            year = row_years[-1] if row_years else None
            reporting_period = str(year) if year else ""
            unit = infer_unit(title) or infer_unit(indicator)
            indicators.add(indicator)
            if year:
                years.add(year)

            for geo_col in geo_columns:
                geo_label = clean_text(geo_col)
                if not geo_label:
                    continue
                explicit_stadtteil = geo_label.startswith("Stadtteil ")
                geo_name = normalize_geo_name(geo_label)
                candidates = geo_by_name.get(geo_name, [])
                if explicit_stadtteil:
                    candidates = [item for item in candidates if item["geo_level"] == "Stadtteil"] or candidates
                elif candidates:
                    non_aggregates = [item for item in candidates if item["geo_level"] == "Ortsteil"]
                    candidates = non_aggregates or candidates
                geo_code = candidates[0]["geo_code"] if candidates else ""
                geo_level = "Stadtteil" if explicit_stadtteil else (candidates[0]["geo_level"] if candidates else "unknown")
                geo_levels.add(geo_level)
                parsed = parse_number(row.get(geo_col, ""), decimal_comma=True)
                records.append(
                    {
                        "source_file": path.name,
                        "source_sheet": "",
                        "statistic_number": nr,
                        "source_row_number": int(source_index) + 2,
                        "title": title,
                        "indicator": indicator,
                        "indicator_slug": slugify(indicator),
                        "indicator_block": 1,
                        "unit": unit,
                        "year": year,
                        "year_start": year_start,
                        "year_end": year,
                        "reporting_period": reporting_period,
                        "geo_code": geo_code,
                        "geo_name": geo_name,
                        "geo_label": geo_label,
                        "geo_level": geo_level,
                        "raw_value": parsed.raw_value,
                        "value": parsed.value,
                        "value_status": parsed.value_status,
                    }
                )

        for indicator in sorted(indicators):
            indicator_source_rows = data[data["Merkmal"].map(clean_text) == indicator]
            indicator_years = {
                y
                for title in indicator_source_rows["Titel"].map(clean_text)
                for y in extract_years(title)
            }
            units = sorted({infer_unit(t) or infer_unit(indicator) for t in indicator_source_rows["Titel"].map(clean_text)})
            catalog_rows.append(
                {
                    "source_file": path.name,
                    "source_section": "",
                    "indicator": indicator,
                    "indicator_slug": slugify(indicator),
                    "indicator_block": 1,
                    "unit": "; ".join([u for u in units if u]),
                    "years": year_range_label(indicator_years),
                    "year_count": len(indicator_years),
                    "geo_levels": "; ".join(sorted(geo_levels)),
                    "source_type": "CSV district snapshot",
                }
            )

        inventory_rows.append(
            {
                "dataset_name": path.name,
                "source_file": path.name,
                "source_type": "CSV district snapshot",
                "encoding": CSV_ENCODING,
                "delimiter": CSV_DELIMITER,
                "decimal_format": "German decimal comma",
                "row_count_raw": len(df),
                "column_count_raw": len(df.columns),
                "indicator_count": len(indicators),
                "years": year_range_label(years),
                "geographic_coverage": "; ".join(sorted(set(clean_text(c) for c in geo_columns if clean_text(c)))),
                "limitations": f"Contains {repeated_headers} repeated header row(s); file is a district/Ortsteil cross-section, not a full Bremen-wide time series.",
                "processed_records": len(records) - source_records_before,
            }
        )

    return pd.DataFrame(records), pd.DataFrame(catalog_rows), pd.DataFrame(inventory_rows)


def process_json_catalog(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    rows: list[dict[str, Any]] = []
    formats = Counter()
    groups = Counter()
    temporal_titles = []
    for item in data:
        resources_raw = item.get("resources") or []
        resources = [resource for resource in resources_raw if isinstance(resource, dict)]
        resource_formats = sorted({clean_text(r.get("format", "")) for r in resources if clean_text(r.get("format", ""))})
        for fmt in resource_formats:
            formats[fmt] += 1
        for group in item.get("groups") or []:
            groups[clean_text(group)] += 1
        title = clean_text(item.get("title", ""))
        title_years = extract_years(title)
        if title_years:
            temporal_titles.extend(title_years)
        rows.append(
            {
                "title": title,
                "name": clean_text(item.get("name", "")),
                "type": clean_text(item.get("type", "")),
                "groups": "; ".join(item.get("groups") or []),
                "tags": "; ".join(item.get("tags") or []),
                "resource_count": len(resources),
                "null_resource_count": len(resources_raw) - len(resources),
                "resource_formats": "; ".join(resource_formats),
                "author": clean_text(item.get("author", "")),
                "maintainer": clean_text(item.get("maintainer", "")),
                "url": clean_text(item.get("url", "")),
                "title_years": "; ".join(map(str, sorted(set(title_years)))),
            }
        )

    inventory = pd.DataFrame(
        [
            {
                "dataset_name": path.name,
                "source_file": path.name,
                "source_type": "JSON open-data metadata catalogue",
                "encoding": "utf-8",
                "delimiter": "",
                "decimal_format": "",
                "row_count_raw": len(data),
                "column_count_raw": "",
                "indicator_count": "",
                "years": year_range_label(set(temporal_titles)),
                "geographic_coverage": "Metadata catalogue; not statistical geography observations",
                "limitations": f"Catalogue metadata only; top resource formats: {', '.join(f'{k}={v}' for k, v in formats.most_common(5))}; top groups: {', '.join(f'{k}={v}' for k, v in groups.most_common(5))}.",
                "processed_records": len(rows),
            }
        ]
    )
    return pd.DataFrame(rows), inventory


def write_csv(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8", quoting=csv.QUOTE_MINIMAL)


def quality_summary(name: str, df: pd.DataFrame) -> dict[str, Any]:
    status_counts = df["value_status"].value_counts(dropna=False).to_dict()
    duplicate_keys = [
        "source_file",
        "source_sheet",
        "statistic_number",
        "source_row_number",
        "title",
        "indicator",
        "indicator_block",
        "reporting_period",
        "geo_code",
        "geo_name",
    ]
    available_keys = [col for col in duplicate_keys if col in df.columns]
    duplicates = int(df.duplicated(available_keys).sum()) if available_keys else 0
    unknown_geo = int((df["geo_level"] == "unknown").sum()) if "geo_level" in df else 0
    years = sorted({int(y) for y in df["year"].dropna().unique()}) if "year" in df else []
    return {
        "name": name,
        "records": len(df),
        "ok_values": int(status_counts.get("ok", 0)),
        "missing_values": int(status_counts.get("missing", 0)),
        "invalid_or_suppressed_values": int(status_counts.get("invalid_or_suppressed", 0)),
        "duplicate_key_rows": duplicates,
        "unknown_geography_rows": unknown_geo,
        "years": year_range_label(set(years)),
    }


def build_quality_report(
    csv_long: pd.DataFrame,
    excel_long: pd.DataFrame,
    json_catalog: pd.DataFrame,
    indicator_catalog: pd.DataFrame,
    inventory: pd.DataFrame,
    geography: pd.DataFrame,
) -> str:
    summaries = [quality_summary("CSV district files", csv_long), quality_summary("Excel Ortsteilatlas workbook", excel_long)]

    overlap = (
        indicator_catalog.groupby("indicator_slug")["source_type"]
        .apply(lambda values: sorted(set(values)))
        .reset_index()
    )
    overlap = overlap[overlap["source_type"].map(len) > 1]
    overlap_count = len(overlap)

    unknown_csv = sorted(csv_long.loc[csv_long["geo_level"] == "unknown", "geo_label"].dropna().unique())
    duplicate_geo_names = geography[geography.duplicated(["geo_name"], keep=False)].sort_values("geo_name")

    lines = [
        "# Data Quality Report",
        "",
        "Generated by `src/prepare_data.py`. Raw files were not modified.",
        "",
        "## Source Reading",
        "",
        f"- CSV files read successfully: {csv_long['source_file'].nunique()} using `{CSV_ENCODING}`, semicolon delimiters, and German decimal commas.",
        f"- Excel workbook read successfully: {excel_long['source_sheet'].nunique()} worksheets from legacy `.xls` via `xlrd`.",
        f"- JSON metadata catalogue read successfully: {len(json_catalog)} catalogue records using UTF-8.",
        "",
        "## Cleaning Decisions",
        "",
        "- German characters were decoded from the CSV files as Windows-1252/CP1252 and written to processed UTF-8 CSV outputs.",
        "- Column names and text fields were Unicode-normalized, trimmed, and whitespace-collapsed.",
        "- CSV numeric values were parsed with German decimal commas. Excel numeric cells were parsed as workbook numeric values.",
        "- Empty strings and common non-values (`-`, `.`, `..`, `...`, `k.A.`) were marked as missing. Other unparsable values were marked `invalid_or_suppressed`.",
        "- No missing values were imputed or fabricated. Each processed row keeps `raw_value`, parsed `value`, and `value_status`.",
        "- CSV district aggregates prefixed with `Stadtteil` were classified as Stadtteile; other names were matched against the Excel geography lookup where possible.",
        "",
        "## Validation Summary",
        "",
    ]
    for summary in summaries:
        lines.extend(
            [
                f"### {summary['name']}",
                "",
                f"- Records: {summary['records']}",
                f"- Parsed numeric values: {summary['ok_values']}",
                f"- Missing values: {summary['missing_values']}",
                f"- Invalid or suppressed values: {summary['invalid_or_suppressed_values']}",
                f"- Duplicate key rows: {summary['duplicate_key_rows']}",
                f"- Unknown geography rows: {summary['unknown_geography_rows']}",
                f"- Reporting years: {summary['years']}",
                "",
            ]
        )

    lines.extend(
        [
            "## Geographic Levels",
            "",
            "- `Ortsteil`: three-digit geography codes in the workbook.",
            "- `Stadtteil`: two-digit geography codes or labels beginning with `Stadtteil`.",
            "- `Stadtbezirk`: one-digit codes or labels beginning with `Stadtbezirk`.",
            "- `Stadt`: the `Stadt Bremen` total row.",
            "",
            f"Geography lookup rows: {len(geography)}.",
            f"Geography names appearing at multiple levels: {len(duplicate_geo_names['geo_name'].unique())}. This is expected for names such as Stadtteil/Ortsteil pairs and was handled using prefixes/codes.",
            "",
            "## Overlap and Comparability",
            "",
            f"- Indicator labels overlapping between CSV and Excel sources after slug normalization: {overlap_count}. Treat overlaps as candidates only; compare definitions, units, and years before merging.",
            "- The CSV files are district/Ortsteil cross-sections with titles mostly referring to 2014/2015 statistics.",
            "- The Excel workbook is the broader Ortsteilatlas-style time-series source, with worksheets covering different year ranges up to 2024.",
            "- The JSON file is a catalogue of open datasets and is not directly mergeable with the statistical observations.",
            "",
            "## Remaining Issues",
            "",
            "- The raw files do not include machine-readable boundary-change metadata. Longitudinal comparisons should verify whether Bremen Ortsteil/Stadtteil definitions changed for the chosen period.",
            "- Some workbook sheet names are truncated in the `.xls` file because Excel sheet names have a length limit; the source sheet names are preserved exactly.",
            "- CSV and Excel indicators may have similar labels but different definitions, denominators, or reference dates.",
            "- Values marked `invalid_or_suppressed` require manual review before statistical analysis.",
        ]
    )

    if unknown_csv:
        lines.append(f"- Unmatched CSV geography labels: {', '.join(unknown_csv)}.")

    lines.extend(
        [
            "",
            "## Inventory Snapshot",
            "",
            f"- Inventory rows: {len(inventory)}.",
            f"- Indicator catalogue rows: {len(indicator_catalog)}.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    csv_paths = sorted(ROOT.glob("ST*.csv"))
    workbook_path = ROOT / "Datentabelle.xls"
    json_path = ROOT / "bremen_data.json"

    excel_long, excel_catalog, excel_inventory = process_excel(workbook_path)
    geography = build_excel_geography_lookup(pd.ExcelFile(workbook_path))
    csv_long, csv_catalog, csv_inventory = process_csv_files(csv_paths, geography)
    json_catalog, json_inventory = process_json_catalog(json_path)

    indicator_catalog = pd.concat([csv_catalog, excel_catalog], ignore_index=True).sort_values(
        ["source_type", "source_file", "source_section", "indicator"]
    )
    inventory = pd.concat([csv_inventory, excel_inventory, json_inventory], ignore_index=True)

    write_csv(PROCESSED / "csv_district_statistics_long.csv", csv_long)
    write_csv(PROCESSED / "excel_ortsteilatlas_long.csv", excel_long)
    write_csv(PROCESSED / "bremen_open_data_catalog.csv", json_catalog)
    write_csv(PROCESSED / "geography_lookup.csv", geography)
    write_csv(ROOT / "indicator_catalog.csv", indicator_catalog)
    write_csv(ROOT / "data_inventory.csv", inventory)

    report = build_quality_report(csv_long, excel_long, json_catalog, indicator_catalog, inventory, geography)
    (ROOT / "data_quality_report.md").write_text(report, encoding="utf-8")

    validation = pd.DataFrame(
        [
            quality_summary("csv_district_statistics_long.csv", csv_long),
            quality_summary("excel_ortsteilatlas_long.csv", excel_long),
        ]
    )
    write_csv(PROCESSED / "validation_summary.csv", validation)

    print("Processed files:")
    print(f"- CSV sources: {len(csv_paths)}")
    print(f"- Excel sheets: {excel_long['source_sheet'].nunique()}")
    print(f"- JSON catalogue records: {len(json_catalog)}")
    print(f"- Processed output directory: {PROCESSED}")


if __name__ == "__main__":
    main()
