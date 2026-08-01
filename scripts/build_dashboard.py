#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_workspace.dashboard import render_dashboard
from agent_workspace.task_store import TaskStore


if __name__ == "__main__":
    output = ROOT / "dashboard" / "index.html"
    render_dashboard(TaskStore().load(), output)
    print(output)

