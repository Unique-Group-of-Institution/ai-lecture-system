#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_workspace.dashboard import render_dashboard
from agent_workspace.task_store import TaskStore


REQUIRED_PATHS = [
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "PROJECT_RULES.md",
    ".mcp.json",
    ".codex/config.toml",
    "docs/ARCHITECTURE.md",
    "docs/DECISIONS.md",
    "docs/STATUS.md",
    "docs/SYSTEM_PROFILE.md",
    "tasks/tasks.json",
    "scripts/taskctl.py",
    "scripts/run_mcp.py",
    "mcp-server/src/lecture_workspace_mcp/server.py",
]


def main() -> int:
    failures: list[str] = []
    for relative in REQUIRED_PATHS:
        if not (ROOT / relative).is_file():
            failures.append(f"Missing required file: {relative}")

    try:
        payload = TaskStore().load()
        render_dashboard(payload, ROOT / "dashboard" / "index.html")
    except Exception as exc:  # validation must report the original cause
        failures.append(f"Task/dashboard validation failed: {exc}")

    try:
        mcp_payload = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
        if "ai-lecture-workspace" not in mcp_payload.get("mcpServers", {}):
            failures.append(".mcp.json does not define ai-lecture-workspace")
    except Exception as exc:
        failures.append(f"Invalid .mcp.json: {exc}")

    test_result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if test_result.returncode != 0:
        failures.append("Unit tests failed:\n" + test_result.stdout + test_result.stderr)

    if failures:
        print("WORKSPACE CHECK FAILED", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(test_result.stdout.strip())
    print("WORKSPACE CHECK PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

