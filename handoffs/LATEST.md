# Latest Agent Handoff

- **Task:** T040 — Build teacher slide-by-slide recording portal
- **Owner:** codex
- **Status:** DONE — the targeted review returned APPROVE and the product owner performed the exact `REVIEW` to `DONE` transition as actor `human`
- **Branch:** `task/t040-teacher-recording-portal`
- **Scope delivered:** Teacher-scoped class/subject/chapter portal, current approved slide and canonical narration review, explicit recording open gate, bounded browser-audio uploads, immutable raw takes, audited retakes and selection, private media playback, and immutable teacher completion bundles
- **Integrity and failure behavior:** Every take binds its workflow, exact approved slide revision, canonical narration snapshot, teacher, sequence, duration, size and SHA-256 digest. Staging and operation-owned promoted files are cleaned if acceptance fails; committed takes are never overwritten or deleted. A later slide revision makes prior takes ineligible without removing history.
- **Authorization and privacy:** Only the exact assigned/requesting teacher with the existing provider-independent capability and course scope can operate T040. CSRF remains enabled. Audio stays in ignored local storage and is served only through authenticated, course-scoped, private/no-store responses. Tests use synthetic media only.
- **Verification:** 9 focused T040 tests, 99 complete Django tests and 19 repository tests passed. Workspace, Django system and migration-drift checks, clean SQLite migration through `0007`, Python compilation, dependency, task/dashboard, privacy/ignore and diff checks passed. Managed Windows sandbox temp ACL failures were resolved by running the same synthetic suites in an approved unsandboxed process; no ACL or source data was changed.
- **Documentation:** `docs/TEACHER_RECORDING_PORTAL.md` contains Windows setup, workflow, browser requirements, local storage, limits, safe failure, backup/recovery and verification instructions.
- **Deferred scope:** Remotion and all video assembly/rendering, admin edit/export, CRM, voice cloning, external uploads and YouTube remain out of T040 and unimplemented.
- **Approval evidence:** Reviewed implementation head `44ef36435096258da1d7f7bec284b24b12ba615d` received an APPROVE verdict and passed CI in run `32363723243`. The product owner authorized finalization, push and normal merge of draft PR #7.
- **Finalization scope:** Only `tasks/tasks.json`, generated `dashboard/index.html`, `docs/STATUS.md`, and `handoffs/LATEST.md` may be committed. No implementation file or full suite is to be changed or rerun.
- **Next action:** Validate the four synchronization files, commit and push them without bypassing hooks, mark PR #7 ready, require fresh successful CI on the exact finalization commit, verify all merge invariants, and merge normally. Keep `task/t040-teacher-recording-portal`; then fast-forward local `main` and leave T050 unmodified.
