from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent_workspace.task_store import TaskError, TaskStore


def fixture() -> dict:
    return {
        "schema_version": 1,
        "project": "Test",
        "updated_at": "2026-01-01T00:00:00Z",
        "tasks": [
            {
                "id": "T1",
                "title": "First",
                "priority": 1,
                "status": "READY",
                "owner": None,
                "dependencies": [],
                "history": [],
                "verification": [],
            },
            {
                "id": "T2",
                "title": "Second",
                "priority": 2,
                "status": "BACKLOG",
                "owner": None,
                "dependencies": ["T1"],
                "history": [],
                "verification": [],
            },
        ],
    }


class TaskStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "tasks.json"
        self.path.write_text(json.dumps(fixture()), encoding="utf-8")
        self.store = TaskStore(self.path)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_next_ready_returns_highest_priority_claimable_task(self) -> None:
        self.assertEqual(self.store.next_ready()["id"], "T1")

    def test_claim_records_owner_status_and_history(self) -> None:
        task = self.store.claim("T1", "claude")
        self.assertEqual(task["owner"], "claude")
        self.assertEqual(task["status"], "IN_PROGRESS")
        self.assertEqual(task["history"][-1]["to"], "IN_PROGRESS")

    def test_owner_cannot_mark_own_task_done(self) -> None:
        self.store.claim("T1", "claude")
        self.store.set_status("T1", "REVIEW", "claude", "Ready for review")
        with self.assertRaisesRegex(TaskError, "cannot mark its own task DONE"):
            self.store.set_status("T1", "DONE", "claude", "Self-approved")

    def test_different_reviewer_can_complete_task(self) -> None:
        self.store.claim("T1", "claude")
        self.store.set_status("T1", "REVIEW", "claude", "Ready for review")
        task = self.store.set_status(
            "T1", "DONE", "codex-reviewer", "Acceptance criteria verified", "tests passed"
        )
        self.assertEqual(task["status"], "DONE")
        self.assertEqual(task["verification"][-1]["evidence"], "tests passed")

    def test_dependency_blocks_ready_transition(self) -> None:
        with self.assertRaisesRegex(TaskError, "incomplete dependencies"):
            self.store.set_status("T2", "READY", "human", "Start second task")

    def test_duplicate_task_ids_are_rejected(self) -> None:
        payload = fixture()
        payload["tasks"].append(dict(payload["tasks"][0]))
        self.path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(TaskError, "Duplicate task id"):
            self.store.load()


if __name__ == "__main__":
    unittest.main()

