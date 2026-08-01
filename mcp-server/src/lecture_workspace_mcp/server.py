from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_workspace.dashboard import render_dashboard
from agent_workspace.task_store import TaskError, TaskStore


mcp = FastMCP(
    "AI Lecture Workspace",
    instructions=(
        "Use tasks/tasks.json as the task source of truth. Claim one READY task before writes. "
        "Implementers move tasks to REVIEW, never DONE. Do not publish, delete source media, "
        "change credentials, or perform destructive migrations without human approval."
    ),
)

ALLOWED_ROOT_DOCUMENTS = {
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "PROJECT_RULES.md",
}
ALLOWED_DOCUMENT_DIRS = {"docs", "handoffs", "tasks"}


def _refresh_dashboard(store: TaskStore) -> None:
    render_dashboard(store.load(), ROOT / "dashboard" / "index.html")


@mcp.tool()
def workspace_health() -> dict[str, Any]:
    """Return safe health information for the shared agent workspace."""
    store = TaskStore()
    summary = store.summary()
    return {
        "ok": True,
        "project_root": str(ROOT),
        "task_file": str(store.path.relative_to(ROOT)),
        "task_summary": summary,
        "mcp_scope": "task state, decisions, and approved project-document reads",
    }


@mcp.tool()
def get_project_status() -> dict[str, Any]:
    """Return task counts, next READY task, and the current project status document."""
    status_text = (ROOT / "docs" / "STATUS.md").read_text(encoding="utf-8")
    return {"tasks": TaskStore().summary(), "status_document": status_text}


@mcp.tool()
def get_next_task() -> dict[str, Any]:
    """Return the highest-priority READY task whose dependencies are DONE."""
    task = TaskStore().next_ready()
    return {"available": task is not None, "task": task}


@mcp.tool()
def claim_task(task_id: str, owner: str, note: str = "Task claimed through MCP") -> dict[str, Any]:
    """Claim one READY task for one owner and record the transition."""
    store = TaskStore()
    try:
        task = store.claim(task_id, owner, note)
        _refresh_dashboard(store)
        return {"ok": True, "task": task}
    except TaskError as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def update_task_status(
    task_id: str,
    new_status: str,
    actor: str,
    note: str,
    verification: str = "",
) -> dict[str, Any]:
    """Apply a validated task-state transition and append auditable history."""
    store = TaskStore()
    try:
        task = store.set_status(
            task_id,
            new_status,
            actor,
            note,
            verification or None,
        )
        _refresh_dashboard(store)
        return {"ok": True, "task": task}
    except TaskError as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def read_project_document(relative_path: str) -> dict[str, Any]:
    """Read an approved project markdown or JSON document without arbitrary filesystem access."""
    candidate = Path(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        return {"ok": False, "error": "Only safe project-relative paths are allowed"}
    allowed = candidate.as_posix() in ALLOWED_ROOT_DOCUMENTS or (
        candidate.parts and candidate.parts[0] in ALLOWED_DOCUMENT_DIRS
    )
    if not allowed or candidate.suffix.lower() not in {".md", ".json"}:
        return {"ok": False, "error": "Document path is outside the approved read scope"}
    resolved = (ROOT / candidate).resolve()
    if not resolved.is_relative_to(ROOT) or not resolved.is_file():
        return {"ok": False, "error": "Document not found"}
    return {"ok": True, "path": candidate.as_posix(), "content": resolved.read_text(encoding="utf-8")}


@mcp.tool()
def record_decision(title: str, decision: str, rationale: str, actor: str) -> dict[str, Any]:
    """Append a numbered architecture decision; never rewrites existing decisions."""
    values = [title.strip(), decision.strip(), rationale.strip(), actor.strip()]
    if not all(values):
        return {"ok": False, "error": "title, decision, rationale, and actor are required"}
    log_path = ROOT / "docs" / "DECISIONS.md"
    existing = log_path.read_text(encoding="utf-8")
    numbers = [int(match) for match in re.findall(r"^## D(\d+)", existing, flags=re.MULTILINE)]
    next_number = max(numbers, default=0) + 1
    safe_actor = actor.strip().replace("\n", " ")
    safe_title = title.strip().replace("\n", " ")
    entry = (
        f"\n## D{next_number:03d} — {safe_title}\n\n"
        f"- **Status:** Proposed\n"
        f"- **Recorded:** {date.today().isoformat()} by {safe_actor}\n"
        f"- **Decision:** {decision.strip()}\n"
        f"- **Reason:** {rationale.strip()}\n"
    )
    with log_path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(entry)
    return {"ok": True, "decision_id": f"D{next_number:03d}", "status": "Proposed"}


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
