from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import gptmd_memory
import curation_learning


class CuratorMDTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "project"
        self.root.mkdir()
        (self.root / "persistence").mkdir()
        for filename in ("AGENTS.md", "SOP.md", "HISTORY.md", "LESSONS-LEARNED.md"):
            (self.root / "persistence" / filename).write_text(f"# {filename}\n", encoding="utf-8")
        (self.root / ".gitignore").write_text(".curatormd/\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "CuratorMD test"], cwd=self.root, check=True)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "baseline"], cwd=self.root, check=True)
        self.plugin_data = tempfile.TemporaryDirectory()
        self.old_plugin_data = os.environ.get("CURATORMD_PLUGIN_DATA")
        os.environ["CURATORMD_PLUGIN_DATA"] = self.plugin_data.name

    def tearDown(self):
        if self.old_plugin_data is None:
            os.environ.pop("CURATORMD_PLUGIN_DATA", None)
        else:
            os.environ["CURATORMD_PLUGIN_DATA"] = self.old_plugin_data
        self.plugin_data.cleanup()
        self.temp_dir.cleanup()

    def test_project_root_must_be_absolute_worktree_root(self):
        with self.assertRaises(gptmd_memory.CuratorError):
            gptmd_memory.resolve_project_root(".")
        with self.assertRaises(gptmd_memory.CuratorError):
            gptmd_memory.resolve_project_root(str(self.root / "persistence"))
        with self.assertRaises(gptmd_memory.CuratorError):
            gptmd_memory.resolve_project_root(str(Path(self.temp_dir.name)))
        alias = Path(self.temp_dir.name) / "project-alias"
        alias.symlink_to(self.root, target_is_directory=True)
        self.assertEqual(gptmd_memory.resolve_project_root(str(alias)), self.root.resolve())

    def test_snapshot_does_not_read_env_values(self):
        secret = "sk-test-secret-value-never-returned"
        (self.root / ".env").write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")
        snapshot = gptmd_memory.environment_snapshot(str(self.root))
        encoded = json.dumps(snapshot)
        self.assertNotIn(secret, encoded)
        self.assertNotIn(".env", json.dumps(snapshot["approved_manifests"]))

    def test_native_projection_redacts_and_is_idempotent(self):
        payload = {"response": "api_key=super-secret-value", "tool_names": ["git"]}
        first = gptmd_memory.native_projection_record(str(self.root), "test-source", "agent:end", payload, profile="test")
        second = gptmd_memory.native_projection_record(str(self.root), "test-source", "agent:end", payload, profile="test")
        self.assertTrue(first["written"])
        self.assertTrue(second["duplicate"])
        record = next((self.root / ".curatormd" / "native-inbox").glob("*.json")).read_text(encoding="utf-8")
        self.assertNotIn("super-secret-value", record)
        self.assertIn("[REDACTED]", record)
        self.assertEqual(json.loads(record)["payload"]["response"], "[REDACTED]")

    def test_pending_candidate_is_reprocessable_and_approved_once(self):
        payload = {
            "response": "Implemented a durable curation decision. api_key=super-secret-value",
            "message": "private task prompt",
            "provider": "openai-codex", "profile": "test", "model": "test-model",
            "result": {"activity_class": "implementation", "status": "success", "result_class": "change", "changed_project": True, "files_changed_count": 1},
        }
        capture = gptmd_memory.native_projection_record(str(self.root), "session-a", "agent:end", payload, profile="test")
        first = gptmd_memory.curate(str(self.root), profile="test")
        self.assertEqual(len(first["ambiguous"]), 1)
        inbox = self.root / ".curatormd" / "native-inbox" / f"{capture['record_id']}.json"
        stored = json.loads(inbox.read_text(encoding="utf-8"))
        self.assertFalse(stored.get("finalized", False))
        self.assertEqual(stored["payload"]["response"], "[REDACTED]")
        self.assertEqual(stored["payload"]["message"], "[REDACTED]")
        self.assertNotIn("private task prompt", inbox.read_text(encoding="utf-8"))
        pending = gptmd_memory.pending_reviews(self.root, "test")
        self.assertEqual(pending["records"][0]["record_id"], capture["record_id"])

        result = gptmd_memory.review_candidate(self.root, capture["record_id"], "approved", 3, "lessons", profile="test")
        self.assertTrue(result["reviewed"])
        duplicate = gptmd_memory.review_candidate(self.root, capture["record_id"], "approved", 3, "lessons", profile="test")
        self.assertTrue(duplicate["duplicate"])
        lesson = (self.root / "persistence" / "LESSONS-LEARNED.md").read_text(encoding="utf-8")
        self.assertEqual(lesson.count(f"record_id={capture['record_id']}"), 1)
        observation_dir = gptmd_memory._plugin_data_root(self.root, "test") / "learning" / "observations"
        observation = json.loads(next(observation_dir.glob("*.json")).read_text(encoding="utf-8"))
        self.assertEqual(observation["disposition"], "approved")
        self.assertEqual(observation["archive"], "lessons")
        self.assertFalse(any(key in observation["features"] for key in ("response", "message", "text")))

    def test_rejection_records_label_without_archive_write(self):
        capture = gptmd_memory.native_projection_record(
            str(self.root), "session-b", "agent:end",
            {"result": {"activity_class": "test", "status": "failure", "result_class": "failure", "failure_class": "test", "tests": {"executed": True, "failed": 1}}},
            profile="test",
        )
        gptmd_memory.curate(str(self.root), profile="test")
        before = {path.name: path.read_text(encoding="utf-8") for path in (self.root / "persistence").glob("*.md")}
        decision = gptmd_memory.review_candidate(self.root, capture["record_id"], "do-not-record", 0, profile="test")
        self.assertEqual(decision["disposition"], "do-not-record")
        after = {path.name: path.read_text(encoding="utf-8") for path in (self.root / "persistence").glob("*.md")}
        self.assertEqual(before, after)
        observation_dir = gptmd_memory._plugin_data_root(self.root, "test") / "learning" / "observations"
        observation = json.loads(next(observation_dir.glob("*.json")).read_text(encoding="utf-8"))
        self.assertIsNone(observation["archive"])
        self.assertIsNone(observation["corrections"]["archive_changed"])

    def test_review_correction_supersedes_label_without_rewriting_archive(self):
        capture = gptmd_memory.native_projection_record(
            str(self.root), "session-revision", "agent:end",
            {"result": {"activity_class": "implementation", "status": "success", "changed_project": True}},
            profile="test",
        )
        gptmd_memory.curate(str(self.root), profile="test")
        gptmd_memory.review_candidate(self.root, capture["record_id"], "approved", 2, "history", profile="test")
        history_before = (self.root / "persistence" / "HISTORY.md").read_text(encoding="utf-8")
        revised = gptmd_memory.review_candidate(self.root, capture["record_id"], "do-not-record", 1, profile="test")
        self.assertEqual(revised["review_revision"], 2)
        self.assertEqual((self.root / "persistence" / "HISTORY.md").read_text(encoding="utf-8"), history_before)
        observations = sorted((gptmd_memory._plugin_data_root(self.root, "test") / "learning" / "observations").glob("*.json"))
        first, second = [json.loads(path.read_text(encoding="utf-8")) for path in observations]
        self.assertFalse(first["active"])
        self.assertEqual(first["superseded_by_observation_id"], second["observation_id"])
        self.assertTrue(second["active"])
        self.assertEqual(second["disposition"], "do-not-record")
        self.assertEqual(curation_learning._active_rows(self.root, "test", curation_learning.datetime.now(curation_learning.timezone.utc))[0]["observation_id"], second["observation_id"])

    def test_pending_inbox_records_do_not_expire(self):
        capture = gptmd_memory.native_projection_record(str(self.root), "session-c", "agent:end", {"note": "pending"}, profile="test")
        path = self.root / ".curatormd" / "native-inbox" / f"{capture['record_id']}.json"
        old = 1_600_000_000
        os.utime(path, (old, old))
        self.assertEqual(gptmd_memory._cleanup_inbox(self.root), 0)
        self.assertTrue(path.exists())

    def test_curator_generated_edits_are_idempotent_and_appendable(self):
        first = gptmd_memory.append_entry(self.root, "history", "Stable", "Keep one copy.", profile="test")
        duplicate = gptmd_memory.append_entry(self.root, "history", "Stable", "Keep one copy.", profile="test")
        second = gptmd_memory.append_entry(self.root, "history", "Next", "Append after the curator's own uncommitted edit.", profile="test")
        self.assertTrue(first["written"])
        self.assertTrue(duplicate["duplicate"])
        self.assertTrue(second["written"])
        history = (self.root / "persistence" / "HISTORY.md").read_text(encoding="utf-8")
        self.assertEqual(history.count("Keep one copy."), 1)
        self.assertIn("Append after the curator's own uncommitted edit.", history)

    def test_concurrent_identical_capture_and_repository_isolation(self):
        payload = {"response": "A safe bounded result."}
        results = []
        threads = [threading.Thread(target=lambda: results.append(gptmd_memory.native_projection_record(str(self.root), "same-event", "agent:end", payload, profile="shared"))) for _ in range(8)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertEqual(sum(result["written"] for result in results), 1)
        self.assertEqual(sum(result["duplicate"] for result in results), 7)

        second_root = Path(self.temp_dir.name) / "second-project"
        second_root.mkdir()
        (second_root / "persistence").mkdir()
        for filename in ("AGENTS.md", "SOP.md", "HISTORY.md", "LESSONS-LEARNED.md"):
            (second_root / "persistence" / filename).write_text(f"# {filename}\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=second_root, check=True)
        subprocess.run(["git", "add", "."], cwd=second_root, check=True)
        subprocess.run(["git", "-c", "user.email=test@example.invalid", "-c", "user.name=CuratorMD test", "commit", "-qm", "baseline"], cwd=second_root, check=True)
        gptmd_memory.native_projection_record(str(second_root), "same-event", "agent:end", payload, profile="shared")
        self.assertNotEqual(gptmd_memory._state_path(self.root, "shared"), gptmd_memory._state_path(second_root, "shared"))

    def test_models_return_finite_normalized_probabilities(self):
        rows = []
        for i in range(48):
            rows.append({
                "features": {"activity_class": "test" if i % 2 else "implementation", "status": "failure" if i % 3 == 0 else "success", "tests_failed": i % 4},
                "approved_target": "approved" if i % 3 else "do-not-record",
                "disposition": "approved" if i % 3 else "do-not-record",
                "priority": i % 6,
                "archive_target": ("agents", "sop", "history", "lessons")[i % 4],
            })
        vocabulary = curation_learning._vocabulary([row["features"] for row in rows])
        vectors = [curation_learning._vector(row["features"], vocabulary) for row in rows]
        approval = curation_learning._fit_binary(rows, vectors, "approved_target")
        priority = curation_learning._fit_ordinal(rows, vectors)
        archive = curation_learning._fit_softmax(rows, vectors, "archive_target", list(curation_learning.ARCHIVES))
        probe = vectors[0]
        probabilities = [
            curation_learning._predict_binary(approval, probe),
            *map(float, curation_learning._predict_ordinal(priority, probe).values()),
            *map(float, curation_learning._predict_softmax(archive, probe).values()),
        ]
        self.assertTrue(all(0.0 <= value <= 1.0 for value in probabilities))
        self.assertAlmostEqual(sum(curation_learning._predict_ordinal(priority, probe).values()), 1.0, places=8)
        self.assertAlmostEqual(sum(curation_learning._predict_softmax(archive, probe).values()), 1.0, places=8)
        self.assertEqual(approval["status"], "fit")
        self.assertEqual(priority["status"], "fit")
        self.assertEqual(archive["status"], "fit")

    def test_qa_and_retrospective_records_are_distinct_and_idempotent(self):
        capture = gptmd_memory.native_projection_record(
            str(self.root), "session-d", "agent:end",
            {"result": {"activity_class": "debug", "status": "failure", "result_class": "failure", "failure_class": "runtime"}},
            profile="test",
        )
        gptmd_memory.curate(str(self.root), profile="test")
        gptmd_memory.review_candidate(self.root, capture["record_id"], "approved", 3, "lessons", profile="test")
        outcome = gptmd_memory.qa_outcome_record(self.root, capture["record_id"], "repeat_failure", 30, False, "No matching failure observed.", finalize_window=True, profile="test")
        duplicate = gptmd_memory.qa_outcome_record(self.root, capture["record_id"], "repeat_failure", 30, False, "No matching failure observed.", finalize_window=True, profile="test")
        self.assertTrue(outcome["written"])
        self.assertTrue(duplicate["duplicate"])
        windows = (60, 90, 180)
        concurrent = [threading.Thread(target=lambda window=window: gptmd_memory.qa_outcome_record(self.root, capture["record_id"], "repeat_failure", window, False, "No matching failure observed.", finalize_window=True, profile="test")) for window in windows]
        for thread in concurrent: thread.start()
        for thread in concurrent: thread.join()
        observation_path = next((gptmd_memory._plugin_data_root(self.root, "test") / "learning" / "observations").glob("*.json"))
        observation = json.loads(observation_path.read_text(encoding="utf-8"))
        self.assertEqual(observation["qa_finalized_windows"], [30, 60, 90, 180])
        self.assertTrue(observation["qa_windows_finalized"])
        self.assertTrue(gptmd_memory.retrospective_review(self.root, capture["record_id"], "yes", 2, "yes", profile="test")["written"])
        report = gptmd_memory.learning_recompute(self.root, "test", force=True)
        self.assertFalse(report["automation_enabled"])
        qa = gptmd_memory.learning_report(self.root, "test")["qa"]
        self.assertEqual(qa["retrospective_review_count"], 1)

    def test_unreviewed_projection_is_ambiguous_and_not_promoted(self):
        gptmd_memory.native_projection_record(str(self.root), "test-source", "agent:end", {"note": "candidate"}, profile="test")
        result = gptmd_memory.curate(str(self.root), profile="test")
        self.assertEqual(len(result["ambiguous"]), 1)
        self.assertEqual((self.root / "persistence" / "HISTORY.md").read_text(encoding="utf-8"), "# HISTORY.md\n")

    def test_reviewed_candidate_is_promoted(self):
        gptmd_memory.native_projection_record(str(self.root), "test-source", "agent:end", {"note": "candidate"}, profile="test")
        path = next((self.root / ".curatormd" / "native-inbox").glob("*.json"))
        record = json.loads(path.read_text(encoding="utf-8"))
        record["reviewed"] = True
        record["candidate"] = {
            "kind": "history",
            "title": "Reviewed test decision",
            "content": "Use the reviewed curation path.",
            "rationale": "The behavior was verified in the test harness.",
            "impact": "Future runs retain a durable decision.",
        }
        path.write_text(json.dumps(record), encoding="utf-8")
        result = gptmd_memory.curate(str(self.root), profile="test")
        self.assertEqual(len(result["written"]), 1)
        self.assertIn("Reviewed test decision", (self.root / "persistence" / "HISTORY.md").read_text(encoding="utf-8"))

    def test_uncommitted_knowledge_file_is_a_conflict(self):
        gptmd_memory.native_projection_record(str(self.root), "test-source", "agent:end", {"note": "candidate"}, profile="test")
        path = next((self.root / ".curatormd" / "native-inbox").glob("*.json"))
        record = json.loads(path.read_text(encoding="utf-8"))
        record["reviewed"] = True
        record["candidate"] = {"kind": "history", "title": "Blocked", "content": "Must not append."}
        path.write_text(json.dumps(record), encoding="utf-8")
        history = self.root / "persistence" / "HISTORY.md"
        history.write_text(history.read_text(encoding="utf-8") + "\nlocal edit\n", encoding="utf-8")
        result = gptmd_memory.curate(str(self.root), profile="test")
        self.assertEqual(len(result["conflicts"]), 1)
        self.assertNotIn("Blocked", history.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
