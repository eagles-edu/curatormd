"""Behavioral tests for the CuratorMD command-line and persistence runtime."""

# pyright: reportPrivateUsage=false
# pylint: disable=protected-access,too-many-public-methods,consider-using-with

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import curation_learning  # pylint: disable=wrong-import-position
import curatormd  # pylint: disable=wrong-import-position


class CuratorMDTests(unittest.TestCase):
    """Exercise repository isolation, review, and learning behavior."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "project"
        self.root.mkdir()
        (self.root / "persistence").mkdir()
        for filename in ("AGENTS.md", "SOP.md", "HISTORY.md", "LESSONS-LEARNED.md"):
            (self.root / "persistence" / filename).write_text(f"# {filename}\n", encoding="utf-8")
        (self.root / ".gitignore").write_text(".curatormd/\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.invalid"], cwd=self.root, check=True
        )
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
        """Reject relative paths and Git subdirectories as project roots."""
        with self.assertRaises(curatormd.CuratorError):
            curatormd.resolve_project_root(".")
        with self.assertRaises(curatormd.CuratorError):
            curatormd.resolve_project_root(str(self.root / "persistence"))
        with self.assertRaises(curatormd.CuratorError):
            curatormd.resolve_project_root(str(Path(self.temp_dir.name)))
        alias = Path(self.temp_dir.name) / "project-alias"
        alias.symlink_to(self.root, target_is_directory=True)
        self.assertEqual(curatormd.resolve_project_root(str(alias)), self.root.resolve())

    def test_snapshot_does_not_read_env_values(self):
        """Keep secret-bearing environment values out of snapshots."""
        secret = "sk-test-secret-value-never-returned"
        (self.root / ".env").write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")
        snapshot = curatormd.environment_snapshot(str(self.root))
        encoded = json.dumps(snapshot)
        self.assertNotIn(secret, encoded)
        self.assertNotIn(".env", json.dumps(snapshot["approved_manifests"]))

    def test_native_projection_redacts_and_is_idempotent(self):
        """Redact unsafe projection data and deduplicate repeated records."""
        payload = {"response": "api_key=super-secret-value", "tool_names": ["git"]}
        first = curatormd.native_projection_record(
            str(self.root), "test-source", "agent:end", payload, profile="test"
        )
        second = curatormd.native_projection_record(
            str(self.root), "test-source", "agent:end", payload, profile="test"
        )
        self.assertTrue(first["written"])
        self.assertTrue(second["duplicate"])
        record = next((self.root / ".curatormd" / "native-inbox").glob("*.json")).read_text(
            encoding="utf-8"
        )
        self.assertNotIn("super-secret-value", record)
        self.assertIn("[REDACTED]", record)
        self.assertEqual(json.loads(record)["payload"]["response"], "[REDACTED]")

    def test_pending_candidate_is_reprocessable_and_approved_once(self):
        """Keep pending candidates retryable and archive approved records once."""
        payload = {
            "response": "Implemented a durable curation decision. api_key=super-secret-value",
            "message": "private task prompt",
            "provider": "openai-codex",
            "profile": "test",
            "model": "test-model",
            "result": {
                "activity_class": "implementation",
                "status": "success",
                "result_class": "change",
                "changed_project": True,
                "files_changed_count": 1,
            },
        }
        capture = curatormd.native_projection_record(
            str(self.root), "session-a", "agent:end", payload, profile="test"
        )
        first = curatormd.curate(str(self.root), profile="test")
        self.assertEqual(len(first["ambiguous"]), 1)
        inbox = self.root / ".curatormd" / "native-inbox" / f"{capture['record_id']}.json"
        stored = json.loads(inbox.read_text(encoding="utf-8"))
        self.assertFalse(stored.get("finalized", False))
        self.assertEqual(stored["payload"]["response"], "[REDACTED]")
        self.assertEqual(stored["payload"]["message"], "[REDACTED]")
        self.assertNotIn("private task prompt", inbox.read_text(encoding="utf-8"))
        pending = curatormd.pending_reviews(self.root, "test")
        self.assertEqual(pending["records"][0]["record_id"], capture["record_id"])

        result = curatormd.review_candidate(
            self.root, capture["record_id"], "approved", 3, "lessons", profile="test"
        )
        self.assertTrue(result["reviewed"])
        duplicate = curatormd.review_candidate(
            self.root, capture["record_id"], "approved", 3, "lessons", profile="test"
        )
        self.assertTrue(duplicate["duplicate"])
        lesson = (self.root / "persistence" / "LESSONS-LEARNED.md").read_text(encoding="utf-8")
        self.assertEqual(lesson.count(f"record_id={capture['record_id']}"), 1)
        observation_dir = (
            curatormd._plugin_data_root(self.root, "test") / "learning" / "observations"
        )
        observation = json.loads(next(observation_dir.glob("*.json")).read_text(encoding="utf-8"))
        self.assertEqual(observation["disposition"], "approved")
        self.assertEqual(observation["archive"], "lessons")
        self.assertFalse(
            any(key in observation["features"] for key in ("response", "message", "text"))
        )

    def test_rejection_records_label_without_archive_write(self):
        """Record a rejection without changing canonical persistence."""
        capture = curatormd.native_projection_record(
            str(self.root),
            "session-b",
            "agent:end",
            {
                "result": {
                    "activity_class": "test",
                    "status": "failure",
                    "result_class": "failure",
                    "failure_class": "test",
                    "tests": {"executed": True, "failed": 1},
                }
            },
            profile="test",
        )
        curatormd.curate(str(self.root), profile="test")
        before = {
            path.name: path.read_text(encoding="utf-8")
            for path in (self.root / "persistence").glob("*.md")
        }
        decision = curatormd.review_candidate(
            self.root, capture["record_id"], "do-not-record", 0, profile="test"
        )
        self.assertEqual(decision["disposition"], "do-not-record")
        after = {
            path.name: path.read_text(encoding="utf-8")
            for path in (self.root / "persistence").glob("*.md")
        }
        self.assertEqual(before, after)
        observation_dir = (
            curatormd._plugin_data_root(self.root, "test") / "learning" / "observations"
        )
        observation = json.loads(next(observation_dir.glob("*.json")).read_text(encoding="utf-8"))
        self.assertIsNone(observation["archive"])
        self.assertIsNone(observation["corrections"]["archive_changed"])

    def test_review_correction_supersedes_label_without_rewriting_archive(self):
        """Supersede an earlier decision while preserving existing archive text."""
        capture = curatormd.native_projection_record(
            str(self.root),
            "session-revision",
            "agent:end",
            {
                "result": {
                    "activity_class": "implementation",
                    "status": "success",
                    "changed_project": True,
                }
            },
            profile="test",
        )
        curatormd.curate(str(self.root), profile="test")
        curatormd.review_candidate(
            self.root, capture["record_id"], "approved", 2, "history", profile="test"
        )
        history_before = (self.root / "persistence" / "HISTORY.md").read_text(encoding="utf-8")
        revised = curatormd.review_candidate(
            self.root, capture["record_id"], "do-not-record", 1, profile="test"
        )
        self.assertEqual(revised["review_revision"], 2)
        self.assertEqual(
            (self.root / "persistence" / "HISTORY.md").read_text(encoding="utf-8"), history_before
        )
        observations = sorted(
            (curatormd._plugin_data_root(self.root, "test") / "learning" / "observations").glob(
                "*.json"
            )
        )
        first, second = [json.loads(path.read_text(encoding="utf-8")) for path in observations]
        self.assertFalse(first["active"])
        self.assertEqual(first["superseded_by_observation_id"], second["observation_id"])
        self.assertTrue(second["active"])
        self.assertEqual(second["disposition"], "do-not-record")
        self.assertEqual(
            curation_learning._active_rows(
                self.root, "test", curation_learning.datetime.now(curation_learning.timezone.utc)
            )[0]["observation_id"],
            second["observation_id"],
        )

    def test_pending_inbox_records_do_not_expire(self):
        """Retain pending inbox records regardless of their age."""
        capture = curatormd.native_projection_record(
            str(self.root), "session-c", "agent:end", {"note": "pending"}, profile="test"
        )
        path = self.root / ".curatormd" / "native-inbox" / f"{capture['record_id']}.json"
        old = 1_600_000_000
        os.utime(path, (old, old))
        self.assertEqual(curatormd._cleanup_inbox(self.root), 0)
        self.assertTrue(path.exists())

    def test_curator_generated_edits_are_idempotent_and_appendable(self):
        """Append distinct generated entries while deduplicating exact repeats."""
        first = curatormd.append_entry(
            self.root, "history", "Stable", "Keep one copy.", profile="test"
        )
        duplicate = curatormd.append_entry(
            self.root, "history", "Stable", "Keep one copy.", profile="test"
        )
        second = curatormd.append_entry(
            self.root,
            "history",
            "Next",
            "Append after the curator's own uncommitted edit.",
            profile="test",
        )
        self.assertTrue(first["written"])
        self.assertTrue(duplicate["duplicate"])
        self.assertTrue(second["written"])
        history = (self.root / "persistence" / "HISTORY.md").read_text(encoding="utf-8")
        self.assertEqual(history.count("Keep one copy."), 1)
        self.assertIn("Append after the curator's own uncommitted edit.", history)

    def test_concurrent_identical_capture_and_repository_isolation(self):
        """Deduplicate concurrent captures independently in each repository."""
        payload = {"response": "A safe bounded result."}
        results: list[dict[str, Any]] = []
        threads = [
            threading.Thread(
                target=lambda: results.append(
                    curatormd.native_projection_record(
                        str(self.root), "same-event", "agent:end", payload, profile="shared"
                    )
                )
            )
            for _ in range(8)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sum(result["written"] for result in results), 1)
        self.assertEqual(sum(result["duplicate"] for result in results), 7)

        second_root = Path(self.temp_dir.name) / "second-project"
        second_root.mkdir()
        (second_root / "persistence").mkdir()
        for filename in ("AGENTS.md", "SOP.md", "HISTORY.md", "LESSONS-LEARNED.md"):
            (second_root / "persistence" / filename).write_text(f"# {filename}\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=second_root, check=True)
        subprocess.run(["git", "add", "."], cwd=second_root, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.email=test@example.invalid",
                "-c",
                "user.name=CuratorMD test",
                "commit",
                "-qm",
                "baseline",
            ],
            cwd=second_root,
            check=True,
        )
        curatormd.native_projection_record(
            str(second_root), "same-event", "agent:end", payload, profile="shared"
        )
        self.assertNotEqual(
            curatormd._state_path(self.root, "shared"), curatormd._state_path(second_root, "shared")
        )

    def test_models_return_finite_normalized_probabilities(self):
        """Keep trained model predictions finite and probability-normalized."""
        rows: list[dict[str, Any]] = []
        for i in range(48):
            rows.append(
                {
                    "features": {
                        "activity_class": "test" if i % 2 else "implementation",
                        "status": "failure" if i % 3 == 0 else "success",
                        "tests_failed": i % 4,
                    },
                    "approved_target": "approved" if i % 3 else "do-not-record",
                    "disposition": "approved" if i % 3 else "do-not-record",
                    "priority": i % 6,
                    "archive_target": ("agents", "sop", "history", "lessons")[i % 4],
                }
            )
        vocabulary = curation_learning._vocabulary([row["features"] for row in rows])
        vectors = [curation_learning._vector(row["features"], vocabulary) for row in rows]
        approval = curation_learning._fit_binary(rows, vectors, "approved_target")
        priority = curation_learning._fit_ordinal(rows, vectors)
        archive = curation_learning._fit_softmax(
            rows, vectors, "archive_target", list(curation_learning.ARCHIVES)
        )
        probe = vectors[0]
        probabilities = [
            curation_learning._predict_binary(approval, probe),
            *map(float, curation_learning._predict_ordinal(priority, probe).values()),
            *map(float, curation_learning._predict_softmax(archive, probe).values()),
        ]
        self.assertTrue(all(0.0 <= value <= 1.0 for value in probabilities))
        self.assertAlmostEqual(
            sum(curation_learning._predict_ordinal(priority, probe).values()), 1.0, places=8
        )
        self.assertAlmostEqual(
            sum(curation_learning._predict_softmax(archive, probe).values()), 1.0, places=8
        )
        self.assertEqual(approval["status"], "fit")
        self.assertEqual(priority["status"], "fit")
        self.assertEqual(archive["status"], "fit")

    def test_qa_and_retrospective_records_are_distinct_and_idempotent(self):
        """Store QA outcomes separately and deduplicate concurrent windows."""
        capture = curatormd.native_projection_record(
            str(self.root),
            "session-d",
            "agent:end",
            {
                "result": {
                    "activity_class": "debug",
                    "status": "failure",
                    "result_class": "failure",
                    "failure_class": "runtime",
                }
            },
            profile="test",
        )
        curatormd.curate(str(self.root), profile="test")
        curatormd.review_candidate(
            self.root, capture["record_id"], "approved", 3, "lessons", profile="test"
        )
        outcome = curatormd.qa_outcome_record(
            self.root,
            capture["record_id"],
            "repeat_failure",
            30,
            False,
            "No matching failure observed.",
            finalize_window=True,
            profile="test",
        )
        duplicate = curatormd.qa_outcome_record(
            self.root,
            capture["record_id"],
            "repeat_failure",
            30,
            False,
            "No matching failure observed.",
            finalize_window=True,
            profile="test",
        )
        self.assertTrue(outcome["written"])
        self.assertTrue(duplicate["duplicate"])
        windows = (60, 90, 180)

        def record_outcome(window: int) -> None:
            curatormd.qa_outcome_record(
                self.root,
                capture["record_id"],
                "repeat_failure",
                window,
                False,
                "No matching failure observed.",
                finalize_window=True,
                profile="test",
            )

        concurrent = [threading.Thread(target=record_outcome, args=(window,)) for window in windows]
        for thread in concurrent:
            thread.start()
        for thread in concurrent:
            thread.join()
        observation_path = next(
            (curatormd._plugin_data_root(self.root, "test") / "learning" / "observations").glob(
                "*.json"
            )
        )
        observation = json.loads(observation_path.read_text(encoding="utf-8"))
        self.assertEqual(observation["qa_finalized_windows"], [30, 60, 90, 180])
        self.assertTrue(observation["qa_windows_finalized"])
        self.assertTrue(
            curatormd.retrospective_review(
                self.root, capture["record_id"], "yes", 2, "yes", profile="test"
            )["written"]
        )
        report = curatormd.learning_recompute(self.root, "test", force=True)
        self.assertFalse(report["automation_enabled"])
        qa = curatormd.learning_report(self.root, "test")["qa"]
        self.assertEqual(qa["retrospective_review_count"], 1)

    def test_unreviewed_projection_is_ambiguous_and_not_promoted(self):
        """Keep incomplete projection payloads out of pending review."""
        curatormd.native_projection_record(
            str(self.root), "test-source", "agent:end", {"note": "candidate"}, profile="test"
        )
        result = curatormd.curate(str(self.root), profile="test")
        self.assertEqual(len(result["ambiguous"]), 1)
        self.assertEqual(
            (self.root / "persistence" / "HISTORY.md").read_text(encoding="utf-8"), "# HISTORY.md\n"
        )

    def test_reviewed_candidate_is_promoted(self):
        """Promote a complete candidate only after explicit human approval."""
        curatormd.native_projection_record(
            str(self.root), "test-source", "agent:end", {"note": "candidate"}, profile="test"
        )
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
        result = curatormd.curate(str(self.root), profile="test")
        self.assertEqual(len(result["written"]), 1)
        self.assertIn(
            "Reviewed test decision",
            (self.root / "persistence" / "HISTORY.md").read_text(encoding="utf-8"),
        )

    def test_uncommitted_knowledge_file_is_a_conflict(self):
        """Refuse to overwrite a canonical file with uncommitted changes."""
        curatormd.native_projection_record(
            str(self.root), "test-source", "agent:end", {"note": "candidate"}, profile="test"
        )
        path = next((self.root / ".curatormd" / "native-inbox").glob("*.json"))
        record = json.loads(path.read_text(encoding="utf-8"))
        record["reviewed"] = True
        record["candidate"] = {"kind": "history", "title": "Blocked", "content": "Must not append."}
        path.write_text(json.dumps(record), encoding="utf-8")
        history = self.root / "persistence" / "HISTORY.md"
        history.write_text(history.read_text(encoding="utf-8") + "\nlocal edit\n", encoding="utf-8")
        result = curatormd.curate(str(self.root), profile="test")
        self.assertEqual(len(result["conflicts"]), 1)
        self.assertNotIn("Blocked", history.read_text(encoding="utf-8"))

    def test_human_review_snapshots_existing_dirty_archive_and_preserves_it(self):
        """Append reviewed entries without discarding pre-existing archive edits."""
        capture = curatormd.native_projection_record(
            str(self.root),
            "sde-dirty-base",
            "agent:end",
            {"response": "Implemented a durable review recovery feature."},
            profile="test",
        )
        curatormd.curate(str(self.root), profile="test")
        history = self.root / "persistence" / "HISTORY.md"
        history.write_text(
            history.read_text(encoding="utf-8") + "\nUser's pending edit.\n", encoding="utf-8"
        )

        result = curatormd.review_candidate(
            self.root, capture["record_id"], "approved", 2, "history", profile="test"
        )

        updated = history.read_text(encoding="utf-8")
        self.assertTrue(result["reviewed"])
        self.assertIn("User's pending edit.", updated)
        self.assertIn("Implemented a durable review recovery feature.", updated)

    def test_changed_target_blocks_recovery_and_correction_supersedes_prepared_transaction(self):
        """Block stale transaction recovery and allow a corrected review decision."""
        capture = curatormd.native_projection_record(
            str(self.root),
            "sde-recovery-correction",
            "agent:end",
            {"response": "Implemented a durable review recovery feature."},
            profile="test",
        )
        curatormd.curate(str(self.root), profile="test")
        history = self.root / "persistence" / "HISTORY.md"
        history.write_text(
            history.read_text(encoding="utf-8") + "\nExisting approved edit.\n", encoding="utf-8"
        )
        with patch.object(
            curatormd,
            "_append_reviewed",
            side_effect=curatormd.CuratorError("simulated interruption"),
        ):
            with self.assertRaisesRegex(curatormd.CuratorError, "simulated interruption"):
                curatormd.review_candidate(
                    self.root, capture["record_id"], "approved", 2, "history", profile="test"
                )

        transaction_dir = (
            curatormd._plugin_data_root(self.root, "test") / "learning" / "transactions"
        )
        transaction_path = transaction_dir / f"{capture['record_id']}-r1.json"
        transaction = json.loads(transaction_path.read_text(encoding="utf-8"))
        self.assertEqual(transaction["status"], "prepared")
        history.write_text(
            history.read_text(encoding="utf-8") + "\nConcurrent edit after approval.\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(curatormd.CuratorError, "unresolved or uncommitted edits"):
            curatormd.recover_transaction(self.root, capture["record_id"], profile="test")

        rejected = curatormd.review_candidate(
            self.root, capture["record_id"], "do-not-record", 2, profile="test"
        )
        self.assertEqual(rejected["disposition"], "do-not-record")
        self.assertEqual(rejected["review_revision"], 2)
        self.assertEqual(
            json.loads(transaction_path.read_text(encoding="utf-8"))["status"], "superseded"
        )
        self.assertNotIn(
            "Implemented a durable review recovery feature.", history.read_text(encoding="utf-8")
        )

    def test_defined_sde_parser_preserves_meaning_and_scrubs_secrets(self):
        """Preserve a complete SDE synthesis while removing credential material."""
        result = curatormd.parse_defined_sde(
            self.root,
            {
                "title": "Recover approved SDE transactions",
                "beginning": "An approved review was stranded after HISTORY.md was already edited.",
                "middle": (
                    "Capture a target hash when approval is prepared; add automatic retry "
                    "and a manual recovery command."
                ),
                "end": (
                    "A changed target remains blocked; an explicit rejection supersedes "
                    "the prepared approval."
                ),
                "rationale": "api_key=super-secret-value",
                "archive": "history",
            },
            profile="test",
        )
        self.assertTrue(result["written"])
        self.assertIn("**Beginning — trigger and context:** An approved review", result["content"])
        self.assertIn("**Middle — decisions and work:** Capture a target hash", result["content"])
        self.assertIn("**End — outcome and verification:** A changed target", result["content"])
        self.assertNotIn("super-secret-value", result["content"])
        self.assertIn("[REDACTED]", result["content"])
        curatormd.curate(self.root, profile="test")
        review = curatormd.pending_reviews(self.root, "test")
        self.assertEqual(review["pending_count"], 1)
        pending = review["records"][0]
        self.assertEqual(pending["candidate"]["kind"], "history")
        self.assertIn("Beginning — trigger and context", pending["candidate"]["content"])
        self.assertIn("Middle — decisions and work", pending["candidate"]["content"])
        self.assertIn("End — outcome and verification", pending["candidate"]["content"])

    def test_defined_sde_parser_requires_all_chronology_parts(self):
        """Require beginning, middle, and end sections in parsed SDE records."""
        with self.assertRaisesRegex(ValueError, "sde.middle must be a non-empty string"):
            curatormd.parse_defined_sde(
                self.root,
                {
                    "title": "Incomplete event summary",
                    "beginning": "The event began.",
                    "end": "The event ended.",
                },
                profile="test",
            )

    def test_vocabulary_only_sde_capture_never_becomes_proposal_text(self):
        """Keep vocabulary-only captures from becoming review proposal prose."""
        curatormd.native_projection_record(
            str(self.root),
            "sde-cues-only",
            "codex:sde:thread",
            {
                "candidate_type": "significant_development_event",
                "sde_id": "SDE-0123456789AB",
                "before": {"change": ["remove"]},
                "after": {"change": ["implemented"]},
                "review_safe_summary": {"text": None, "status": "unavailable"},
            },
            profile="test",
        )
        result = curatormd.curate(self.root, profile="test")
        self.assertEqual(result["written"], [])
        self.assertEqual(len(result["suppressed"]), 1)
        self.assertFalse(curatormd.pending_reviews(self.root, "test")["records"])


if __name__ == "__main__":
    unittest.main()
