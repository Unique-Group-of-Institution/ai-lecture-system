# Project Status

**Updated:** 2026-08-21

**Phase:** Phase-1 application foundation

**Overall status:** T050 local Remotion video assembly, review and export implementation is complete and in REVIEW on its dedicated task branch

## Completed

- Phase-1 business workflow clarified.
- Pilot Physics lecture and branded deck created.
- Aamir Sir audio technical-QC demonstration created.
- Audio correction policy clarified.
- Shared-agent operating model frozen.
- Agent instructions, task state machine and offline dashboard created.
- Restricted project MCP server skeleton created.
- Windows setup, CI and seven unit tests added.
- T001 approved and moved to DONE.
- Admin-PC profile captured for Windows build 19045, i5-6500, 8 GB RAM and approximately 68.3 GiB free workspace storage.
- Phase-1 publication boundary frozen: LMS integration is deferred; Phase 1 ends at admin-approved YouTube publication through the existing local uploader.
- Private institutional repository created at `https://github.com/Unique-Group-of-Institution/ai-lecture-system` and reviewed bootstrap pushed to `main`.
- Existing CI confirmed to run on `pull_request` events and pushes to `main`.
- Version-controlled local Git safety rejects direct pushes to `main` while permitting task and feature branches.
- Windows hook setup is repeatable and active in the current clone.
- T003 was approved by the product owner through PR #1 and moved to DONE by a human.
- T010 was approved by the product owner through PR #2 and moved to DONE by a human.
- T020 was approved by the product owner through PR #3 and moved from REVIEW to DONE by a human.
- T021 was approved by the product owner through PR #4 and moved from REVIEW to DONE by a human.
- T022 was approved by the product owner through PR #5 after an independent APPROVE review and moved from REVIEW to DONE by a human.
- T030 was approved by the product owner through PR #6 after an APPROVE targeted re-review and moved from REVIEW to DONE by a human.
- T040 was approved by the product owner through PR #7 after an APPROVE targeted review and moved from REVIEW to DONE by a human.

## Latest completed task

- T040 is DONE under `codex` on `task/t040-teacher-recording-portal` after the targeted review returned APPROVE and the product owner authorized PR #7 finalization, push and merge and performed the exact human `REVIEW` to `DONE` transition. Reviewed implementation head `44ef36435096258da1d7f7bec284b24b12ba615d` passed CI in run `32363723243`. The synchronization-only finalization commit must receive fresh successful exact-head CI before PR #7 is merged normally. Video assembly and Remotion integration remain deferred to T050.

## Approved Phase-1 workflow

- Teacher selects class, subject and chapter, then opens authorized textbook/Unique notes locally.
- Teacher provides generation guidelines; the system drafts source-grounded slides and a per-slide narration script.
- Teacher approves slides/script before recording audio slide-by-slide.
- The system assembles a local draft video; admin performs AI-assisted editing; teacher reviews the video; admin gives final approval.
- The approved narration script supplies captions/transcript text. Full Whisper transcription is not required.
- The final package moves to a local YouTube-ready folder; upload requires separate explicit admin approval.
- Voice cloning is outside Phase 1 and separately gated by teacher consent, revocation, audit and institutional approval.

## T020 benchmark

- Input duration: 568.789 seconds; validated derivative: PCM signed 16-bit, 16 kHz, mono, 18,201,336 bytes.
- Conversion runtime: 1.523 seconds. Source size and modification timestamp remained unchanged.
- Transcription runtime: 1,616.126 seconds; real-time factor 2.8413; peak working set 670,408,704 bytes.
- Automatically detected language code: `hi` (the CLI JSON provided no probability). This is a model limitation for the Urdu/English recording, not an accuracy or correct-rendering claim; spoken-content validation remains pending local teacher inspection.
- Transcript-free technical QC: 29 ordered/valid segments; two long-transcript-gap flags; zero low-confidence, timestamp-discontinuity, unusually-low-volume or clipping flags. Transcript gaps are not reported as silence, and no background-noise category is claimed because the tracked algorithm does not implement one.
- All real media, transcript text, timestamps, logs, model weights and tools remain local and ignored. No external upload, paid API, semantic correction, cut or caption judgment occurred.
- Ten T020 synthetic unit tests cover path validation, privacy-safe errors, overwrite refusal, timestamp ordering, Urdu/English Unicode, QC flags, safe placement, WAV metrics and missing dependencies.
- Verification passed after review fixes: `python scripts/check_workspace.py`; all 19 tests under `tests/`; all 13 Django tests; `manage.py check`; migration consistency; Python compilation; task/dashboard validation; `python -m pip check`; and `git diff --check`.
- Implementation commit `835742a` was pushed on `task/t020-local-whisper-audio-qc` through the active hook. Draft PR #3 targets `main`: `https://github.com/Unique-Group-of-Institution/ai-lecture-system/pull/3`. `workspace-ci` passed in Actions run `31091173324`, job `92582267539`.
- Benchmark conclusion: preserve the local tools/evidence as optional future QC research, but stop diagnostics and full-audio reruns. The approved narration script replaces Whisper output as the primary caption/transcript source.

