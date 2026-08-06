# Project Status

**Updated:** 2026-08-06

**Phase:** Phase-1 application foundation

**Overall status:** T020 local Whisper/audio-QC benchmark ready for independent review

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

- T020 is in REVIEW under `codex` on `task/t020-local-whisper-audio-qc`. The authorized pilot remained local and immutable. Portable FFmpeg produced a validated PCM derivative, and `whisper.cpp` 1.9.2 with multilingual `small-q5_1` completed the CPU-only benchmark. Tracked orchestration, documentation and synthetic privacy/safety tests are ready for independent review.

## T020 benchmark

- Input duration: 568.789 seconds; validated derivative: PCM signed 16-bit, 16 kHz, mono, 18,201,336 bytes.
- Conversion runtime: 1.523 seconds. Source size and modification timestamp remained unchanged.
- Transcription runtime: 1,616.126 seconds; real-time factor 2.8413; peak working set 670,408,704 bytes.
- Detected language code: `hi` (the CLI JSON provided no probability); 29 segments with ordered, valid timestamps.
- Transcript-free technical QC: zero clipped samples; six long-silence flags, two long-transcript-gap flags and one possible-background-noise flag.
- All real media, transcript text, timestamps, logs, model weights and tools remain local and ignored. No external upload, paid API, semantic correction, cut or caption judgment occurred.
- Eight T020 synthetic unit tests cover path validation, overwrite refusal, timestamp ordering, Urdu/English Unicode, QC flags, safe placement, WAV metrics and missing dependencies.
- Verification passed: `python scripts/check_workspace.py`; all 17 tests under `tests/`; all 13 Django tests; `manage.py check`; migration consistency; Python compilation; task/dashboard validation; `python -m pip check`; and `git diff --check`.

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
- The 8 GB RAM and low-memory legacy GPUs constrain larger Whisper models and later render-setting choices; T020's `small-q5_1` CPU benchmark is complete.
- The local `small-q5_1` Whisper model has been benchmarked; larger models remain untested and are not required for T020.
- The current GitHub plan does not support server-side branch protection for this private repository. The paid upgrade is deferred; local hooks must be installed on every clone and are not equivalent to server-side enforcement.

## Current quality rule

Keep the repository private under `Unique-Group-of-Institution`. Changes must use task or feature branches, pull requests, and passing CI; never bypass the local hook.
