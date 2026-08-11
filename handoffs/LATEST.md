# Latest Agent Handoff

- **Task:** T030 — Implement the Phase-1 workflow job queue and approval states
- **Owner:** codex
- **Status:** REVIEW — implementation and complete local validation passed; independent or human review is required
- **Branch:** `task/t030-workflow-queue-approvals`
- **Architecture:** Authentication-provider-independent `WorkflowActorContext` with explicit teacher, administrator and system-worker capabilities. Django roles are an adapter; CRM/SSO sessions and tables remain deferred.
- **State machine:** Explicit source/content-ready, slide/narration draft and teacher approval, recording pending/ready, draft-video pending/ready, teacher revision/approval, final administrator approval and export-ready states. Current-version checks, allowlisted reasons and idempotency keys reject stale, duplicate, backward or skipped transitions.
- **Approval gates:** Current T022 slide revisions are fingerprinted at teacher approval. A later revision atomically invalidates downstream state and audits the rollback. Administrators cannot replace teacher approvals; teachers cannot grant final administrator approval; teacher video approval precedes final admin approval; export-ready requires final admin approval and a successful matching job.
- **Queue:** Four exact bounded reference-only job types; no commands, arbitrary code, credentials or paths. Database transactions, PostgreSQL row locks/`SKIP LOCKED`, attempt limits, leases, expiry recovery, bounded retries, idempotent submission/completion, pending-only cancellation, privacy-safe failures and immutable events are implemented. Job completion never advances state automatically.
- **Concurrency:** SQLite is sequential/single-worker only and is not claimed safe for multi-worker production. PostgreSQL plus a controlled worker deployment is mandatory before concurrency.
- **Models/APIs:** Migration `0006` adds `LectureWorkflow`, `WorkflowAuditEvent`, `WorkflowJob` and `WorkflowJobEvent`. Minimal scoped workflow/transition/audit and queue submit/inspect/claim/complete/fail/cancel JSON APIs are present; Django admin paths are read-only.
- **Scope exclusions:** No recording UI, audio/video processing, voice clone, export generation, uploader action, CRM integration, paid dependency, Redis/Celery/cloud queue, stronger AI provider or real/private artifact access.
- **Verification:** Synthetic-only 18 focused T030 tests, 88 complete Django tests and 19 complete repository tests passed. Workspace, system, migration drift, clean disposable migration, compilation, dependency, task/dashboard, privacy/ignore and diff checks passed.
- **Publication:** Scoped commit, hook-protected push, draft PR into `main` and fresh CI confirmation are the remaining publication steps; do not approve, mark ready, merge or self-complete T030.
