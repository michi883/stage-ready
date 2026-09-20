"""The evaluation's scoring and the rule-table agent, on the fixtures. Standard library only."""
import json
import unittest

from stage_ready import rules_agent
from stage_ready.backends.cached import CachedBackend
from stage_ready.evaluate import _score, load_set
from stage_ready.loop import run
from stage_ready.profile import Profile


class RulesBackend(CachedBackend):
    """The cached measurements with the rule table choosing — the ablation over the fixtures."""
    name = "cached+rules"

    def decide(self, clip, profile, state):
        return rules_agent.decide(profile, state)


class RuleTable(unittest.TestCase):
    def test_reproduces_every_fixture_path(self):
        # On the five recorded runs the rule table lands on the same path the agent chose — the
        # ablation's baseline; where they differ on the evaluation set is what EVALUATION.md reports.
        prof = Profile.load()
        for clip in CachedBackend().clips():
            agent = list(run(clip, prof, CachedBackend()))[-1]
            rules = list(run(clip, prof, RulesBackend()))[-1]
            self.assertEqual(rules["path"], agent["path"], clip.id)
            self.assertEqual(rules["outcome"], agent["outcome"], clip.id)

    def test_every_decision_cites_and_is_allowed(self):
        prof = Profile.load()
        for clip in CachedBackend().clips():
            evs = list(run(clip, prof, RulesBackend()))
            self.assertFalse([e for e in evs if e["type"] == "guard"], clip.id)      # nothing the loop had to refuse
            for e in evs:
                if e["type"] == "decide.result":
                    d = e["decision"]
                    d = d if isinstance(d, dict) else d.__dict__
                    self.assertEqual(d["model"], "rules")
                    self.assertTrue(d["reasoning"].startswith("Rule"), d["reasoning"])


class Scoring(unittest.TestCase):
    def setUp(self):
        self.dm = load_set()["defect_map"]

    def test_labels_are_set_for_every_item_and_map_to_findings(self):
        s = load_set()
        ids = [i["id"] for i in s["items"]]
        self.assertEqual(len(ids), len(set(ids)))
        for it in s["items"]:
            self.assertIn(it["labels"]["expected_outcome"], ("deliver", "reshoot", "either", "reject"), it["id"])
            for d in it["labels"]["defects"]:
                self.assertIn(d, self.dm, f"{it['id']}: unknown defect {d}")
            self.assertTrue(it["labels"]["why"], it["id"])
            self.assertIn("attempt_1", it["archive"]["artifacts"], it["id"])

    def test_a_delivery_the_label_forbids_is_silently_wrong(self):
        out = {"id": "x", "kind": "real", "outcome": "delivered", "labels": {"defects": ["pillarbox"], "expected_outcome": "reshoot"},
               "inspect": [{"findings": [{"id": "picture_area", "status": "fail"}]}], "verify": [{"gates": []}]}
        sc = _score(out, self.dm)["score"]
        self.assertTrue(sc["silently_wrong"]); self.assertFalse(sc["outcome_ok"])
        self.assertTrue(sc["detections"]["pillarbox"]["detected"]); self.assertEqual(sc["missed"], [])

    def test_a_defective_delivery_every_gate_passed_is_silently_wrong(self):
        out = {"id": "g", "kind": "gate", "outcome": "delivered", "labels": {"defects": ["frames_frozen"], "expected_outcome": "reject"},
               "verify": [{"gates": [{"id": "frame_count", "status": "pass"}]}]}
        sc = _score(out, self.dm)["score"]
        self.assertTrue(sc["silently_wrong"])
        self.assertFalse(sc["detections"]["frames_frozen"]["detected"])

    def test_a_refusal_before_the_loop_is_the_reshoot_exit_and_measures_nothing(self):
        out = {"id": "r", "kind": "real", "outcome": "refused", "refusal": "pose QC failed (above)", "labels": {"defects": ["two_subjects", "crown_cut"], "expected_outcome": "reshoot"}}
        sc = _score(out, self.dm)["score"]
        self.assertTrue(sc["outcome_ok"]); self.assertFalse(sc["silently_wrong"])
        self.assertTrue(sc["detections"]["two_subjects"]["detected"])          # the pipeline's pose QC is the one_subject measure
        self.assertIsNone(sc["detections"]["crown_cut"]["detected"])           # not measured, not missed
        self.assertEqual(sc["missed"], [])

    def test_either_accepts_both_exits_and_flags_unlabelled_findings(self):
        out = {"id": "e", "kind": "real", "outcome": "reshoot", "labels": {"defects": [], "expected_outcome": "either"},
               "inspect": [{"findings": [{"id": "headroom", "status": "warn"}, {"id": "pose_coverage", "status": "pass"}]}],
               "verify": [{"gates": [{"id": "separation", "status": "fail"}]}], "reshoot": {"items": []}}
        sc = _score(out, self.dm)["score"]
        self.assertTrue(sc["outcome_ok"])
        self.assertEqual(sc["unlabelled_flags"], ["headroom", "separation"])


if __name__ == "__main__":
    unittest.main()
