# Latest Agent Handoff

- **Task:** T040 — Build teacher slide-by-slide recording portal
- **Owner:** codex
- **Status:** REVIEW — the implementing agent performed only the authorized `IN_PROGRESS` to `REVIEW` transition; an independent reviewer or the human product owner must decide `DONE`
- **Branch:** `task/t040-teacher-recording-portal`
- **Scope delivered:** Teacher-scoped class/subject/chapter portal, current approved slide and canonical narration review, explicit recording open gate, bounded browser-audio uploads, immutable raw takes, audited retakes and selection, private media playback, and immutable teacher completion bundles
- **Integrity and failure behavior:** Every take binds its workflow, exact approved slide revision, canonical narration snapshot, teacher, sequence, duration, size and SHA-256 digest. Staging and operation-owned promoted files are cleaned if acceptance fails; committed takes are never overwritten or deleted. A later slide revision makes prior takes ineligible without removing history.
- **Authorization and privacy:** Only the exact assigned/requesting teacher with the existing provider-independent capability and course scope can operate T040. CSRF remains enabled. Audio stays in ignored local storage and is served only through authenticated, course-scoped, private/no-store responses. Tests use synthetic media only.
- **Verification:** 9 focused T040 tests, 99 complete Django tests and 19 repository tests passed. Workspace, Django system and migration-drift checks, clean SQLite migration through `0007`, Python compilation, dependency, task/dashboard, privacy/ignore and diff checks passed. Managed Windows sandbox temp ACL failures were resolved by running the same synthetic suites in an approved unsandboxed process; no ACL or source data was changed.
- **Documentation:** `docs/TEACHER_RECORDING_PORTAL.md` contains Windows setup, workflow, browser requirements, local storage, limits, safe failure, backup/recovery and verification instructions.
- **Deferred scope:** Remotion and all video assembly/rendering, admin edit/export, CRM, voice cloning, external uploads and YouTube remain out of T040 and unimplemented.
- **Review focus:** Verify non-bypassable teacher/current-approval gates, cross-course media isolation, immutable history, exact completion evidence, filesystem/database failure cleanup, migration portability, and the absence of external endpoints or tracked media.
- **Next action:** Commit and push only the T040-authorized files, open one draft PR into `main`, and require fresh successful `workspace-ci` before review. Do not mark T040 `DONE`.