## Current task

- T050 is owned by `codex` and is in REVIEW. The complete local-first implementation and synthetic validation evidence are present on `task/t050-remotion-video-assembly`; independent review is required before any human may move it to DONE.

## Proposed backlog — not yet implemented

- T060: separately deferred consented voice-clone option.
- T070: separately gated local YouTube-ready handoff and upload.

## T010 verification

- Django 6.0.8 runs on the installed Python 3.14.5; the project dependency remains constrained to compatible 6.0 patch releases.
- Clean migrations applied to a disposable SQLite database.
- All 13 Django tests passed, including required/missing secret configuration, teacher/admin permissions, anonymous and unassigned-user rejection, relationship/constraint behavior and portability checks.
- All 9 existing repository tests passed through `python scripts/check_workspace.py`.
- `python manage.py check`, migration consistency, and `git diff --check` passed.
- Implementation commit `96937e3` was pushed on `task/t010-db-auth-foundation` through the active local hook.
- Draft PR #2 targets `main`: `https://github.com/Unique-Group-of-Institution/ai-lecture-system/pull/2`. Its latest `workspace-ci` validation passed (Actions run `31079810095`). The PR is cleanly mergeable and is being finalized after product-owner approval.
- Human review fixes remove the tracked `SECRET_KEY` fallback, require `AI_LECTURE_SECRET_KEY`, document a process-only Windows setup, and run Django validation in CI on Python 3.14.
- Editable installation now uses explicit setuptools package discovery and succeeds with the declared Python 3.12+ and Django 6.0 dependency metadata.
- The product owner approved PR #2 and moved T010 from REVIEW to DONE at `2026-08-06T07:14:38Z`.

## Blockers

- FFmpeg is not globally installed; a verified portable FFmpeg 9.0 build is available only in ignored T020 local storage. LibreOffice is not installed.
- The 8 GB RAM and low-memory legacy GPUs constrain render choices. T020 confirms local full-audio Whisper is too slow for the primary workflow.
- Urdu/Hindi automatic script selection is unreliable with the tested model; full Urdu transcription and further model testing are deferred.
- The current GitHub plan does not support server-side branch protection for this private repository. The paid upgrade is deferred; local hooks must be installed on every clone and are not equivalent to server-side enforcement.

## T021 implementation

