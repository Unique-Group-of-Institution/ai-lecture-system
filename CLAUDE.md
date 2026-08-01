# Claude Code Project Instructions

Treat `PROJECT_RULES.md` as the authoritative shared policy. Before editing, also read `docs/STATUS.md`, `docs/DECISIONS.md`, `docs/PHASE_1_SCOPE.md`, and `tasks/tasks.json`.

## Required workflow

1. Run `python scripts/taskctl.py next`.
2. Claim one READY task using `python scripts/taskctl.py claim <ID> --owner claude`.
3. Implement only its documented scope.
4. Run `python scripts/check_workspace.py` plus task-specific tests.
5. Move the task to REVIEW, not DONE.
6. Update `docs/STATUS.md` and `handoffs/LATEST.md`.

Never perform a database-destructive action, delete source media, publish to LMS/YouTube, change credentials, or add a paid dependency without explicit human approval.

Do not assume another agent's chat history is available. Repository files and task history are the source of truth.

