# Bremen Socioeconomic Inequality Atlas — 2024

## Purpose and section boundaries

This additive visual evidence package complements Section 2 V2 and answers RQ1 (neighborhood socioeconomic/demographic differences) and RQ2 (indicator usefulness). It reads the shared 2024 economic observations without changing them. It does not compute composites, TOPSIS, clustering, deprivation scores, official risk classes or disadvantage rankings. The cards are purposively selected economic examples, not a representative sample or a demographic atlas. Contextual demographic evidence remains in Section 2 V2.

## Data and definitions

Baseline: `20b79ae817c5d7c7b80e1d93c79d415d47037be7`, branch `analysis/section-2-v2`. Authoritative socioeconomic input: `data/processed/ortsteil_analysis_ready.csv`. There are 88 represented statistical geographic records, 79 complete cases, 79 valid unemployment observations, 79 employment observations and 84 SGB II observations. Codes are strings. All observations are 2024 percentages. The three denominators differ; unemployment is not the official all-civilian-labour-force unemployment rate. No missing observation is imputed or replaced with zero. Exact shared catalog definitions follow:

| feature | original_german_name | english_name | definition | source_sheet | indicator_block | unit |
| --- | --- | --- | --- | --- | --- | --- |
| unemployment | Anteil der Arbeitslosen an den sozialversicherungspflichtig Beschäftigten zuzüglich Arbeitslose (%) | Unemployment quotient (%) | Registered unemployed / (social-insurance employees + registered unemployed). Not the official all-civilian-labour-force unemployment rate. | Erwerbstätigkeit, Arbeitslosig | 1 | % |
| employment | Anteil der sozialversicherungspflichtig Beschäftigten an der Bevölkerung im Alter von 15 bis unter 65 Jahren (%) | Social-insurance employment (%) | Social-insurance employees at residence / population aged 15 to under 65. Excludes self-employment and civil servants; low values are an imperfect labour-market disadvantage proxy. | Erwerbstätigkeit, Arbeitslosig | 1 | % |
| benefit_receipt | Anteil der Leistungsberechtigten (Grundsicherung für Arbeitsuchende, SGB II) an der Bevölkerung unter 65 Jahren (%) | SGB II receipt, under 65 (%) | SGB II entitled recipients / population under 65. Measures receipt, not all poverty or unmet need; includes employed recipients. | Sozialleistungen | 1 | % |

Unemployment and receipt are relevant direct economic indicators with incomplete coverage and restricted definitions. Employment offers another labor-market perspective but excludes employment outside social insurance. These aggregate associations do not measure individual poverty, unmet benefit need or causation. All data, old output and Section 2 V2 hashes are checked before execution.

## Official boundary source and compatibility

