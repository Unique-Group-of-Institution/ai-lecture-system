# Latest Agent Handoff

- **Task:** T080 — Wire lecture-division scoped PPT generation pipeline
- **Owner:** qoder
- **Status:** REVIEW — end-to-end verified with the real Class 9 Computer Science textbook on 2026-09-22; awaiting human REVIEW→DONE
- **Branch:** `simple-lms-workflow` (uncommitted; manual review, staging and commit required — the working tree also contains unrelated prior-session changes that must not be bundled)
- **Scope delivered:**
  - `LectureDivision` model (chapter + lecture number + textbook `page_start`/`page_end`, with ordered-range and uniqueness constraints) plus migration `0010`; `GenerationRequest` gained `lecture` FK and `pptx_storage_key`.
  - Management commands: `ingest_textbook`, `import_lecture_division` (JSON/CSV), `approve_ocr_pages`, `generate_lecture_ppt` (division → page-scoped generation → workflow → queued slide-engine job in one transaction; `--skip-engine` flag).
  - `lectures/generation.py`: page-scoped grounded generation; `create_generation` rejects out-of-scope / foreign-chapter / unscoped lectures.
  - `lectures/slide_engine.py`: lecture-aware canonical payload; runs the in-repo Node engine, validates the `.pptx`, persists `pptx_storage_key`.
  - `lectures/views.py`: `export_generation_pptx` serves/produces the persisted PPTX through the in-repo engine (owner-or-staff, safe JSON errors).
- **2026-09-22 real-content session (this handoff):**
  - Real 169-page CS9 textbook ingested as `ContentSource` 2 ("CS9 Textbook (Final Proof)", rights confirmed, READY); course `CS9-2026` (teacher `bilal.ali`) with 7 lecture divisions covering book pages 6-27 (physical PDF page = book page + 3).
  - Slide-quality fix in `DeterministicExtractiveGenerator`: units are now whole sentences (wrapped PDF lines merged, digit-only page-number lines skipped, sentence boundaries flushed with absolute page offsets). Grounding is unchanged — every claim remains an exact page-snapshot character range.
  - Schema-safety fix in `lectures/lecture_builder.py`: bullets enforce the Node schema minLength 2; slos/recap/reviewQuestions enforce minLength 5 with a recap fallback to slide leads; `lectures/slide_engine.py` recap picks the first ≥5-char claim.
  - Dev-database permission fix: the `Teacher` group now carries generation/review permissions (`add/change/view_generationrequest`, `add/change/view_slidedraft`, …) and `admin` is a superuser. Without `lectures.add_generationrequest` the actor context reports `can_generate=False` and Studio returns "Generation is unavailable."
  - Test fixes: `test_lecture_builder.py` passes the required `previous_knowledge` kwarg; `tests_legacy.py` strips `DATABASE_URL` from the clean-migration subprocess env so `AI_LECTURE_SQLITE_PATH` is honoured.
  - End-to-end: `generate_lecture_ppt --course-code CS9-2026 --lecture 1..7` produced generations 10-16; each created a workflow, a SUCCEEDED slide-engine job and a real deck at `data/slide-engine/generation-10..16/lecture.pptx`.
  - Endpoint verification (Django test client): as `bilal.ali` — `/`, `/studio/`, `/api/generations/10/`, `/api/workflows/`, `/studio/lecture/10/`, `/teacher/recordings/`, `/api/generations/10/export-pptx/` all 200; `/admin/video-assembly/` 403 by design (administrator-only). As `admin` — generation detail 403 by design (owner-only API), export-pptx 200 via staff/superuser allowance.
  - Full suite: `python manage.py test lectures` — 123 tests OK.
- **Expected non-errors (do not "fix"):**
  - Video assembly pages show "Unsupported environment / rendering disabled": T050 Remotion processing is intentionally gated to the trusted local evaluation mode (`AI_LECTURE_VIDEO_RENDER_ADAPTER`, `AI_LECTURE_REMOTION_EVALUATION_ACK`, `AI_LECTURE_DEPLOYMENT_MODE=local-evaluation`). Phase-1 deliverable is the PPTX; video stays disabled unless the product owner explicitly authorizes the evaluation flags.
  - Older generations 1-9 remain in the database with pre-fix low-quality drafts. All generation records are immutable (PROTECT FKs) by design; teachers should open generations 10-16.
