# Task Board

`tasks.json` is the machine-readable source of truth. Do not hand-edit task status while an agent is active; use `scripts/taskctl.py` so validation, history and timestamps are preserved.

## States

- `BACKLOG`: defined but not available.
- `READY`: dependencies are satisfied and an agent may claim it.
- `IN_PROGRESS`: owned by one agent.
- `REVIEW`: implementation finished; another reviewer must verify it.
- `DONE`: accepted by a different reviewer or human.
- `BLOCKED`: cannot proceed; history note must explain why.

## Examples

```text
python scripts/taskctl.py list
python scripts/taskctl.py next
python scripts/taskctl.py claim T002 --owner claude
python scripts/taskctl.py status T002 REVIEW --actor claude --note "Profile and probe attached"
python scripts/taskctl.py status T002 DONE --actor human --note "Verified on admin laptop"
```

