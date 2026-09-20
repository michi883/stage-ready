"""The demo is deterministic and the loop enforces its guarantees. Standard library only."""
import json
import unittest

from stage_ready.backends import get_backend
from stage_ready.backends.cached import CLIPS as FIXTURE_ROOT, CachedBackend, FixtureMissing
from stage_ready.loop import run
from stage_ready.models import Decision, VerifyResult, Gate
from stage_ready.profile import Profile


CLIPS = ("sandy", "ethel", "zach", "zach_padded")


def trace(clip_id, backend=None):
    backend = backend or get_backend(demo=True)
    return list(run(backend.clip(clip_id), Profile.load(), backend))


class DemoPaths(unittest.TestCase):
    EXPECTED = {   # the lineup, in billing order — three agent behaviours, each recording's own path
        "sandy": ("reshoot", ["inspect", "fix", "inspect", "process", "verify ✗", "reshoot"]),               # fix what can be fixed, then catch what cannot
        "ethel": ("delivered", ["inspect", "process", "verify ✗", "reprocess", "verify ✓", "deliver"]),     # adapt and recover
        "zach": ("delivered", ["inspect", "process", "verify ✓", "deliver"]),                                # already suitable: verified on the first pass
        "zach_padded": ("delivered", ["inspect", "fix", "inspect", "process", "verify ✓", "deliver"]),       # controlled input: fix what was injected, then verified
    }
    DELIVERED = ("ethel", "zach", "zach_padded")

    def test_three_paths(self):
        for cid, (outcome, path) in self.EXPECTED.items():
            end = trace(cid)[-1]
            self.assertEqual(end["type"], "run.end", cid)
            self.assertEqual(end["outcome"], outcome, cid)
            self.assertEqual(end["path"], path, cid)

    def test_deterministic(self):
        for cid in CLIPS:
            a = json.dumps(trace(cid), sort_keys=True)
            b = json.dumps(trace(cid), sort_keys=True)
            self.assertEqual(a, b, cid)

    def test_every_process_is_verified_and_every_fix_reinspected(self):
        for cid in CLIPS:
            evs = [e["type"] for e in trace(cid)]
            for i, t in enumerate(evs):
                if t == "process.result":
                    self.assertEqual(evs[i + 1], "phase"); self.assertEqual(evs[i + 2], "verify.result")
                if t == "fix.result":
                    self.assertEqual(evs[i + 1], "phase"); self.assertEqual(evs[i + 2], "inspect.result")

    def test_ethel_changes_strategy_after_failed_verification(self):
        evs = trace("ethel")
        verifies = [e for e in evs if e["type"] == "verify.result"]
        self.assertFalse(verifies[0]["passed"]); self.assertTrue(verifies[1]["passed"])
        self.assertEqual([g["id"] for g in verifies[0]["result"]["failing"]], ["separation"])
        strategies = [e["result"]["strategy"] for e in evs if e["type"] == "process.result"]
        self.assertEqual(strategies, ["process.standard", "process.separation_targeted"])
        self.assertEqual(evs[-1]["delivery"]["budget"], {"reprocesses_used": 1, "retry_budget": 2})

    def test_sandy_fix_resolves_without_new_defects(self):
        evs = trace("sandy")
        after = [e for e in evs if e["type"] == "inspect.result" and e["result"]["target"] == "fixed"][0]
        self.assertEqual(after["resolved"], ["picture_area", "subject_size"])
        self.assertEqual(after["new_defects"], [])
        self.assertEqual([e["result"]["strategy"] for e in evs if e["type"] == "fix.result"], ["fix.reframe"])

    def test_zach_is_verified_on_the_first_pass(self):
        # The alternate take (zach_sain_v1, mint trousers): every gate on the first attempt, no fix,
        # no retry — the trousers carry the outline the black shirt does not (separation 2.37x).
        evs = trace("zach")
        v = [e for e in evs if e["type"] == "verify.result"]
        self.assertEqual(len(v), 1); self.assertTrue(v[0]["passed"])
        m = evs[-1]["delivery"]["measurements"]
        self.assertEqual((m["separation"], m["frames"]), (2.37, 1800))
        self.assertEqual(evs[-1]["delivery"]["budget"], {"reprocesses_used": 0, "retry_budget": 2})
        warns = [f["id"] for f in [e for e in evs if e["type"] == "inspect.result"][0]["result"]["findings"] if f["status"] == "warn"]
        self.assertEqual(warns, ["headroom", "face_exposure"])                     # honest notes, not defects

    def test_sandy_reshoot_names_the_cause_first(self):
        # The gates that fail are head height; the cause is the walk-in INSPECT warned about, and
        # the request leads with it, so the guidance is "be at your final distance", not "tripod".
        end = trace("sandy")[-1]
        v = [e for e in trace("sandy") if e["type"] == "verify.result"][-1]
        self.assertEqual([g["id"] for g in v["result"]["failing"]], ["head_spread", "head_drift"])
        items = end["reshoot"]["items"]
        self.assertEqual([i["id"] for i in items], ["distance_steady", "head_spread", "head_drift"])
        self.assertTrue(items[0]["cause"])
        self.assertIn("final distance", items[0]["guidance"])
        self.assertEqual(end["reshoot"]["budget"], {"reprocesses_used": 0, "retry_budget": 2})

    def test_outputs_agree_on_the_profile(self):
        for cid in self.DELIVERED:
            m = trace(cid)[-1]["delivery"]["measurements"]
            self.assertGreaterEqual(m["separation"], 1.5)
            self.assertLessEqual(m["head_spread"], 0.02)
            self.assertLessEqual(m["shoulder_span_p50"], 0.55)

    def test_verify_gate_list_is_the_profiles(self):
        want = [g["id"] for g in Profile.load().gates]
        for cid in CLIPS:
            for e in trace(cid):
                if e["type"] == "verify.result":
                    self.assertEqual([g["id"] for g in e["result"]["gates"]], want)

    def test_no_number_is_ahead_of_its_measurement(self):
        # A fixture may say it is projected (the UI then tags it), but none is allowed to be:
        # Ethel's second attempt was the last one, measured 2026-09-19 at 1.52x (separation.log).
        # And every recording's numbers are its own: no fixture carries another clip's measurements.
        for path in sorted(FIXTURE_ROOT.glob("*/clip.json")):
            fx = json.load(path.open()).get("fixture", "")
            self.assertNotIn("measurements:", fx, f"{path.parent.name} substitutes another recording's numbers")
        # every derived demo input names its original, hash, time range and edits (demo/derived.json)
        import pathlib
        derived = json.load(open(pathlib.Path(FIXTURE_ROOT).parent / "derived.json"))["derived"]
        for path in sorted(FIXTURE_ROOT.glob("*/clip.json")):
            rec = json.load(path.open())["recognize"]
            if "derived_from" in rec:
                d = rec["derived_from"]
                self.assertTrue(d.get("file") and d.get("sha256") and d.get("time_range") and d.get("edits"), path.parent.name)
                self.assertTrue(any(x["original_sha256"] == d["sha256"] for x in derived.values()), f"{path.parent.name}: derivation not in demo/derived.json")
        for path in sorted(FIXTURE_ROOT.glob("*/*.json")):
            prov = json.load(path.open()).get("provenance", "")
            self.assertFalse(prov.startswith("PROJECTED"), f"{path.name} is projected: {prov[:80]}")
        m = trace("ethel")[-1]["delivery"]["measurements"]
        self.assertEqual((m["separation"], m["edge_luma_in"], m["edge_luma_out"]), (1.52, 0.188, 0.123))


