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