Dataset: ATKIS - Verwaltungsgrenzen Land Bremen. Publisher and attribution: **Landesamt GeoInformation Bremen**. License: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Source [official ISO metadata](https://metaver.de/csw/partner/hb?Service=CSW&Request=GetRecordById&Version=2.0.2&id=D9F32B22-C647-42FD-9E95-1344AC57BC46&outputSchema=http://www.isotc211.org/2005/gmd&elementSetName=full); [metadata page](https://metaver.de/trefferanzeige?docuuid=D9F32B22-C647-42FD-9E95-1344AC57BC46); [WFS capabilities](https://geodienste.bremen.de/wfs_verwaltungsgrenzen?SERVICE=WFS&REQUEST=GetCapabilities); [official shapefile download](https://gdi2.geo.bremen.de/inspire/download/Verwaltungsgrenzen/data/Verwaltungsgrenzen_HB.zip). Data were accessed on 10 October 2026. Raw responses and documentary evidence are frozen under `sources/`; URLs, CRS, format, dates and SHA-256 hashes are in `boundary_source_metadata.json`.

The metadata identifies a **dataset revision on 11 December 2024**, not an exact legal boundary-validity day. Metadata itself was updated in 2026; retrieval date is not the boundary date. GML coordinates are EPSG:25832 (ETRS89 / UTM zone 32N), used unchanged with equal map aspect and north-up orientation. This is an annual 2024 comparison, not proof that statistics and polygons have exactly identical reference days. Historical geometry compatibility is not established.

## Join and scope

The official Ortsteil WFS and ZIP DBF each contain **87** polygons; they agree on codes and names. WFS attributes incorrectly declare numberReturned=0 despite 87 actual member elements, so actual parsed records and independent DBF counts determine coverage. `sch_ot` ends in the shared three-digit code; independent `sch_ot_ags` confirms that suffix. Identifiers are unique and municipality codes are checked.

**Oberneuland exception:** the shared statistical table identifies 361, while the official polygon is Stadtteil `04011360`, absent from the Ortsteil layer. A named, explicit one-to-one crosswalk uses its unchanged official Stadtteil polygon. The [official administrative-division document](https://www.transparenz.bremen.de/metainformationen/verordnung-ueber-die-neuordnung-der-stadtbremischen-verwaltungsbezirke-vom-23-februar-1951-70486?asl=bremen203_tpgesetz.c.55340.de&template=20_gp_ifg_meta_detail_d) identifies Oberneuland as 361; the [2013 municipal proposal](https://www.rathaus.bremen.de/sixcms/media.php/13/20130312_Ortsgesetz_Stadtteil_Oberneuland.pdf) explains the undivided area and its elevation to Stadtteil status. The proposal is documentary support, not a claim that a proposal is enacted law. The shared lookup has one statistical unit in this territory, and the current official layer has one Oberneuland polygon. This is a documented correspondence of an undivided area, not a generic suffix/name join between geographic levels or an invented polygon.

After that exception: **88/88 matched**, no unmatched polygon in the selected scope, no remaining unmatched socioeconomic record, no missing geometry. Three harmless name differences are reported rather than silently normalized:

| geo_code | geo_name | boundary_name |
| --- | --- | --- |
| 421 | Regensburger Straße | Regensburger Str. |
| 437 | Ueberseestadt | Überseestadt |
| 515 | St. Magnus | St.Magnus |

The scope is the 88 represented mainland statistical units. The separate overseas-port enclave (123) is absent from both the selected mainland layers and the socioeconomic master. These maps do not claim full coverage of all city territory or Land Bremen/Bremerhaven. Geometry checks cover CRS, finite closed nondegenerate rings, original vertices, multipart/hole rendering and coordinate area versus published area. No full topology/overlap certification is claimed. See `geographic_join_validation.csv`, `.json` and `.md`.

## Map classification and design

Maps A and B use the same extent and **shared fixed 5-percentage-point intervals**, from 0 to 35%, and the same sequential cividis palette. Every observed value is inside this range. Classes are [a,b), with the final upper bound included. Fixed shared breaks permit direct numerical rate comparison; they do not make the denominators interchangeable or constitute policy thresholds. Gray denotes missing observations: 9 for unemployment, 4 for SGB II. Both maps show all 88 mapped geographic records. Figures include boundary attribution, reporting year and boundary dataset revision year. At 300 DPI, labels are intentionally sparse; the supporting join CSV gives all geographic identities.

The bivariate map uses only the 79 paired observations to compute NumPy **linear quantiles at 1/3 and 2/3**. Unemployment cutpoints: 8.5398000000% and 14.1290000000%. SGB II cutpoints: 10.2200000000% and 18.0283000000%. Values equal to cutpoints belong to the lower class. Equal observed values would never be split. There are no repeated observed values, but **two observations per indicator lie exactly on its cutpoints**; they are assigned to the lower adjoining class. This gives marginal group sizes 27, 26 and 26, rather than splitting tied values or forcing equal counts. Repeated quantile boundaries would stop map production for explicit review; the script does not quietly reduce classes. The exported integer codes 0/1/2 identify categories, not scores. All 88 records remain in the export; nine missing either indicator have no assigned economic class and appear gray. The 3×3 legend separates the indicator dimensions; blue/teal–purple colors, text labels and the CSV support interpretation, without claiming accessibility for every color-vision condition.

## Economic indicator agreement and mapped descriptions

Spearman rho is **0.9738558909444986**, n=79, independently checked using ranked observations. **65/79 (82.28%)** occupy the same relative tertile for both indicators; **14/79** differ. This is relative economic-indicator agreement, not agreement among Section 4 methods and not external validation of deprivation. Changing class breaks may change apparent visual agreement.

| unemployment_class | sgbii_lower_third | sgbii_middle_third | sgbii_upper_third |
| --- | --- | --- | --- |
| 0 | 24 | 3 | 0 |
| 1 | 3 | 19 | 4 |
| 2 | 0 | 4 | 22 |

Ohlenhof, in the official Bremen-West subdivision, has the highest observed unemployment (27.5409%) and SGB II receipt (34.6216%). Seehausen, in Bremen-Süd, has the lowest observed unemployment (2.5896%); In den Hufen, in Bremen-West, has the lowest available SGB II receipt (0.9901%) but missing unemployment. Thus similar overall association coexists with different coverage and denominators. In the bivariate map the upper/upper category contains 22 observed units: Bahnhofsvorstadt, Neuenland, Huckelriede, Kattenturm, Mittelshuchting, Sodenmatt, Kirchhuchting, Neue Vahr Nord, Neue Vahr Südost, Tenever, Blockdiek, Hemelingen, Lindenhof, Gröpelingen, Ohlenhof, Oslebshausen, Burgdamm, Vegesack, Grohn, Aumund-Hammersbeck, Blumenthal, Lüssum-Bockhorn. By official Stadtbezirk those upper/upper units are distributed as {'Bremen-Mitte': 1, 'Bremen-Nord': 6, 'Bremen-Ost': 5, 'Bremen-Süd': 6, 'Bremen-West': 4}. These categorical descriptions refer to actual mapped codes and official attributes. They establish neither formal spatial clustering nor spatial significance; no Moran's I, neighborhood weights or spatial hypothesis tests were computed. Large polygons are visually prominent regardless of population.

## Data blind spots and governance

All 88 geographic records are retained in `spatial_missingness_2024.csv`. There are 79 fully observed records, five missing two primary indicators, four missing all three, and none missing exactly one. The observed count and both independent completeness flags are checked. No selected geometry lacks a socioeconomic row; the map legend explicitly reports that count as zero.

| geo_code | geo_name | observed_primary_count | missing_primary_count |
| --- | --- | --- | --- |
| 122 | Industriehäfen | 0 | 3 |
| 124 | Neustädter Hafen | 0 | 3 |
| 125 | Hohentorshafen | 0 | 3 |
| 271 | Strom | 1 | 2 |
| 411 | Blockland | 1 | 2 |
| 424 | In den Hufen | 1 | 2 |
| 436 | Hohweg | 1 | 2 |
| 444 | In den Wischen | 0 | 3 |
| 512 | Werderland | 1 | 2 |

By official subdivision, the nine incomplete units are {'Bremen-Mitte': 3, 'Bremen-Nord': 1, 'Bremen-Süd': 1, 'Bremen-West': 4}. Their exclusion reduces the scope of economic comparisons and could conceal evidence gaps from decision-support users. Missingness cannot be interpreted as favorable conditions or zero economic need. No reason for any missing observation is inferred from a neighborhood name, polygon area or land use. No population impact or missingness mechanism is estimated; denominator counts are unavailable.

## Evidence-card selection and findings

Selection is deterministic: observed unemployment maximum/minimum; observed SGB II maximum; deduplicate selected codes; first geographic code among records with all three economic values missing; and the only strictly opposite-side unemployment/SGB II median example among 79 complete observations. Ties at extrema use the lowest code. This produces four cards: Ohlenhof, Seehausen, Industriehäfen and Hastedt. The unemployment and SGB II maxima identify the same neighborhood. All panels share a 0–100% scale, with separate denominator explanations. Missing values are labeled and are not drawn as zero-length bars.

| geo_code | geo_name | unemployment | employment | benefit_receipt | selection_reason | interpretation |
| --- | --- | --- | --- | --- | --- | --- |
| 443 | Ohlenhof | 27.5409 | 49.0596 | 34.6216 | Highest observed unemployment; Highest observed SGB II receipt | Highest observed unemployment and under-65 SGB II receipt; distinct populations. |
| 261 | Seehausen | 2.5896 | 72.7138 | 2.8537 | Lowest observed unemployment | Lowest observed unemployment; highest observed insured-employment participation. |
| 122 | Industriehäfen | missing | missing | missing | Missing all economic observations; lowest code among equally incomplete cases | All three economic observations are missing; economic conditions cannot be inferred. |
| 382 | Hastedt | 11.5414 | 61.5617 | 12.4187 | Only strictly opposite-side median example in the 79-case sample | Above the unemployment median, below the SGB II median; sample-relative contrast. |

Hastedt's unemployment is 11.5414%, above the complete-case median 10.9762%; its SGB II value is 12.4187%, below median 13.2323%. This is a modest, threshold-dependent contrast, not an exceptional risk classification; its bivariate tertile combination may still agree. Industriehäfen has no economic evidence for these three indicators, so its economic conditions cannot be inferred. All cards are observed examples and are not representative of Bremen's neighborhoods.

## Limitations and unresolved issues

The exact legal boundary reference day, exact indicator reference days and complete municipal denominator definitions remain unverified. The undivided Oberneuland crosswalk is explicit and should be reviewed if newer official definitions or geometry appear. No geometric topology certification is available with installed libraries; basic geometry and published area checks passed. The official boundary snapshot is archived, not a historical sequence. This evidence is for 2024, not current 2026 conditions. Aggregate rates cannot establish individual disadvantage, causal effects or resource-allocation priorities. No population weights, uncertainty intervals, formal spatial tests, composite index or rankings are produced. Median or tertile groups are sensitive to thresholds. Economic indicators overlap strongly. Demographic characteristics are not automatically deprivation; relevant context remains in V2. Missing data are not demonstrably random.

## Reproduction and preservation

Run from repository root with the existing environment:

```powershell
.\.venv-section2\Scripts\python.exe -B src\build_section2_atlas.py
```

Default reproduction is **offline**, using the archived sources and their pinned hashes. No package installation or GIS package is needed. Matplotlib renders original GML polygon coordinates without approximating boundaries. The `--fetch` option only downloads missing source snapshots; existing sources are never overwritten. A fresh WFS retrieval can differ in geometry IDs/timestamps/hash; it is not a substitute for the archived version and requires explicit review if pinned hashes differ. Source URLs are recorded for audit, not a promise that a live service reproduces byte-identical files later.

Outputs are staged and validated before publication; any differing existing atlas file prevents publication. Identical reruns leave outputs untouched. Shared tracked files, the old Section 2 files and all original V2 outputs are verified unchanged; source snapshots and inputs are hashed. `atlas_reproduction_manifest.json` records versions, hashes and validations. No changes are made to V2's original reproducibility manifest. Its frozen audit-time file inventory may differ from today's additive repository contents; the atlas has a separate manifest.

## Use in the report and other sections

Main report: use the side-by-side economic maps and missingness map; include the bivariate map only if there is space to explain its sample-relative classes. Presentation: side-by-side maps plus evidence cards provide clear observed contrasts. Supplement: individual maps, full join report, class counts and all CSVs. See `atlas_figure_captions.md`.

Section 1 can use documented contrasts and evidence gaps for problem framing. Section 3 can expose provenance, code crosswalks and missingness transparently. Section 4 receives unchanged primary inputs and warnings about indicator overlap; weighting, composite methods, TOPSIS, clustering and method-agreement evaluation remain its responsibilities.