class Recognition(unittest.TestCase):
    """An upload is matched to a known clip the way the live matte cache is keyed: by SHA-256."""

    def test_lineup_order_and_fingerprints(self):
        clips = get_backend(demo=True).clips()
        self.assertEqual([c.id for c in clips], ["sandy", "ethel", "zach", "zach_padded"])   # midtownshow.com/2040 + the controlled input (lineup placement pending)
        for c in clips:
            hashes = c.recognize.get("sha256")
            for x in ([hashes] if isinstance(hashes, str) else hashes):
                self.assertRegex(x, r"^[0-9a-f]{64}$", c.id)
            self.assertTrue(c.recognize.get("names"), c.id)

    def test_by_sha256_beats_name(self):
        b = get_backend(demo=True)
        sha = b.clip("sandy").recognize["sha256"]
        c = b.recognize(sha256=sha.upper(), name="ethel_chadwick.mp4")   # the name says Ethel; the bytes say Sandy
        self.assertEqual(c.id, "sandy")
        self.assertEqual(c.recognize["matched_by"], "sha256")

    def test_by_name_alias_case_insensitive(self):
        c = get_backend(demo=True).recognize(name="/Volumes/cam/ETHEL_CHADWICK.MP4")
        self.assertEqual(c.id, "ethel")
        self.assertEqual(c.recognize["matched_by"], "name")

    def test_a_derived_input_is_recognised_by_its_own_hash_not_its_originals(self):
        # zach_sain_v1_demo.mp4 is derived from zach_sain_v1.mov (demo/derived.json): the demo replays
        # the derived file's run; the original take is a different file and is not matched to it.
        b = get_backend(demo=True)
        c = b.clip("zach")
        self.assertEqual(b.recognize(sha256=c.recognize["sha256"]).id, "zach")
        self.assertIsNone(b.recognize(sha256=c.recognize["derived_from"]["sha256"]))
        self.assertNotIn("zach_sain_v1.mov", [n.lower() for n in c.recognize["names"]])

    def test_unknown_is_none_not_a_guess(self):
        self.assertIsNone(get_backend(demo=True).recognize(sha256="00" * 32, name="holiday.mp4"))
        self.assertIsNone(get_backend(demo=True).recognize())

    def test_live_local_mode_has_no_agent_and_no_lookup(self):
        # STAGE_READY_LIVE_LOCAL=1: the laptop measures, nobody decides, nothing is looked up on S3.
        from stage_ready.backends.live import LiveBackend, LiveNotWired, SubjectSegmenter
        from stage_ready.vision import OpenCVMissing
        from stage_ready.vision.segment import ModelMissing
        b = LiveBackend(local=True)
        with self.assertRaises(LiveNotWired):
            b.recognize(sha256="00" * 32)
        with self.assertRaises(LiveNotWired):
            b.decide(None, Profile.load(), None)
        # The DNN seam refuses plainly rather than guessing: no OpenCV 5, or no model file.
        with self.assertRaises((OpenCVMissing, ModelMissing)):
            SubjectSegmenter(model="/nonexistent/model.onnx")

    def test_s3_layout_is_keyed_by_source_hash(self):
        # Every prefix is the source's SHA-256 — the matte cache's key — and the workdir keeps the archive's layout.
        from stage_ready.aws import artifact_key, measurement_key, run_key, s3_archive_block, source_key, work_prefix
        c = get_backend(demo=True).clip("ethel")
        sha = c.recognize["sha256"]
        blk = s3_archive_block(c.archive, sha)
        self.assertEqual(blk["workdir"], f"work/{sha}")
        self.assertEqual(blk["source"], f"sources/{sha}/source.mp4")
        self.assertEqual(blk["artifacts"]["attempt_2"], {"video": f"artifacts/{sha}/attempt_2.mp4", "composite": "comp_sep"})
        self.assertEqual((source_key(sha, ".mov"), work_prefix(sha), artifact_key(sha, "attempt_1")),
                         (f"sources/{sha}/source.mov", f"work/{sha}", f"artifacts/{sha}/attempt_1.mp4"))
        self.assertEqual(measurement_key(sha, "verify", "attempt_1"), f"measurements/{sha}/verify.attempt_1.json")
        self.assertTrue(run_key(sha, "r1").startswith(f"runs/{sha}/"))

    def test_decision_tool_schema_matches_the_record(self):
        from stage_ready.models import DECISION_TOOL_SCHEMA, Decision
        import dataclasses
        fields = {f.name for f in dataclasses.fields(Decision)} - {"model", "duration_ms", "cached"}
        self.assertEqual(set(DECISION_TOOL_SCHEMA["properties"]), fields)
        self.assertEqual(DECISION_TOOL_SCHEMA["properties"]["action"]["enum"], ["inspect", "fix", "process", "deliver", "reshoot"])


