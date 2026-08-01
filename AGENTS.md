# Codex Project Instructions

Before doing any work, read these files in order:

1. `PROJECT_RULES.md`
2. `docs/STATUS.md`
3. `docs/DECISIONS.md`
4. `docs/PHASE_1_SCOPE.md`
5. `tasks/tasks.json`

## Working contract

- Claim exactly one READY task before editing.
- Do not edit a task owned by another active agent.
- Work only inside the claimed task's scope.
- Keep the system local-first and zero paid-API-cost in Phase 1.
- Never delete source recordings or teacher content.
- Never remove spoken content without a transcript-backed edit decision and teacher approval.
- Ask before database-destructive changes, publishing, credentials, paid dependencies, or security-boundary changes.
- Run `python scripts/check_workspace.py` and relevant tests before moving a task to REVIEW.
- Update `docs/STATUS.md`, `handoffs/LATEST.md`, and the task record after material work.
- Do not mark your own implementation DONE. Move it to REVIEW; a reviewer or human approves DONE.

## Code review rules

- Flag changes that bypass teacher or admin approval gates.
- Flag any upload of private syllabus/audio to an external service.
- Flag hard-coded credentials, absolute user-specific paths, or paid API dependencies.
- Flag audio cuts that lack a timestamped correction record.
- Require tests for task-state changes, path validation, and render pipeline orchestration.