- **Verification:** `python manage.py test lectures` 123/123 OK; `scripts/check_workspace.py` WORKSPACE CHECK PASSED; `scripts/taskctl.py validate` task data valid.
- **Pending decision (destructive — needs explicit human approval):** earlier demo rows (users `admin`/`teacher.cs9`, course `CS9`, divisions 1-2, synthetic source 1, generations 1-2, workflow 1) plus pre-fix generations 3-9 and scratch files `.codex/scratch/cs9-textbook-sample.pdf`, `cs9-division.json`. Nothing was deleted.
- **Operational notes for Windows CMD:** helper batch files at the workspace root set every required `AI_LECTURE_*` variable: `start-server.bat` (runserver), `check-db-state.bat` + `check_db_state.py` (DB inventory), `fix-permissions.bat` + `fix_permissions.py`, `reset-passwords.bat`, `verify_endpoints.py` (endpoint smoke check).
- **Prior context (not part of T080):** T050 remains DONE; its synchronization-only finalization commit still requires fresh exact-head CI before PR #11 is merged normally, and PR #8 stays superseded.


## 2026-10-01 — T090 teacherless foundation

- T090 is IN_PROGRESS under codex on `feature/teacherless-lecture-foundation`; PR #14 is open.
- Existing T050 teacher-recording Remotion contract and T080 Django/PPT pipeline are untouched.
- Added isolated `TeacherlessLectureProps` scene contract, deterministic scene renderer, dedicated Remotion entrypoint, synthetic fixture, fixture validator, and boundary documentation.
- Scene primitives currently cover concept text, formulas, diagrams/callouts, fade-in, draw, highlight and step reveal; optional scene audio does not require teacher recordings.
- No database migration, external service, paid AI API, voice cloning, credential or production media was added.
- Branch is 14 commits ahead of main because each small deliverable was committed independently. CI workflow runs were not yet reported for the PR head at handoff; do not treat the PR as verified until CI executes and passes.

## T090 progress update — CI verified

- GitHub Actions `workspace-ci` run #61 completed successfully.
- Passed workspace validation, Django foundation tests/checks, embedded slide engine validation, Remotion dependency/type checking, and the new teacherless fixture check.
- Added approved-generation -> teacherless manifest compiler, immutable source provenance mapping, estimated timeline, SRT export, and provider-neutral TTS contract.
- T091 is queued for real TTS integration and measured audio timing.
- The real browser-based teacherless MP4 smoke render is intentionally still pending; CI does not run the Remotion browser render yet. Do not mark T090 fully complete until that render is executed and inspected.
- PR #14 remains the isolated integration point; main is unchanged.

## 2026-10-01 — T090 MP4 verification + T091 Windows TTS (qoder)

- T090 moved to REVIEW: real MP4 renders proven locally — `data/lectures/t090-teacherless-smoke.mp4` (1.0s) and `data/lectures/t090-teacherless-verify.mp4` (5.8s, 1920x1080); frame stills in `data/lectures/t090-verify-stills/` confirm fadeIn, highlight, draw and stepReveal.
- PR #14 is CI-green and MERGEABLE, but the `centralugi-cmyk` gh account lacks merge permission and direct pushes to `main` are blocked by the local Git safety hook. An account with write access must click merge.
- T091 claimed and moved to REVIEW: `WindowsSystemSpeechProvider` in `lectures/tts.py` (offline, zero-cost, PowerShell System.Speech, mono 22.05 kHz WAV, measured duration + SHA-256 artifact, fail-closed validation); `apply_narration_audio`/`synthesize_teacherless_narration` in `lectures/teacherless.py` attach `narrationAudioSrc`, re-time scenes to measured audio + 300 ms hold, set `ttsProvider`/`AUDIO_READY` and recompute QA; writes `manifest-v2.json` only after full success.
- Tests: `lectures/tests/test_teacherless_tts.py` — 8 tests OK (stub-provider manifest re-timing, fail-closed input checks, live Windows synthesis).
- Audio-integrated demo render: `data/lectures/t090-teacherless-t091-demo.mp4` — 11.1s, 1920x1080, AAC track carrying the AI narration.
- Windows CLI renders need `--timeoutInMilliseconds=300000` and `TEMP`/`TMP` pointed at `data\tmp` (Chrome cold-start constraint on this machine).
- Work done on local branch `integrate-t090` (== `feature/teacherless-lecture-foundation` tip); T091 changes to be pushed as `task/t091-teacherless-tts`.

