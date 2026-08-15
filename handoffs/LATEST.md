# Latest Agent Handoff

- **Task:** T040 — Build teacher slide-by-slide recording portal
- **Owner:** codex
- **Status:** IN_PROGRESS — product owner authorized T040; exact human `BACKLOG` to `READY` and Codex `READY` to `IN_PROGRESS` transitions are recorded
- **Branch:** `task/t040-teacher-recording-portal`, created from merged `main` commit `a5358fd17d9bfdb9e0d278c59c747d96c9d48e80`
- **Dependencies:** T022 and T030 are DONE
- **Approved scope:** Class, subject and chapter selection; current slide and narration review; per-slide browser recording; slide-level retakes; and teacher recording completion
- **Recording integrity:** Approved slides and narration are required before recording. Every raw take remains immutable; a retake creates a new version and must not overwrite an earlier take.
- **Authorization:** Only the assigned course teacher may access and record the course workflow. Provider-independent actor context and existing T030 approval gates remain authoritative.
- **Privacy:** Teacher audio and institutional content remain local. Tests use synthetic media only. No external upload, paid API, credentials, real media or private artifact access is authorized.
- **Deferred scope:** Video assembly, Remotion rendering, admin edit/review/export, voice cloning and YouTube upload remain outside T040. Remotion remains planned for the separately scoped T050 proof of concept.
- **T030 baseline:** PR #6 merged into `main` as `a5358fd17d9bfdb9e0d278c59c747d96c9d48e80` after finalization commit `bcab4403f6bab8cb2ac315e31967d2b79b9d10c6` passed CI run `31679941510`. Trusted HTTP worker operations remain fail-closed; SQLite remains sequential/single-worker.
- **Next action:** Inspect the current Django frontend structure and T022/T030 service boundaries, define the smallest secure T040 implementation slice, add synthetic tests, and keep the task IN_PROGRESS until implementation is ready for REVIEW.