- Rights-confirmed institutional and teacher-owned sources have enforced access scopes plus class, subject, course and chapter context.
- Immutable originals and versioned derived UTF-8 page text retain source-file, extraction, page, method, hash, confidence and review provenance.
- Validation permits only PDF/PNG/JPG/JPEG and checks safe names/paths, size, signatures, strict PDF parsing and Pillow decoding.
- Text PDFs use local pypdf. Scans/images use explicit local Tesseract `urd+eng`, orientation-aware segmentation and TSV confidence. No cloud OCR or external transfer exists.
- All binaries, models, real sources and derived content remain ignored. Only synthetic fixtures were used.
- Independent-review corrections add bounded/isolated PDF extraction and rendering, decompression-bomb and cumulative resource ceilings, mandatory teacher approval for every OCR page, database-enforced review provenance, read-only admin provenance, atomic staging/promotion with failure cleanup, a final original-integrity gate, and collision-retrying extraction-version allocation.
- The T021 extraction lock is complete for the three verified Windows content wheels; a full cross-platform application transitive lock is documented as deferred in docs/CONTENT_TOOLS.md.
- Review-correction verification passed with synthetic fixtures and a process-scoped key: workspace check and 19 non-Django tests; 46 Django tests; clean migrations; Django and migration-consistency checks; compilation; pip check; task/dashboard validation; content-library/tool ignore validation; and git diff --check.
- Second-review corrections incrementally bound OCR stdout/stderr, terminate and reap OCR on timeout/overflow/failure, validate bounded TSV without exposing content in errors, and move PDF upload inspection into a timeout/output-bounded spawn-safe worker with strictly validated responses.
- Regression coverage now includes oversized OCR streams, OCR timeout/nonzero/malformed output, malformed/excessive/non-finite PDF worker responses, malformed selections, cleanup parent/out-of-scope rejection and valid boundary inputs.
- SQLite extraction is explicitly single-worker/sequential for the Phase-1 pilot. At the T021 review point, concurrent multi-teacher production still required the then-unimplemented T030 PostgreSQL-portable queue foundation.
- Second-review verification passed using synthetic fixtures and a new process-scoped temp root beneath ignored `data/content-tools/tmp`: focused 41 T021 tests; 19 non-Django tests; 54 Django tests; clean migrations; Django system and migration checks; compilation; pip, workspace, task/dashboard, privacy/ignore and diff validation.
- The product owner approved PR #4 and moved T021 from REVIEW to DONE. The SQLite sequential/single-worker limitation is accepted for Phase 1; PostgreSQL plus a controlled queue remains mandatory before concurrent production. No real content was processed or committed.

## Current quality rule

Keep the repository private under `Unique-Group-of-Institution`. Changes must use task or feature branches, pull requests, and passing CI; never bypass the local hook.

## T050 implementation

- A deterministic local Remotion 4.0.514 composition now assembles immutable T022 slide/narration snapshots with exact selected T040 recording takes, bilingual Urdu/English layout, institutional branding, canonical captions and bounded transitions. Every draft is a new immutable render version; raw takes and prior render artifacts are never overwritten or deleted.
- The Django service snapshots and revalidates the exact current slide approval fingerprint, recording completion, ordered revision/take selection, narration hashes and recording file hashes. Changed or missing evidence fails closed and makes the affected render or export ineligible.
- Administrators can request drafts and apply only allowlisted branding, caption-layout and transition/hold edits. Spoken-content removal additionally requires exact canonical-transcript evidence, bounded timestamps and the assigned teacher's immutable approval before a derived render can be created.
- The assigned teacher reviews the exact current draft before an administrator can grant final approval. Export packaging requires both approvals and the exact T030 `DRAFT_VIDEO_READINESS` and `EXPORT_READINESS` job/result gates; the resulting versioned local package contains MP4, SRT captions, metadata, a package manifest and editable PPTX slides, but performs no upload or publication.
- Rendering authority remains server-side. HTTP cannot mint worker identity or execute rendering. The adapter uses a fixed local composition, codec and concurrency with `shell=False`, bounded output and timeout, exact argument schemas and project-contained ignored paths. It requires both an explicit local adapter switch and the evaluation-only acknowledgement; production use fails closed.
- Migration `0008` adds PostgreSQL-portable immutable input, edit, review, approval, render-version and export-package evidence. The responsive admin/teacher interface exposes eligible bundles, versions, previews, edits, approval ordering and pending/failed/stale/unsupported states.
- Official evaluation dependencies are pinned in the dedicated subproject: Remotion packages 4.0.514, React/React DOM 19.2.3, TypeScript 5.9.3 and matching React types. Lock validation found 300 registry.npmjs.org entries with integrity data and exact Remotion-family versions. Remotion-managed Chrome Headless Shell 149.0.7790.0 is local and ignored; no global, paid, cloud or upload dependency is used.
- Synthetic-only verification passed on 2026-08-20: 8 focused T050 tests, all 107 Django tests and all 19 repository tests; workspace validation; Django system and migration-drift checks; clean SQLite migration through `0008`; compilation; Python dependency, npm lock/version/TypeScript, task/dashboard, privacy/ignore and diff checks. A one-second local synthetic H.264 smoke render succeeded (178,903 bytes; SHA-256 `fca3789e3bd550444f8573fe4aabb7edb992864bbe7e9be91116e72f81878e1f`). Generated media, binaries, caches and `node_modules` remain ignored and untracked.

