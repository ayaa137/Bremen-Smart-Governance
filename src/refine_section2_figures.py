"""Create report figures from validated Section 2 outputs; preserve originals.

Run: python src/refine_section2_figures.py
Existing revised outputs are checked for equality, never overwritten.
"""
import json
import tempfile
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_section2 as base

ROOT = base.ROOT
REPORT = base.REPORT
DEST = ROOT / "figures/section2"
NAMES = ["figure1_compact_extreme_unemployment_2024.png",
         "figure2_scatter_revised_annotation_2024.png",
         "figure3_context_distributions_revised_caption_2024.png"]


def main():
    baseline = json.loads((REPORT / "reproducibility_manifest.json").read_text(encoding="utf-8"))
    protected = {**baseline["inputs"], **baseline["outputs"]}
    for name, expected in protected.items():
        assert base.digest(ROOT / name) == expected, f"Changed baseline file: {name}"
    master = pd.read_csv(base.DATA / "section2_2024_ortsteil_analysis.csv", dtype={"geo_code": str})
    correlation = json.loads((REPORT / "correlation_results.json").read_text(encoding="utf-8"))
    assert len(master) == 88 and master.geo_code.is_unique
    assert master.reporting_year.eq(2024).all()
    pair = master.dropna(subset=base.IDS[:2]).sort_values([base.IDS[0], "geo_code"])
    assert len(pair) == correlation["n"] == 79
    # Cross-check the stored coefficient without modifying its calculation/output.
    assert np.isclose(pair[base.IDS[:2]].rank().corr().iloc[0, 1], correlation["spearman_rho"], atol=1e-14)
    low, high = pair.head(5), pair.tail(5).iloc[::-1]
    assert len(set(low.geo_code) | set(high.geo_code)) == 10
    assert low[base.IDS[0]].max() < pair.iloc[5][base.IDS[0]]
    assert high[base.IDS[0]].min() > pair.iloc[-6][base.IDS[0]]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "savefig.dpi": 300})
    with tempfile.TemporaryDirectory(prefix="section2-revised-figures-") as tmp:
        stage = Path(tmp)
        fig, axes = plt.subplots(2, 1, figsize=(9.5, 7.8), sharex=True)
        for ax, group, title in zip(axes, [high, low], ["Five highest observed unemployment values", "Five lowest observed unemployment values"]):
            y = np.arange(5)
            x, z = group[base.IDS[0]], group[base.IDS[1]]
            ax.hlines(y, x, z, color="#cbd5e1", linewidth=1.3)
            ax.scatter(x, y, color="#176b91", s=42, zorder=3,
                       label="Unemployed / (socially insured employees + unemployed)")
            ax.scatter(z, y, color="#bd5938", marker="D", s=35, zorder=3,
                       label="SGB II recipients / population under 65")
            ax.set_yticks(y, group.geo_name + " (" + group.geo_code + ")")
            ax.set_ylim(4.7, -.7)
            ax.set_title(title, loc="left", fontsize=11)
            ax.set_xlim(0, 37)
            ax.grid(axis="x", alpha=.2)
        axes[-1].set_xlabel("Rate (%) — distinct denominators")
        fig.suptitle("Economic indicators at the observed unemployment extremes\nBremen · 2024 · Ortsteil · 10 selected from 79 pairwise-observed neighborhoods",
                     x=.25, ha="left", fontsize=12, y=.96)
        handles, labels = axes[0].get_legend_handles_labels()
        fig.legend(handles, labels, loc="lower left", bbox_to_anchor=(.03, .105), frameon=False, fontsize=9)
        fig.subplots_adjust(left=.25, right=.97, top=.83, bottom=.25, hspace=.38)
        fig.text(.04, .025,
                 "Selection: five highest and five lowest observed unemployment values among the 79 Ortsteile with both rates.\n"
                 "This deliberately selected subset is not representative of all neighborhoods. Full n = 79 comparison: supplementary Figure S1.\n"
                 "Source: Datentabelle.xls; worksheets Erwerbstätigkeit, Arbeitslosig and Sozialleistungen; validated 2024 analysis CSV.",
                 fontsize=8)
        fig.savefig(stage / NAMES[0])
        plt.close(fig)

        original_save = plt.Figure.savefig
        original_dest = base.FIGURES
        evidence = {}

        def save_revised(figure, filename, *args, **kwargs):
            name = Path(filename).name
            if name == "figure1_neighborhood_rates.png":
                return  # Original full Figure 1 is already preserved as Figure S1.
            if name == "figure2_unemployment_sgbii_scatter.png":
                ax = figure.axes[0]
                np.testing.assert_array_equal(ax.collections[0].get_offsets(), pair[base.IDS[:2]].to_numpy())
                annotation = next(t for t in ax.texts if t.get_text() == "Seehausen")
                xy = annotation.xy
                annotation.remove()
                ax.annotate("Seehausen", xy, xytext=(0, 35), textcoords="offset points",
                            fontsize=8, ha="left", va="bottom",
                            arrowprops={"arrowstyle": "-", "color": "#64748b", "lw": .7})
                ax.set_title(f"Unemployment and SGB II receipt\n2024 · Ortsteil · Spearman ρ = {correlation['spearman_rho']:.6f} · n = 79", loc="left")
                figure.texts[0].set_text(figure.texts[0].get_text() +
                    f"\nStored Spearman coefficient: {correlation['spearman_rho']!r}; unchanged from the validated analysis.")
                evidence["figure2"] = {"n": 79, "spearman_rho": correlation["spearman_rho"], "all_point_coordinates_verified": True}
                output = NAMES[1]
            else:
                assert name == "figure3_context_distributions.png"
                # The original plotting function preserves data, bins, panel axes and scales.
                counts = []
                for ax, ident in zip(figure.axes, base.IDS[2:]):
                    values = master[ident].dropna()
                    expected_counts, expected_edges = np.histogram(values, bins="fd")
                    np.testing.assert_array_equal([p.get_height() for p in ax.patches], expected_counts)
                    np.testing.assert_allclose([p.get_x() for p in ax.patches], expected_edges[:-1])
                    np.testing.assert_allclose([p.get_width() for p in ax.patches], np.diff(expected_edges))
                    counts.append({"indicator": ident, "n": len(values), "xlim": list(ax.get_xlim()), "ylim": list(ax.get_ylim())})
                old = figure.texts[-1].get_text()
                figure.texts[-1].set_text(old + "\nContextual indicators of household composition, housing space and age structure; not direct measures of deprivation.")
                evidence["figure3"] = {"panels": counts, "original_data_bins_and_scales_preserved": True}
                output = NAMES[2]
            return original_save(figure, stage / output, *args, **kwargs)

        try:
            base.FIGURES = stage
            plt.Figure.savefig = save_revised
            base.figures(master, correlation)
        finally:
            plt.Figure.savefig = original_save
            base.FIGURES = original_dest
        outputs = {}
        for name in NAMES:
            target = DEST / name
            generated = stage / name
            assert generated.is_file()
            if target.exists():
                assert target.read_bytes() == generated.read_bytes(), f"Refusing to replace existing revised figure: {target}"
            else:
                with target.open("xb") as f:
                    f.write(generated.read_bytes())
            outputs[str(target.relative_to(ROOT))] = base.digest(target)
        selection = {"rule": "Five highest and five lowest unemployment observations among the 79 Ortsteile with both economic indicators; code is a deterministic secondary sort, no boundary ties present.",
                     "highest": high[["geo_code", "geo_name"]].to_dict("records"),
                     "lowest": low[["geo_code", "geo_name"]].to_dict("records"), "representative": False}
        manifest = {"generator": "src/refine_section2_figures.py", "script_sha256": base.digest(Path(__file__)),
                    "baseline_manifest_sha256": base.digest(REPORT / "reproducibility_manifest.json"),
                    "selection": selection, "validation": evidence, "outputs": outputs}
        path = REPORT / "visualization_refinement_manifest.json"
        content = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
        if path.exists():
            assert path.read_text(encoding="utf-8") == content, "Refusing to overwrite changed visualization manifest"
        else:
            with path.open("x", encoding="utf-8") as f:
                f.write(content)
    for name, expected in protected.items():
        assert base.digest(ROOT / name) == expected, f"Protected file changed: {name}"
    print(json.dumps(selection, ensure_ascii=False, indent=2))
    print("PASS: selection, scatter coordinates, stored correlation, contextual panel bins/scales and protected-file hashes.")


if __name__ == "__main__":
    main()
