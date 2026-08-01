from __future__ import annotations

import json
import os
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ALLOWED_STATES = {"BACKLOG", "READY", "IN_PROGRESS", "REVIEW", "DONE", "BLOCKED"}
ALLOWED_TRANSITIONS = {
    "BACKLOG": {"READY", "BLOCKED"},
    "READY": {"IN_PROGRESS", "BACKLOG", "BLOCKED"},
    "IN_PROGRESS": {"REVIEW", "READY", "BLOCKED"},
    "REVIEW": {"DONE", "IN_PROGRESS", "BLOCKED"},
    "BLOCKED": {"BACKLOG", "READY"},
    "DONE": set(),
}


class TaskError(ValueError):
    """Raised when task data or a requested transition is invalid."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class TaskStore:
    def __init__(self, path: str | Path | None = None) -> None:
        root = Path(__file__).resolve().parents[1]
        self.path = Path(path) if path else root / "tasks" / "tasks.json"

    def load(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise TaskError(f"Task file not found: {self.path}") from exc
        except json.JSONDecodeError as exc:
            raise TaskError(f"Task file is not valid JSON: {exc}") from exc
        self.validate(payload)
        return payload

    def validate(self, payload: dict[str, Any]) -> None:
        if payload.get("schema_version") != 1:
            raise TaskError("Unsupported or missing task schema_version")
        tasks = payload.get("tasks")
        if not isinstance(tasks, list):
            raise TaskError("tasks must be a list")

        ids: set[str] = set()
        for task in tasks:
            required = {"id", "title", "priority", "status", "owner", "dependencies", "history"}
            missing = required.difference(task)
            if missing:
                raise TaskError(f"Task is missing fields: {sorted(missing)}")
            task_id = task["id"]
            if not isinstance(task_id, str) or not task_id:
                raise TaskError("Every task must have a non-empty string id")
            if task_id in ids:
                raise TaskError(f"Duplicate task id: {task_id}")
            ids.add(task_id)
            if task["status"] not in ALLOWED_STATES:
                raise TaskError(f"Invalid status for {task_id}: {task['status']}")
            if not isinstance(task["dependencies"], list):
                raise TaskError(f"dependencies must be a list for {task_id}")
            if not isinstance(task["history"], list):
                raise TaskError(f"history must be a list for {task_id}")

        for task in tasks:
            unknown = set(task["dependencies"]).difference(ids)
            if unknown:
                raise TaskError(f"Unknown dependencies for {task['id']}: {sorted(unknown)}")
            if task["id"] in task["dependencies"]:
                raise TaskError(f"Task cannot depend on itself: {task['id']}")

    def save(self, payload: dict[str, Any]) -> None:
        self.validate(payload)
        payload["updated_at"] = utc_now()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(payload, stream, indent=2, ensure_ascii=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, self.path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

    @staticmethod
    def _task_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {task["id"]: task for task in payload["tasks"]}

    def get(self, task_id: str) -> dict[str, Any]:
        payload = self.load()
        try:
            return deepcopy(self._task_map(payload)[task_id])
        except KeyError as exc:
            raise TaskError(f"Unknown task id: {task_id}") from exc

    def next_ready(self) -> dict[str, Any] | None:
        payload = self.load()
        by_id = self._task_map(payload)
        candidates = []
        for task in payload["tasks"]:
            if task["status"] != "READY" or task["owner"]:
                continue
            if all(by_id[dependency]["status"] == "DONE" for dependency in task["dependencies"]):
                candidates.append(task)
        if not candidates:
            return None
        return deepcopy(sorted(candidates, key=lambda item: (item["priority"], item["id"]))[0])

    def claim(self, task_id: str, owner: str, note: str = "Task claimed") -> dict[str, Any]:
        owner = owner.strip()
        if not owner:
            raise TaskError("owner cannot be empty")
        payload = self.load()
        by_id = self._task_map(payload)
        if task_id not in by_id:
            raise TaskError(f"Unknown task id: {task_id}")
        task = by_id[task_id]
        if task["status"] != "READY":
            raise TaskError(f"Only READY tasks can be claimed; {task_id} is {task['status']}")
        if task["owner"]:
            raise TaskError(f"Task {task_id} is already owned by {task['owner']}")
        incomplete = [dep for dep in task["dependencies"] if by_id[dep]["status"] != "DONE"]
        if incomplete:
            raise TaskError(f"Task {task_id} has incomplete dependencies: {incomplete}")
        active = [
            item["id"]
            for item in payload["tasks"]
            if str(item["owner"] or "").casefold() == owner.casefold()
            and item["status"] == "IN_PROGRESS"
        ]
        if active:
            raise TaskError(f"Owner {owner} already has an active task: {active[0]}")

        task["owner"] = owner
        self._transition(task, "IN_PROGRESS", owner, note)
        self.save(payload)
        return deepcopy(task)

    def set_status(
        self, task_id: str, new_status: str, actor: str, note: str, verification: str | None = None
    ) -> dict[str, Any]:
        new_status = new_status.upper().strip()
        actor = actor.strip()
        note = note.strip()
        if not actor or not note:
            raise TaskError("actor and note are required")

        payload = self.load()
        by_id = self._task_map(payload)
        if task_id not in by_id:
            raise TaskError(f"Unknown task id: {task_id}")
        task = by_id[task_id]
        if new_status not in ALLOWED_TRANSITIONS[task["status"]]:
            raise TaskError(f"Invalid transition: {task['status']} -> {new_status}")
        same_as_owner = actor.casefold() == str(task.get("owner") or "").casefold()
        if new_status == "DONE" and actor.casefold() != "human" and same_as_owner:
            raise TaskError("The implementing owner cannot mark its own task DONE")
        if new_status == "READY":
            incomplete = [dep for dep in task["dependencies"] if by_id[dep]["status"] != "DONE"]
            if incomplete:
                raise TaskError(f"Cannot make task READY; incomplete dependencies: {incomplete}")
            task["owner"] = None
        if verification:
            task.setdefault("verification", []).append(
                {"at": utc_now(), "actor": actor, "evidence": verification.strip()}
            )
        self._transition(task, new_status, actor, note)
        self.save(payload)
        return deepcopy(task)

    @staticmethod
    def _transition(task: dict[str, Any], new_status: str, actor: str, note: str) -> None:
        old_status = task["status"]
        task["status"] = new_status
        task["history"].append(
            {"at": utc_now(), "actor": actor, "from": old_status, "to": new_status, "note": note}
        )

    def summary(self) -> dict[str, Any]:
        payload = self.load()
        counts = {state: 0 for state in sorted(ALLOWED_STATES)}
        for task in payload["tasks"]:
            counts[task["status"]] += 1
        return {
            "project": payload["project"],
            "updated_at": payload["updated_at"],
            "counts": counts,
            "next_ready": self.next_ready(),
        }
