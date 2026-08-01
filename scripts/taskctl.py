#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_workspace.dashboard import render_dashboard
from agent_workspace.task_store import TaskError, TaskStore


def update_dashboard(store: TaskStore) -> None:
    render_dashboard(store.load(), ROOT / "dashboard" / "index.html")


def print_task(task: dict | None) -> None:
    if task is None:
        print("No claimable READY task.")
        return
    print(json.dumps(task, indent=2, ensure_ascii=False))


def list_tasks(store: TaskStore) -> None:
    payload = store.load()
    print(f"{'ID':<6} {'STATUS':<12} {'OWNER':<14} TITLE")
    print("-" * 82)
    for task in sorted(payload["tasks"], key=lambda item: (item["priority"], item["id"])):
        print(f"{task['id']:<6} {task['status']:<12} {(task['owner'] or '—'):<14} {task['title']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Control the shared AI Lecture System task board")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List all tasks")
    sub.add_parser("next", help="Show the next claimable READY task")
    sub.add_parser("validate", help="Validate tasks and regenerate dashboard")

    show = sub.add_parser("show", help="Show one task")
    show.add_argument("task_id")

    claim = sub.add_parser("claim", help="Claim a READY task")
    claim.add_argument("task_id")
    claim.add_argument("--owner", required=True)
    claim.add_argument("--note", default="Task claimed")

    status = sub.add_parser("status", help="Transition a task")
    status.add_argument("task_id")
    status.add_argument("new_status")
    status.add_argument("--actor", required=True)
    status.add_argument("--note", required=True)
    status.add_argument("--verification")

    args = parser.parse_args()
    store = TaskStore()
    try:
        if args.command == "list":
            list_tasks(store)
        elif args.command == "next":
            print_task(store.next_ready())
        elif args.command == "show":
            print_task(store.get(args.task_id))
        elif args.command == "claim":
            print_task(store.claim(args.task_id, args.owner, args.note))
            update_dashboard(store)
        elif args.command == "status":
            print_task(
                store.set_status(
                    args.task_id,
                    args.new_status,
                    args.actor,
                    args.note,
                    args.verification,
                )
            )
            update_dashboard(store)
        elif args.command == "validate":
            store.load()
            update_dashboard(store)
            print("Task data valid; dashboard regenerated.")
        return 0
    except TaskError as exc:
        print(f"Task error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

