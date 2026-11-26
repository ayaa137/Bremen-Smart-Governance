import csv
from decimal import Decimal
from hashlib import sha256
from html import escape, unescape
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
from tempfile import TemporaryDirectory
import unittest

import build_dashboard as dashboard


class ResourceReferences(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        self.urls.extend(value for name, value in attrs if name in {"src", "href"})


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (dashboard.RELEASE / "neighborhoods.csv").open(encoding="utf-8", newline="") as stream:
            cls.rows = {row["geo_code"]: row for row in csv.DictReader(stream)}
        cls.payload = dashboard.build_page()
        cls.page = cls.payload.decode("utf-8")
        cls.panels = dict(re.findall(r'<article class="detail" id="ortsteil-(\d{3})"[^>]*>(.*?)</article>',
                                     cls.page, re.S))

    def test_directory_contains_all_88_neighborhoods(self):
        directory = re.findall(r'<tr data-code="(\d{3})" data-name="([^"]+)" data-eligible="(True|False)">',
                               self.page)
        self.assertEqual(len(directory), 88)
        self.assertEqual({code: (unescape(name), eligible) for code, name, eligible in directory},
                         {code: (row["geo_name"], row["scoring_eligible"])
                          for code, row in self.rows.items()})
        self.assertEqual(set(self.panels), set(self.rows))
        self.assertEqual(len(self.panels), 88)

    def test_79_scored_panels_preserve_saved_methods_and_values(self):
        scored = {code: row for code, row in self.rows.items() if row["scoring_eligible"] == "True"}
        self.assertEqual(len(scored), 79)
        for code, row in scored.items():
            with self.subTest(code=code):
                panel = self.panels[code]
                self.assertIn(">Scored</span>", panel)
                for key in (*dashboard.INDICATORS, *dashboard.SCORES, "floor_area_m2_per_resident"):
                    match = re.search(rf'data-field="{key}">.*?data-saved="([^"]+)">([^<]+)', panel, re.S)
                    self.assertIsNotNone(match)
                    raw, shown = match.groups()
                    self.assertEqual(unescape(raw), row[key])
                    if key in dashboard.INDICATORS:
                        self.assertEqual(shown, f"{Decimal(row[key]):.4f}%")
                    elif key.endswith("_score"):
                        self.assertEqual(shown, f"{Decimal(row[key]):.4f}")
                    elif key == "floor_area_m2_per_resident":
                        self.assertEqual(shown, f"{Decimal(row[key]):.2f} m²")
                    else:
                        self.assertEqual(shown, row[key])

    def test_nine_exclusions_have_reasons_and_never_acquire_scores(self):
        excluded = {code: row for code, row in self.rows.items() if row["scoring_eligible"] == "False"}
        self.assertEqual(len(excluded), 9)
        for code, row in excluded.items():
            with self.subTest(code=code):
                panel = self.panels[code]
                self.assertIn(">Excluded</span>", panel)
                self.assertIn(escape(dashboard.reason(row)), panel)
                for key in (*dashboard.INDICATORS, *dashboard.SCORES, "floor_area_m2_per_resident"):
                    value = re.search(rf'data-field="{key}">(.*?)</dd>', panel, re.S).group(1)
                    if row[key]:
                        self.assertIn(f'data-saved="{row[key]}"', value)
                    else:
                        self.assertIn('data-missing="true">Unavailable', value)
                        self.assertNotIn("data-saved=", value)
        self.assertIn("View 9 exclusion reasons", self.page)

    def test_five_candidates_are_all_proposed_and_unvisited(self):
        candidates = re.findall(r'<tr class="fieldwork-row">.*?<a href="#ortsteil-(\d{3})".*?<code>([^<]+)</code>',
                                self.page)
        self.assertEqual(len(candidates), 5)
        self.assertEqual({code for code, _ in candidates},
                         {code for code, row in self.rows.items() if row["fieldwork_status"]})
        self.assertEqual({status for _, status in candidates}, {"proposed_not_visited"})

    def test_spatial_results_appear_only_at_release_level(self):
        with (dashboard.RELEASE / "spatial_summary.csv").open(encoding="utf-8", newline="") as stream:
            source = list(csv.DictReader(stream))
        self.assertEqual([row["seed"] for row in source], ["2024", "2024"])
        self.assertIn("Permutation seed 2024.", self.page)
        spatial = re.search(r'<tbody id="spatial-results">(.*?)</tbody>', self.page, re.S).group(1)
        actual = re.findall(r'<th scope="row">(\d+)</th><td>(\d+)</td>'
                            r'<td><span data-saved="([^"]+)">([^<]+)</span></td>'
                            r'<td><span data-saved="([^"]+)">([^<]+)</span></td>'
                            r'<td>(\d+)</td>', spatial)
        self.assertEqual(actual, [
            ("4", "79", "0.29918123088903403", "0.299181", "0.0001", "0.0001", "9999"),
            ("6", "79", "0.20072149377376158", "0.200721", "0.0011", "0.0011", "9999"),
        ])
        self.assertEqual([(k, n, value, p, permutations)
                          for k, n, value, _, p, _, permutations in actual],
                         [(row["k"], row["n"], row["morans_i"], row["p_two_sided"], row["permutations"])
                          for row in source])
        self.assertTrue(all("Moran" not in panel for panel in self.panels.values()))

    def test_spatial_table_has_monte_carlo_caveat(self):
        card = re.search(r'<article class="card content-card">\s*<h3>Global Moran.*?</article>',
                         self.page, re.S).group(0)
        self.assertIn('aria-describedby="spatial-monte-carlo"', card)
        note = re.search(r'<p class="muted" id="spatial-monte-carlo">([^<]+)</p>', card).group(1)
        for phrase in ("9,999 permutations", "plus-one correction", "0.0001 is the smallest attainable p-value",
                       "Zero extreme permutations still give an estimate of 0.0001",
                       "simulation uncertainty", "underlying p-value may be smaller or larger"):
            self.assertIn(phrase, note)
        self.assertTrue(all("spatial-monte-carlo" not in panel for panel in self.panels.values()))

    def test_displayed_coverage_distinguishes_housing_from_neighborhoods(self):
        for label, count in (("represented", 88), ("scored", 79), ("excluded", 9)):
            self.assertIn(f'<dd id="{label}-count">{count}</dd>', self.page)
        housing = re.findall(r'data-field="floor_area_m2_per_resident"><span data-saved=', self.page)
        self.assertEqual(len(housing), 79)
        self.assertIn('alt="Scatterplot of 79 scored Bremen neighborhoods', self.page)

    def test_html_is_deterministic_and_self_contained(self):
        rebuilt = dashboard.build_page()
        self.assertEqual(sha256(rebuilt).hexdigest(), sha256(self.payload).hexdigest())
        self.assertNotRegex(self.page, r"(?m)[ \t]+$")
        parser = ResourceReferences()
        parser.feed(self.page)
        self.assertEqual(sum(url.startswith("data:image/png;base64,") for url in parser.urls), 1)
        self.assertTrue(all(url.startswith(("#", "data:image/png;base64,")) for url in parser.urls))
        self.assertIn("default-src 'none'", self.page)

    def test_build_rejects_either_modified_release_csv_before_rendering(self):
        for name in ("neighborhoods.csv", "spatial_summary.csv"):
            with self.subTest(name=name), TemporaryDirectory() as temp:
                copied = Path(temp)
                for source in ("manifest.json", "neighborhoods.csv", "spatial_summary.csv"):
                    shutil.copyfile(dashboard.RELEASE / source, copied / source)
                with (copied / name).open("ab") as stream:
                    stream.write(b"\n")
                with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                    dashboard.build_page(directory=copied)

    def test_build_rejects_modified_figure(self):
        with TemporaryDirectory() as temp:
            figure = Path(temp) / "housing_benchmark.png"
            figure.write_bytes(dashboard.FIGURE.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch for housing_benchmark.png"):
                dashboard.build_page(figure=figure)


if __name__ == "__main__":
    unittest.main()
