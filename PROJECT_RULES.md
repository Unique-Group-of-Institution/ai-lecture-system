# Shared Project Rules

## 1. Authority

The human product owner approves scope, content, destructive operations, credentials, publication, and production deployment. Agents may implement, test, document, and prepare review artifacts within an approved task.

## 2. Source of truth

- Code and durable instructions: this Git repository.
- Task state: `tasks/tasks.json`.
- Architecture decisions: `docs/DECISIONS.md`.
- Current progress: `docs/STATUS.md`.
- Latest cross-agent handoff: `handoffs/LATEST.md`.

Chat history is supporting context, not the authoritative project record.

## 3. One writer, one reviewer

- Only one agent owns an IN_PROGRESS task.
- Agents must not edit overlapping files simultaneously.
- The implementing agent moves a task to REVIEW.
- A different agent or the human product owner moves it to DONE.

## 4. Phase-1 boundaries

- Local-first execution.
- No paid AI APIs.
- No voice cloning.
- Teacher records scene-wise audio after approving draft scenes/slides.
- Local Whisper produces a timestamped transcript.
- Sound cleanup may be automatic; semantic cuts require teacher approval.
- Admin approval is required before export or publication.

## 5. Safety gates

Explicit human approval is required before:

- destructive database migrations or data deletion;
- source-media deletion or overwrite;
- changing secrets or authentication configuration;
- external uploads or publication;
- production deployment;
- adding recurring-cost services;
- widening MCP tool permissions.

## 6. Quality gates

Every implementation task must include:

- clear acceptance criteria;
- automated verification where practical;
- no secrets in code or logs;
- Windows-compatible instructions;
- updated status and handoff notes;
- rollback or safe failure behavior for file-processing steps.

## 7. Data privacy

Teacher audio, syllabus files, transcripts, and student/institution data stay local unless the human explicitly approves a destination. Agents must use synthetic fixtures in tests.

## 8. Audio integrity

- Preserve raw audio as immutable input.
- Create derived versions with explicit version names.
- Do not invent captions or factual corrections.
- Store every destructive cut as a timestamped edit decision.
- Missing content requires a teacher patch or approved voice-clone workflow in a later phase.

