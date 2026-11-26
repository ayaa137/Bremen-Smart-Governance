import copy
from hashlib import sha256
import json
from pathlib import Path
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
