from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent_workspace.dashboard import render_dashboard


class DashboardTests(unittest.TestCase):
    def test_dashboard_escapes_task_content(self) -> None:
        payload = {
            "updated_at": "2026-01-01T00:00:00Z",
            "tasks": [
                {
                    "id": "T1",
                    "title": "<unsafe>",
                    "priority": 1,
                    "status": "READY",
                    "owner": None,
                    "dependencies": [],
                    "acceptance_criteria": ["No <script> tags"],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "index.html"
            render_dashboard(payload, output)
            html = output.read_text(encoding="utf-8")
            self.assertIn("&lt;unsafe&gt;", html)
            self.assertNotIn("<unsafe>", html)
            self.assertIn("&lt;script&gt;", html)


if __name__ == "__main__":
    unittest.main()

