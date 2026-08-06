# Project Status

**Updated:** 2026-08-06

**Phase:** Phase-1 application foundation

**Overall status:** Script-first Phase-1 workflow approved; T020 benchmark limitations ready for review

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

## Current task

- T020 remains in REVIEW under `codex` on `task/t020-local-whisper-audio-qc`. The local decoder/Whisper pipeline was benchmarked while the authorized source remained private and immutable. CPU processing is too slow for the primary workflow and automatic Urdu/Hindi script detection is unreliable. Full Urdu transcription and further model testing are explicitly deferred; no further teacher-audio processing is authorized for T020.

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

## Proposed backlog — not yet implemented

- T021: authorized chapter-content library and source-page extraction.
- T022: source-grounded slide and per-slide narration-script generation.
- T030: workflow/job queue and approval states.
- T040: teacher slide-by-slide recording portal.
- T050: admin video assembly, AI-assisted edit, teacher review and export.
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

## Current quality rule

Keep the repository private under `Unique-Group-of-Institution`. Changes must use task or feature branches, pull requests, and passing CI; never bypass the local hook.
