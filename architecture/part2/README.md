# Part 2 integration and offline dashboard

This workflow assembles the saved 2024 Part 1 and Part 2 results. Run these commands from the repository root with Python 3.9 or newer and Git.

```powershell
python -B architecture/part2/integrate.py
```

The build uses only Python's standard library and local Git. Its neighborhood spine is [`data/processed/ortsteil_analysis_ready.csv`](../../data/processed/ortsteil_analysis_ready.csv), the 2024 analysis-ready Ortsteil snapshot. Historical annual panel data are outside this integration. The build reads the seven release inputs from the most recent commit in the current history that touched any of them. For `2024-v1` that source is `fa2c6e2`. It verifies that the working copies match the Git snapshot, allowing checkout line-ending conversions. The manifest hashes the original seven Git blobs and both published CSVs.

The validator checks schemas, keys, coverage, and consistency with the saved rankings. It checks the spatial settings (`k=4` and `k=6`, 79 areas, 9,999 permutations, seed 2024), finite statistics, the bound for the row-standardized symmetric-neighbor graph, and the plus-one p-value arithmetic. For each shortlist entry it checks the baseline ranks, rank gap, and sensitivity bounds and spans. The auxiliary [`results/weight_rank_ranges.csv`](../../results/weight_rank_ranges.csv) is read from the same source commit and checked against its working copy. The existing manifest retains its seven release input hashes. The validator checks the saved evidence for consistency. The upstream workflows calculate the graph, permutations, and sensitivity scenarios.

The default release is `releases/2024-v1/`. All inputs are validated before the release is published. A byte-identical rerun verifies the existing files. A differing release at that path stops the build. To publish a changed integration contract or input release, review the change and assign a new release version in `integrate.py`.

| File | Contents |
| --- | --- |
| `neighborhoods.csv` | 88 Ortsteile in code order. Use `(geo_code, year)` as the key and read `geo_code` as text. The 79 eligible areas retain the saved Composite Index and TOPSIS scores and separate ranks, their nominal K-means profile, and housing benchmark values. Nine excluded areas retain their source indicators and reasons, with blank analysis fields. Housing blanks indicate absence from the benchmark output. The five fieldwork candidates all have status `proposed_not_visited`. |
| `spatial_summary.csv` | Two global Moran's I results at release level, one each for `k=4` and `k=6`. Includes the saved diagnostics, sample fingerprints, and caveats. |
| `manifest.json` | Release schema version, reporting year, source commit, row counts, and SHA-256 hashes. |

TOPSIS ideal distances remain available in the source CSV. The joined release covers 2024 only. Geographic polygons and historical comparisons are outside its scope.

## Offline student dashboard

From the repository root, build the dashboard, open it in the default Windows browser, and run the full integration and dashboard test suite.

```powershell
python -B architecture/part2/build_dashboard.py
Invoke-Item 'architecture/part2/prototype/index.html'
python -B -m unittest discover -s architecture/part2 -p 'test_*.py' -v
```

The builder verifies both release CSVs against the manifest and checks the housing figure separately before generating the [single-file dashboard](prototype/index.html). The page embeds the figure and runs offline in a browser. JavaScript enables search, filters, and focused neighborhood selection. The release CSVs are available in the repository. The dashboard has no download controls.

See the [four-layer architecture](four_layer_architecture.md) and [technical benchmark](technical_benchmark.md) for the prototype scope and proposed municipal work.
