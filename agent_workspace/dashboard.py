from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any


STATUS_COLORS = {
    "BACKLOG": "#dfe5ef",
    "READY": "#dce9ff",
    "IN_PROGRESS": "#fff0a8",
    "REVIEW": "#e7ddff",
    "DONE": "#d9f5e5",
    "BLOCKED": "#ffdcdc",
}


def render_dashboard(payload: dict[str, Any], output: Path) -> None:
    counts = {status: 0 for status in STATUS_COLORS}
    for task in payload["tasks"]:
        counts[task["status"]] += 1

    count_blocks = "".join(
        f'<div class="metric"><span>{escape(status.replace("_", " ").title())}</span>'
        f'<strong>{counts[status]}</strong></div>'
        for status in STATUS_COLORS
    )

    rows = []
    for task in sorted(payload["tasks"], key=lambda item: (item["priority"], item["id"])):
        acceptance = "<br>".join(f"• {escape(item)}" for item in task.get("acceptance_criteria", []))
        deps = ", ".join(task["dependencies"]) or "—"
        owner = escape(task["owner"] or "Unassigned")
        color = STATUS_COLORS[task["status"]]
        rows.append(
            "<tr>"
            f"<td><strong>{escape(task['id'])}</strong></td>"
            f"<td><strong>{escape(task['title'])}</strong><small>{acceptance}</small></td>"
            f"<td><span class=\"status\" style=\"background:{color}\">{escape(task['status'])}</span></td>"
            f"<td>{owner}</td><td>{escape(deps)}</td>"
            "</tr>"
        )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Lecture System — Agent Dashboard</title>
  <style>
    :root {{ --navy:#202f78; --blue:#3157a4; --yellow:#ffcb21; --ink:#14213d; --muted:#65718a; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:#f1f5fc; color:var(--ink); font-family:Segoe UI,Arial,sans-serif; }}
    header {{ background:var(--navy); border-top:8px solid var(--yellow); color:white; padding:28px max(24px,calc((100vw - 1400px)/2)); }}
    header small {{ color:var(--yellow); font-weight:700; letter-spacing:.08em; }}
    h1 {{ margin:7px 0 5px; font-size:32px; }}
    header p {{ margin:0; color:#dce7ff; }}
    main {{ max-width:1400px; margin:24px auto; padding:0 24px 40px; }}
    .metrics {{ display:grid; grid-template-columns:repeat(6,1fr); gap:12px; margin-bottom:20px; }}
    .metric {{ background:white; border-radius:13px; padding:15px; box-shadow:0 6px 18px rgba(32,47,120,.08); }}
    .metric span {{ display:block; color:var(--muted); font-size:13px; }}
    .metric strong {{ display:block; color:var(--navy); font-size:28px; margin-top:5px; }}
    .panel {{ background:white; border-radius:15px; box-shadow:0 8px 25px rgba(32,47,120,.08); overflow:hidden; }}
    .panel-head {{ display:flex; align-items:center; justify-content:space-between; padding:18px 20px; border-bottom:1px solid #e3e9f4; }}
    .panel-head h2 {{ margin:0; color:var(--navy); }}
    .links a {{ color:var(--blue); margin-left:15px; font-weight:650; text-decoration:none; }}
    table {{ width:100%; border-collapse:collapse; }}
    th,td {{ text-align:left; padding:14px 16px; vertical-align:top; border-bottom:1px solid #e8edf6; }}
    th {{ color:var(--muted); font-size:12px; letter-spacing:.06em; text-transform:uppercase; }}
    td small {{ display:block; color:var(--muted); margin-top:7px; line-height:1.45; }}
    .status {{ display:inline-block; border-radius:999px; padding:6px 9px; font-size:12px; font-weight:750; white-space:nowrap; }}
    footer {{ max-width:1400px; margin:auto; padding:0 24px 35px; color:var(--muted); font-size:13px; }}
    @media(max-width:900px) {{ .metrics {{ grid-template-columns:repeat(2,1fr); }} .panel {{ overflow:auto; }} table {{ min-width:850px; }} }}
  </style>
</head>
<body>
  <header><small>UNIQUE GROUP OF INSTITUTIONS · PHASE 1</small><h1>AI Lecture System — Agent Dashboard</h1><p>One shared task board for the product owner, Claude Code and ChatGPT/Codex.</p></header>
  <main>
    <section class="metrics">{count_blocks}</section>
    <section class="panel">
      <div class="panel-head"><h2>Task Board</h2><div class="links"><a href="../docs/STATUS.md">Status</a><a href="../docs/DECISIONS.md">Decisions</a><a href="../docs/SYSTEM_PROFILE.md">System Profile</a></div></div>
      <table><thead><tr><th>ID</th><th>Task and acceptance</th><th>Status</th><th>Owner</th><th>Dependencies</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
    </section>
  </main>
  <footer>Generated from tasks/tasks.json at {escape(payload['updated_at'])}. Run <strong>python scripts/build_dashboard.py</strong> after manual task-data changes.</footer>
</body></html>"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8", newline="\n")