## 2026-10-01 — T092 intro/outro/logo/music integration (qoder)

- T092 claimed and moved to REVIEW on branch `task/t092-teacherless-branding` (stacked on `task/t091-teacherless-tts`): `TeacherlessProduction` optional block in `remotion/src/teacherlessTypes.ts` (validated srcs, explicit intro/outro durations, traversal-safe) and intro/outro `Sequence`s, scene shift, looping low-volume music `<Audio>` hook and top-right logo `<Img>` watermark in `remotion/src/TeacherlessLecture.tsx`.
- Evidence: `data/lectures/t090-teacherless-t092-demo.mp4` — 601 frames, 20.096s, 1920x1080, AAC narration track, 6.0 MB; stills `data/lectures/t092-stills/t092-intro-60.png`, `t092-scene-300.png`, `t092-outro-550.png` visually confirm intro video, watermark over scenes, and outro.
- Render environment note (PO directive): keep everything under the E-drive project path — `TEMP`/`TMP` = `data\tmp`, `--timeoutInMilliseconds=300000`, `--concurrency=1`. A browser-connect timeout was seen once under heavy RAM/disk pressure; a retry with the same E-drive temp succeeded. Do not scatter scratch to other drives and do not kill the PO's Chrome.
- Pending: PO to supply background music file (hook ready via `musicSrc`); UGI slide-template PPTX backgrounds are a separate follow-up; next up is the Studio "Generate Teacherless Lecture" button, then a real Class 9 Chemistry lecture end-to-end.

## 2026-10-01 — T093 Studio "Generate Teacherless Lecture" button (qoder)

- T093 claimed and moved to REVIEW on branch `task/t093-teacherless-studio-ui` (stacked on `task/t092-teacherless-branding`; PR base must stay that branch until the PO merges the T092 PR).
- New pieces: `TeacherlessRender` model + migration `0011` (immutable, versioned per generation), `lectures/teacherless_render.py` service (request/authz/stale-recovery + full pipeline in a daemon worker thread), `remotion/scripts/render_teacherless.mjs` trusted sibling renderer (T050's locked `render.mjs` untouched), three URLs (`/api/teacherless/generations/<id>/render/`, `/api/teacherless/renders/<id>/status/`, `/teacherless/renders/<id>/media/`), and the Studio lecture "Teacherless Lecture" card with polling, inline preview, download and re-render.
- Two defects were caught only by live browser E2E and are now fixed: the renderer node process could hang after writing the MP4 (leaked chrome-headless-shell handles; script now `process.exit(0)` after rename), and the disabled RUNNING button locked teachers out of stale recovery (button now clickable/idempotent during PENDING/RUNNING).
- Evidence: generation 17 (synthetic `e2e-teacher` demo, dev DB) — v1 MP4 rendered but row stuck RUNNING (pre-fix), recovered as `FAILED RENDER_STALE`; v2 completed end-to-end: SUCCEEDED, 2 scenes, 19714 ms, 6,027,795 bytes, sha256 `2c352220716cb5ac...` at `data/lectures/teacherless/generation-17/render-v2-.../lecture.mp4`. Browser showed download link, Re-render button and playing video element; media returns `video/mp4` inline and `attachment` with `?download=1`.
- Tests: 156/156 `lectures` suite OK (33 new in `lectures/test_teacherless_render.py`); `check_workspace.py` and `taskctl.py validate` passed. Migrations: `0011` is now applied to the dev DB.
- Next (PO priority order): real Class 9 Chemistry lecture end-to-end (warn: a 20-30 min lecture on the i5-6500 estimates several hours of render time), then Google Drive upload (manual first per project rule), then wire the music file when delivered (`data/assets/music/*.mp3|wav` is auto-detected).