class Guardrails(unittest.TestCase):
    """The loop, not the agent, owns the exits."""

    class Scripted(CachedBackend):
        name = "scripted"
        def __init__(self, decisions):
            self._d = list(decisions)
        def decide(self, clip, profile, state):
            return self._d.pop(0)

    def test_deliver_refused_before_any_verification(self):
        # Ethel's own path (standard fails, the retry passes), with a premature deliver in front of it.
        b = self.Scripted([Decision(action="deliver", reasoning="premature"),
                           Decision(action="process", strategy="process.standard", reasoning="ok"),
                           Decision(action="process", strategy="process.separation_targeted", reasoning="retry"),
                           Decision(action="deliver", reasoning="ok")])
        evs = list(run(b.clip("ethel"), Profile.load(), b))
        guards = [e for e in evs if e["type"] == "guard"]
        self.assertEqual(len(guards), 1)
        self.assertIn("nothing has been verified", guards[0]["reason"])
        self.assertEqual(evs[-1]["outcome"], "delivered")

    def test_unknown_strategy_refused(self):
        b = self.Scripted([Decision(action="process", strategy="process.magic", reasoning="?"),
                           Decision(action="process", strategy="process.standard", reasoning="ok"),
                           Decision(action="process", strategy="process.separation_targeted", reasoning="retry"),
                           Decision(action="deliver", reasoning="ok")])
        evs = list(run(b.clip("ethel"), Profile.load(), b))
        self.assertIn("not in the profile", [e for e in evs if e["type"] == "guard"][0]["reason"])
        self.assertEqual(evs[-1]["outcome"], "delivered")

    def test_spent_budget_ends_in_reshoot_request(self):
        # Ethel with a retry budget of zero: the first failed verification is the end of the road.
        p = Profile.load(); p.data["retry_budget"] = 0
        b = self.Scripted([Decision(action="process", strategy="process.standard", reasoning="first"),
                           Decision(action="process", strategy="process.separation_targeted", reasoning="retry")])
        evs = list(run(b.clip("ethel"), p, b))
        end = evs[-1]
        self.assertEqual(end["outcome"], "reshoot")
        self.assertEqual([i["id"] for i in end["reshoot"]["items"]], ["separation"])
        self.assertIn("wear", end["reshoot"]["items"][0]["guidance"].lower())
        self.assertEqual(end["path"], ["inspect", "process", "verify ✗", "reshoot"])

    def test_missing_fixture_is_loud(self):
        b = self.Scripted([Decision(action="fix", strategy="fix.reframe", reasoning="no fixture for Zach")])
        with self.assertRaises(FixtureMissing):
            list(run(b.clip("ethel"), Profile.load(), b))


if __name__ == "__main__":
    unittest.main()