## T040 implementation

- The assigned course teacher can list recording workflows by class, subject, course and chapter, review the exact current approved slide revision and canonical narration, and explicitly open the recording stage. Administrators, unassigned teachers, anonymous users and cross-course requests cannot substitute this access.
- Browser audio is accepted only in bounded WebM/Opus, Ogg/Opus, MP4/M4A or WAV containers with a safe filename, matching media type/extension and container signature, declared size, measured streamed size and bounded teacher-supplied duration. Requests are CSRF protected and media responses are authenticated, course scoped, private and non-cacheable.
- Every accepted raw take has a unique generated project-local storage key, take number, immutable database record, SHA-256 digest, exact slide revision, canonical narration snapshot and teacher identity. Retakes create new files and audit events; selection changes never overwrite or delete earlier takes.
- Staged writes are promoted without overwriting an existing path. Interrupted streams and validation failures remove staging files; a database or automatic-selection failure after promotion rolls back the take and removes only that operation-owned promoted file. Accepted source recordings have no delete workflow.
- Completion locks and revalidates the workflow version, approval fingerprint, exact ordered current revision list and selected teacher-owned take for every slide. It creates an immutable completion bundle before the auditable teacher-only transition to `RECORDING_READY`. A later slide revision invalidates downstream readiness while preserving historical raw takes and audit records.
- Migration `0007` adds PostgreSQL-portable take, selection, selection-event, completion and completion-item records. Read-only admin inspection, local login/portal pages, responsive CSS, browser recording JavaScript and Windows operation/recovery guidance are included. No rendering, Remotion, export, CRM, voice cloning, external upload, paid API or YouTube implementation was added.
- Synthetic-only verification passed on 2026-08-20: 9 focused T040 tests, all 99 Django tests and all 19 repository tests; workspace validation; Django system and migration-consistency checks; a clean SQLite migration through `0007`; compilation; dependency, task/dashboard, privacy/ignore and diff checks. The complete Windows suites required an approved unsandboxed process because the managed filesystem sandbox denied Python-created temporary directories; no ACL was weakened and no inaccessible temp tree was deleted.
- Targeted review approved reviewed implementation head `44ef36435096258da1d7f7bec284b24b12ba615d`; CI run `32363723243` passed on that head. The product owner moved T040 from REVIEW to DONE as actor `human` and authorized the synchronization-only finalization, push and normal merge of PR #7, subject to fresh successful CI on the exact finalization commit.

## T022 implementation

- A provider-independent generation domain receives only an internal actor ID, permitted course/source IDs and explicit capabilities; the current Django adapter enforces T010 roles and T021 visibility. CRM/SSO integration remains deferred.
- `deterministic-extractive-v1` runs fully locally with no new dependency or network call. It deterministically selects bounded exact spans from fully reviewed synthetic source pages and fails closed on unsupported output.
- Immutable generation/source/page snapshots retain extraction version, source/page hashes and reviewed UTF-8 text. Every slide claim and narration statement stores an exact page-snapshot character range and hash.
- Ordered slide revisions are append-only. Only the requesting course teacher can revise or approve; edits invalidate the current approval, administrators cannot substitute approval, and captions are returned only from the current approved canonical narration snapshot.
- Migration `0005` adds PostgreSQL-portable generation, snapshot, slide, revision, claim, narration, reference and canonical-caption records with protected relationships, constraints and indexes. Minimal JSON APIs and read-only Django admin inspection are included; no production frontend, queue, recording, render, voice or upload work was added.
- Synthetic-only verification passed: 16 focused T022 tests, all 70 Django tests and all 19 non-Django tests; workspace validation; Django system and migration-consistency checks; clean disposable SQLite migration; scoped Python compilation; pip dependency check; task/dashboard validation; privacy/ignore scans; and diff checks. Windows sandbox-created inaccessible temp directories were left untouched; successful temp-dependent runs used unique ignored workspace-local roots without ACL changes.
- T022 is DONE after an independent APPROVE review and the product owner's exact human `REVIEW` to `DONE` transition. The deterministic extractive Phase-1 generator limitation is accepted; CRM integration and stronger AI-provider evaluation remain deferred.
- Implementation commit `0c96607` and reviewed evidence head `99be0fc` were pushed through the active local hook. PR #5 targets `main`: `https://github.com/Unique-Group-of-Institution/ai-lecture-system/pull/5`. Complete implementation CI passed on reviewed head `99be0fc` in Actions run `31470738204`, job `93713275733`; a fresh run is required on the approval/status finalization commit before merge.

