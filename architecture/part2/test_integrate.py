import copy
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import integrate as workflow


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables, cls.commit, cls.hashes = workflow.load_inputs(workflow.ROOT)

    def setUp(self):
        self.inputs = copy.deepcopy(self.tables)

    def test_saved_outputs_join_without_losing_exclusions(self):
        neighborhoods, spatial = workflow.integrate(self.inputs)
        self.assertEqual(len(neighborhoods), 88)
        self.assertEqual(len({(row["geo_code"], row["year"]) for row in neighborhoods}), 88)
        self.assertTrue(all(row["year"] == "2024" and len(row["geo_code"]) == 3 for row in neighborhoods))
        self.assertEqual([row["k"] for row in spatial], ["4", "6"])
        self.assertNotIn("morans_i", neighborhoods[0])

        source = {name: {row["geo_code"]: row for row in rows}
                  for name, rows in self.inputs.items() if name != "spatial"}
        excluded = 0
        candidates = 0
        for row in neighborhoods:
            code = row["geo_code"]
            spine = source["spine"][code]
            self.assertEqual({field: row[field] for field in spine}, spine)
            if spine["scoring_eligible"] == "True":
                for method in ("composite", "topsis"):
                    self.assertEqual(row[f"{method}_score"], source[method][code][f"{method}_score"])
                    self.assertEqual(row[f"{method}_rank"], source[method][code]["rank"])
                self.assertEqual(row["cluster"], source["clusters"][code]["cluster"])
                self.assertEqual(row["floor_area_m2_per_resident"],
                                 source["housing"][code]["floor_area_m2_per_resident"])
            else:
                excluded += 1
                self.assertTrue(row["exclusion_reason"])
                self.assertTrue(all(row[field] == "" for field in (
                    "composite_score", "composite_rank", "topsis_score", "topsis_rank",
                    "cluster", "floor_area_m2_per_resident",
                )))
            self.assertEqual(row["fieldwork_status"], source["fieldwork"].get(code, {}).get("fieldwork_status", ""))
            candidates += row["fieldwork_status"] == "proposed_not_visited"
        self.assertEqual((excluded, candidates), (9, 5))

    def test_unexpected_csv_schema_fails(self):
        payload = workflow.csv_bytes(self.inputs["composite"])
        with self.assertRaisesRegex(ValueError, "unexpected CSV columns"):
            workflow.read_csv(payload, "topsis")

    def test_duplicate_neighborhood_key_fails(self):
        self.inputs["composite"].append(self.inputs["composite"][0])
        with self.assertRaisesRegex(ValueError, "duplicate neighborhood key"):
            workflow.integrate(self.inputs)

    def test_missing_housing_row_fails(self):
        self.inputs["housing"].pop()
        with self.assertRaisesRegex(ValueError, "expected 79 rows, found 78"):
            workflow.integrate(self.inputs)

    def test_wrong_year_or_malformed_identifier_fails(self):
        for field, value in (("year", "2020"), ("geo_code", "11")):
            with self.subTest(field=field):
                inputs = copy.deepcopy(self.inputs)
                inputs["topsis"][0][field] = value
                with self.assertRaisesRegex(ValueError, "invalid neighborhood identity"):
                    workflow.integrate(inputs)

    def test_unmatched_fieldwork_code_fails(self):
        excluded = next(row for row in self.inputs["spine"] if row["scoring_eligible"] == "False")
        self.inputs["fieldwork"][0]["geo_code"] = excluded["geo_code"]
        with self.assertRaisesRegex(ValueError, "unmatched or ineligible neighborhood"):
            workflow.integrate(self.inputs)

    def test_fieldwork_status_must_be_preserved(self):
        self.inputs["fieldwork"][0]["fieldwork_status"] = ""
        with self.assertRaisesRegex(ValueError, "unexpected fieldwork role or status"):
            workflow.integrate(self.inputs)

    def test_nonfinite_value_fails(self):
        self.inputs["housing"][0]["floor_area_m2_per_resident"] = "NaN"
        with self.assertRaisesRegex(ValueError, "floor_area_m2_per_resident must be finite"):
            workflow.integrate(self.inputs)

    def test_inconsistent_exclusion_reason_fails(self):
        excluded = next(row for row in self.inputs["spine"] if row["scoring_eligible"] == "False")
        excluded["exclusion_reason"] = ""
        with self.assertRaisesRegex(ValueError, "eligibility or reason disagrees"):
            workflow.integrate(self.inputs)

    def test_housing_score_must_match_saved_composite(self):
        self.inputs["housing"][0]["composite_score"] = self.inputs["housing"][1]["composite_score"]
        with self.assertRaisesRegex(ValueError, "composite_score disagrees with saved composite_score"):
            workflow.integrate(self.inputs)

    def test_spatial_summary_must_match_saved_score_fingerprint(self):
        for row in self.inputs["spatial"]:
            row["sample_scores_sha256"] = row["centroids_sha256"]
        with self.assertRaisesRegex(ValueError, "score sample fingerprint disagrees"):
            workflow.integrate(self.inputs)

    def test_invalid_spatial_fields_fail_before_publication(self):
        cases = (
            ("morans_i", "12", "morans_i exceeds"),
            ("morans_i", "NaN", "morans_i must be finite"),
            ("permutation_null_mean", "-12", "permutation_null_mean exceeds"),
            ("p_two_sided", "0.7777", "inconsistent plus-one p-value"),
            ("p_two_sided", "0", "p_two_sided is outside"),
            ("p_minimum", "0.0002", "inconsistent p_minimum"),
            ("seed", "19", "seed is outside"),
            ("permutations", "1", "permutations is outside"),
            ("permutations", "9999.5", "permutations is outside"),
            ("extreme_permutations", "0.5", "extreme_permutations must be an integer"),
            ("extreme_permutations", "-1", "extreme_permutations is outside"),
            ("extreme_permutations", "10000", "extreme_permutations is outside"),
            ("theoretical_null_expectation", "-0.02", "inconsistent theoretical null expectation"),
            ("n", "78", "unexpected year or sample size"),
            ("k", "5", "expected one summary row"),
            ("weights", "binary_knn", "unexpected spatial weights or CRS"),
            ("p_definition", "one-sided", "unexpected p-value definition"),
            ("degree_min", "3", "degree_min is outside"),
            ("degree_mean", "5.1", "degree_mean disagrees"),
            ("component_sizes", "78", "inconsistent component sizes"),
            ("link_distance_mean_m", "Infinity", "link_distance_mean_m must be finite"),
            ("p_minimum", "", "missing summary field"),
        )
        self.assert_invalid_cases_do_not_publish("spatial", cases)

    def test_spatial_bound_does_not_assume_unit_range(self):
        # A synthetic value within the conservative bound is not proof it is attainable.
        self.inputs["spatial"][0]["morans_i"] = "1.1"
        workflow.integrate(self.inputs)

    def test_impossible_edge_counts_fail_before_publication(self):
        cases = [
            (row, self.edge_diagnostics(edges, maximum), "undirected_edges is outside")
            for row, edges, maximum in ((0, 157, 4), (0, 317, 12), (0, 350, 12),
                                        (1, 236, 6), (1, 475, 18))
        ]
        self.assert_invalid_rows_do_not_publish("spatial", cases)

    def test_degree_extrema_must_fit_total_degree(self):
        cases = [
            (0, self.edge_diagnostics(edges, maximum), "total degree disagrees")
            for edges, maximum in ((158, 5), (237, 6))
        ]
        self.assert_invalid_rows_do_not_publish("spatial", cases)

    def test_edge_and_degree_limits_are_inclusive(self):
        # These are boundary diagnostics, not reconstructed kNN graphs.
        for row, edges, maximum in ((0, 158, 4), (0, 316, 12), (1, 237, 6), (1, 474, 18),
                                    (0, 159, 6), (0, 236, 6)):
            with self.subTest(row=row, edges=edges, maximum=maximum):
                inputs = copy.deepcopy(self.inputs)
                inputs["spatial"][row].update(self.edge_diagnostics(edges, maximum))
                workflow.integrate(inputs)

    @staticmethod
    def edge_diagnostics(edges, maximum):
        return {"undirected_edges": str(edges), "degree_max": str(maximum),
                "degree_mean": str(Decimal(2 * edges) / 79)}

    def test_missing_or_duplicate_spatial_rows_fail(self):
        rows = self.inputs["spatial"]
        for bad_rows in ([rows[0]], [rows[0], rows[0]], [*rows, rows[1]]):
            with self.subTest(rows=len(bad_rows)):
                self.inputs["spatial"] = bad_rows
                with self.assertRaisesRegex(ValueError, "expected one summary row"):
                    workflow.integrate(self.inputs)

    def test_invalid_shortlist_fields_fail_before_publication(self):
        cases = (
            ("absolute_rank_gap", "12", "inconsistent absolute_rank_gap"),
            ("composite_rank", "2", "composite rank mismatch"),
            ("composite_weight_rank_min", "0", "composite_weight_rank_min is outside"),
            ("composite_weight_rank_max", "2", "rank bounds disagree with saved"),
            ("composite_weight_rank_max", "1.5", "composite_weight_rank_max must be an integer"),
            ("composite_weight_rank_span", "1", "inconsistent composite rank span"),
            ("topsis_weight_rank_span", "1", "inconsistent topsis rank span"),
            ("max_weight_rank_span", "1", "inconsistent max_weight_rank_span"),
            ("visit_priority", "2", "invalid or duplicate visit priority"),
            ("fieldwork_status", "visited", "unexpected fieldwork role or status"),
        )
        self.assert_invalid_cases_do_not_publish("fieldwork", cases)

    def test_missing_or_duplicate_source_rank_ranges_fail(self):
        for duplicate, message in ((False, "incomplete coverage"), (True, "duplicate rank range")):
            with self.subTest(duplicate=duplicate):
                inputs = copy.deepcopy(self.inputs)
                removed = inputs["ranges"].pop()
                if duplicate:
                    inputs["ranges"].append(inputs["ranges"][0])
                self.assertNotIn(removed, inputs["ranges"])
                with self.assertRaisesRegex(ValueError, message):
                    workflow.integrate(inputs)

    def assert_invalid_cases_do_not_publish(self, table, cases):
        self.assert_invalid_rows_do_not_publish(
            table, [(0, {field: value}, message) for field, value, message in cases]
        )

    def assert_invalid_rows_do_not_publish(self, table, cases):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            tracked = workflow.HERE / "releases" / workflow.RELEASE
            destination = root / "existing" / "releases" / workflow.RELEASE
            shutil.copytree(tracked, destination)
            original = {p.name: p.read_bytes() for p in destination.iterdir()}
            for row, updates, message in cases:
                inputs = copy.deepcopy(self.inputs)
                inputs[table][row].update(updates)
                for here in (root / "fresh", root / "existing"):
                    with self.subTest(row=row, updates=updates, destination=here.name):
                        with patch.object(workflow, "HERE", here), patch.object(
                            workflow, "load_inputs", return_value=(inputs, self.commit, self.hashes)
                        ), patch.object(workflow, "publish", wraps=workflow.publish) as publish:
                            with self.assertRaisesRegex(ValueError, message):
                                workflow.main()
                            publish.assert_not_called()
                        self.assertFalse((root / "fresh").exists())
                        self.assertEqual({p.name: p.read_bytes() for p in destination.iterdir()}, original)

    def test_release_hashes_and_non_overwriting_reruns(self):
        neighborhoods, spatial = workflow.integrate(self.inputs)
        outputs = workflow.release_files(neighborhoods, spatial, self.commit, self.hashes)
        manifest = json.loads(outputs["manifest.json"])
        self.assertEqual(manifest["source_git_commit"], self.commit)
        self.assertEqual(set(manifest["inputs_sha256"]), set(workflow.INPUTS.values()))
        for name in ("neighborhoods.csv", "spatial_summary.csv"):
            self.assertEqual(manifest["outputs_sha256"][name], sha256(outputs[name]).hexdigest())
        with TemporaryDirectory() as tmp:
            destination = Path(tmp) / workflow.RELEASE
            with patch.object(Path, "mkdir", autospec=True, side_effect=Path.mkdir) as mkdir:
                self.assertEqual(workflow.publish(destination, outputs), "Created")
            staged_parents = [call.args[0].parent for call in mkdir.call_args_list
                              if call.args[0] != destination.parent]
            self.assertEqual(staged_parents, [destination.parent])
            self.assertEqual(workflow.publish(destination, outputs), "Verified existing")
            changed = dict(outputs, **{"neighborhoods.csv": outputs["spatial_summary.csv"]})
            with self.assertRaisesRegex(ValueError, "Existing release differs"):
                workflow.publish(destination, changed)
            self.assertEqual({p.name: p.read_bytes() for p in destination.iterdir()}, outputs)


if __name__ == "__main__":
    unittest.main()
