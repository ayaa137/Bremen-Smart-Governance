# Geographic join validation

Status: **PASS with explicit documented Oberneuland exception and reference-date limitations**.

Official Ortsteil WFS: 87 actual unique features, confirmed independently by the official shapefile DBF. Initial unmatched socioeconomic code: 361 Oberneuland. No unmatched polygon. Code suffixes were checked against the independent official AGS-style field. WFS numberReturned=0 is unreliable; actual member and DBF counts are used.

The undivided Oberneuland polygon is published as Stadtteil 04011360. The crosswalk to statistical 361 is individually documented using https://www.transparenz.bremen.de/metainformationen/verordnung-ueber-die-neuordnung-der-stadtbremischen-verwaltungsbezirke-vom-23-februar-1951-70486?asl=bremen203_tpgesetz.c.55340.de&template=20_gp_ifg_meta_detail_d and https://www.rathaus.bremen.de/sixcms/media.php/13/20130312_Ortsgesetz_Stadtteil_Oberneuland.pdf. It is not a general conversion between levels. Final coverage: **88/88 matched**, no remaining unmatched records or missing geometry. The three name discrepancies are formatting/spelling variants:

| geo_code | geo_name | boundary_name |
| --- | --- | --- |
| 421 | Regensburger Straße | Regensburger Str. |
| 437 | Ueberseestadt | Überseestadt |
| 515 | St. Magnus | St.Magnus |

CRS: EPSG:25832. Official dataset revision: 11 December 2024; exact legal boundary-validity day remains unknown. Geometry tests: finite, closed, nondegenerate polygon rings, supported CRS/encoding, multipart/hole preservation, areas compared with official feature areas. No full topology/overlap certification. Full numeric/row evidence: geographic_join_validation.json and geographic_join_validation.csv.

Scope: 88 represented mainland statistical units, excluding a separately represented overseas-port enclave (123) and Bremerhaven. Map titles refer to this documented represented scope, not complete Land Bremen coverage.