## T030 implementation

- A provider-independent, prevalidated `WorkflowActorContext` carries teacher, administrator or system-worker type, opaque identity reference, internal actor mapping, permitted course IDs and explicit capabilities. The current Django adapter authenticates only teacher/administrator operations. Because Phase 1 has no trusted HTTP worker-authentication mechanism, HTTP claim/complete/fail and system-only transition operations fail closed; request JSON, headers and query parameters cannot mint worker identity, scope or capability. CRM sessions/tables remain deferred.
- `LectureWorkflow` implements the explicit source-ready through export-ready state graph. Current-state versions, allowlisted reason codes and unique transition idempotency keys reject stale, duplicate, backward and skipped transitions.
- Teacher slide/narration approval fingerprints every current T022 revision. A later teacher revision transaction invalidates the approval, clears downstream readiness/approval references, returns the workflow to draft and writes an immutable audit event.
- Assigned-teacher slide/narration and video approvals cannot be replaced by administrators. Teacher video approval is mandatory before final administrator approval; only final administrator approval plus a successful export-readiness job permits export-ready state.
- `WorkflowJob` is a database-backed, PostgreSQL-portable coordination queue with four exact bounded payload schemas and four strict completion-result schemas. Results bind the exact job, job type, workflow and version to a typed generation/recording/video/export reference. Job-driven transitions atomically revalidate that evidence, reject missing/malformed/mismatched results and caller substitutions, and persist the validated result reference. The queue retains payload hashes, idempotent completion, atomic claim, bounded leases/retries, privacy-safe failures, pending-only cancellation and immutable events; it stores no commands, credentials or filesystem paths and executes no processor.
- SQLite is explicitly sequential/single-worker and rejects claims if that setting is disabled. Concurrent production requires PostgreSQL plus controlled workers; the PostgreSQL path uses transactional row locking and `SKIP LOCKED` where supported.
- Migration `0006` adds workflows, immutable workflow audits, jobs and immutable job events with protected relationships, unique constraints, retry/attempt checks and portable indexes. Minimal scoped JSON APIs and read-only Django admin inspection cover workflow, transition and audit inspection. Administrative inspection/submission/cancellation remain available, while HTTP worker primitives are reserved and fail closed until a separately authorized trusted server-side adapter exists.
- T040 recording UI, T050 video processing, T060 voice cloning, T070 export/upload execution, CRM integration, paid services, Redis/Celery/cloud queues and stronger AI providers were not implemented.
- Synthetic-only HIGH-review correction verification passed: 20 focused T030 tests, all 90 Django tests and all 19 repository tests; workspace validation; Django system and migration-consistency checks; clean disposable SQLite migration; compilation; dependency, task/dashboard, privacy/ignore and diff checks. Regression coverage includes every job-driven transition's matching, missing, malformed, cross-job/type/workflow/version and substituted result cases; administrator worker-minting attempts; fail-closed HTTP system operations; prevalidated worker capability/course restrictions; and non-forgeable HTTP audit attribution. No real content, media, transcript, production database, upload, credential or private artifact was accessed.
- Review-correction implementation commit `de1142c` and reviewed evidence commit `47a246306d9c45c71b738a1fdaccbcb098d8261a` were pushed through the active hook on `task/t030-workflow-queue-approvals`. PR #6 targets `main`: `https://github.com/Unique-Group-of-Institution/ai-lecture-system/pull/6`. `workspace-ci` passed on the exact reviewed implementation head in Actions run `31576595399`, job `94050001606`. Finalization commit `bcab4403f6bab8cb2ac315e31967d2b79b9d10c6` passed fresh CI in run `31679941510`; PR #6 merged normally into `main` as `a5358fd17d9bfdb9e0d278c59c747d96c9d48e80`. T030 is DONE after the product owner's exact human `REVIEW` to `DONE` transition.
