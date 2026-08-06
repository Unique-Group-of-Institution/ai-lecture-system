# Architecture Decision Log

Do not rewrite old decisions. Add a new superseding decision when the project changes direction.

## D001 — Local-first Phase 1

- **Status:** Accepted
- **Decision:** Store and process syllabus, audio, transcripts and renders locally.
- **Reason:** Privacy, zero paid-API cost and operational control.

## D002 — Scene-first recording

- **Status:** Accepted
- **Decision:** Generate and approve scenes/slides before the teacher records audio per scene.
- **Reason:** This resolves the problem of teachers recording without knowing the visible slide and makes corrections local to one scene.

## D003 — Audio integrity gate

- **Status:** Accepted
- **Decision:** Automatic sound cleanup is allowed; semantic cuts require timestamped transcript evidence and teacher approval.
- **Reason:** AI must not silently alter the teacher's meaning.

## D004 — One writer, one reviewer

- **Status:** Accepted
- **Decision:** One AI agent owns an implementation task; another agent or human reviews it.
- **Reason:** Prevent overlapping edits and model-to-model drift.

## D005 — Shared repository instead of live agent chat sync

- **Status:** Accepted
- **Decision:** Claude Code and Codex coordinate through repository files, task history and MCP tools.
- **Reason:** Chats are not a reliable cross-agent source of truth.

## D006 — SQLite first, PostgreSQL-ready schema

- **Status:** Accepted
- **Decision:** Use SQLite for the single-PC pilot while keeping ORM models portable to PostgreSQL.
- **Reason:** Lowest setup burden for the first vertical slice.

## D007 — Human publication gate

- **Status:** Accepted
- **Decision:** No agent may publish to LMS or YouTube without explicit admin approval.
- **Reason:** Quality, privacy and reputational risk.

## D008 — Phase 1 ends at YouTube publication

- **Status:** Accepted
- **Decision:** Defer all LMS integration and LMS API work to a future phase. In Phase 1, generate and approve the final lecture package locally, then copy only approved publication files to the existing YouTube uploader watch folder at `F:\Youtube Setup\youtube-uploader\input_folder`.
- **Reason:** This provides a concrete, local-first publication boundary using the existing uploader without coupling Phase 1 to an unknown LMS. Uploader credentials remain outside the AI Lecture System and must not be inspected, printed, modified or exposed.

## D009 — Institutional private GitHub repository and review workflow

- **Status:** Blocked pending a GitHub plan that supports private-repository branch protection
- **Decision:** Host the project only in the private `Unique-Group-of-Institution/ai-lecture-system` repository. Before T003 can complete, protect `main` from force pushes and deletion. Changes should reach `main` through pull requests with CI validation; required approving reviews need not be enforced while the project has a single operator.
- **Reason:** Institutional ownership, private source control and protected history are required without creating a review rule that the sole operator cannot satisfy. GitHub returned HTTP 403 when protection was requested because the current plan does not support this feature for the private repository. Making the repository public is not an acceptable workaround.

## D010 — Zero-cost local Git safety for the private repository

- **Status:** Accepted; supersedes D009's blocked completion condition
- **Decision:** Keep the institutional repository private and require changes to use `task/*` or `feature/*` branches, pull requests into `main`, and passing CI. Install the version-controlled `.githooks/pre-push` hook in every clone so local direct pushes to `main` are rejected. Defer paid GitHub server-side branch protection.
- **Reason:** The product owner approved this zero-cost Phase-1 substitute after GitHub returned HTTP 403 for private-repository protection on the current organization plan. Local hooks reduce accidental direct pushes but are explicitly not equivalent to server-side enforcement.

## D011 — Django authentication and portable local data foundation

- **Status:** Accepted for T010 review
- **Decision:** Use stable Django 6.0 with its built-in user, group and permission system. Use local SQLite through the Django ORM, with `Teacher` and `Administrator` groups, explicit object-visibility policies, protected ownership relationships, portable constraints and conventional indexes. Teachers may view their own course context and create/view their own lecture requests. Administrators receive all lecture-domain permissions, non-destructive user-management permissions and Django staff access.
- **Reason:** Django 6.0 supports the installed Python 3.14 release and provides a small, maintainable authentication foundation without a custom backend. ORM-only schema features keep the pilot portable to PostgreSQL, while protected foreign keys and scoped query policies preserve teacher content and approval boundaries.

## D012 — Portable CPU-only Whisper benchmark pipeline

- **Status:** Accepted for T020 review
- **Decision:** Use the stable official `whisper.cpp` 1.9.2 Windows x64 CPU build with the multilingual quantized `small-q5_1` model and four CPU threads. Decode authorized M4A input to a separate 16 kHz mono signed-16-bit PCM derivative using the portable Gyan.dev FFmpeg 9.0 Release Essentials build. Keep tools, weights, PCM, transcript, QC and logs beneath ignored local storage; commit only standard-library orchestration, synthetic tests and transcript-free aggregate metrics.
- **Reason:** The target PC has 8 GB RAM, an i5-6500 and no useful CUDA GPU, while its installed Python 3.14 makes native Python Whisper wheels uncertain. The portable CLI completed the 568.789-second pilot in 1,616.126 seconds (RTF 2.8413) with a 670,408,704-byte peak working set and no paid API or external media transfer. Separate no-overwrite PCM conversion preserves the immutable source and makes decoding repeatable.

## D013 — Script-first Phase-1 lecture workflow

- **Status:** Accepted; supersedes full Whisper transcription as a Phase-1 primary-path requirement
- **Decision:** Build Phase 1 around authorized local chapter content, teacher generation guidelines, source-grounded slides, and a per-slide narration script approved before slide-by-slide recording. Use the approved script as the caption/transcript source. Assemble a draft video locally, allow AI-assisted admin editing, require teacher video review and admin final approval, then prepare a local YouTube-ready package. Upload remains a separate explicitly admin-approved action. Local Whisper is optional future QC, not a primary workflow dependency.
- **Reason:** The T020 CPU benchmark ran at RTF 2.8413 and automatic Urdu/Hindi script detection was unreliable. Script-first production preserves source grounding, gives the teacher control before recording, avoids slow full-audio transcription, and provides an approved caption source without weakening privacy or approval gates.

## D014 — Voice cloning is separately consented and deferred

- **Status:** Accepted as a later-phase gate; not authorized for Phase 1
- **Decision:** Any future voice-clone option requires explicit teacher consent, consent revocation, auditable use records and institutional approval before implementation or use.
- **Reason:** A reusable synthetic voice changes the privacy, identity and security boundary. It cannot be inferred from ordinary recording approval and must not enter the Phase-1 workflow.

## D015 — Authorized local content library and page provenance

- **Status:** Accepted for T021 review
- **Decision:** Register only rights-confirmed institutional or teacher-owned PDF/PNG/JPG sources. Institutional content is visible to administrators and the assigned course teacher; teacher uploads are owner/admin private. Store immutable originals and separately versioned page text beneath ignored local storage. Validate names, containment, size, signatures and decoder integrity. Extract PDF text with pypdf and use explicit project-local Tesseract 5.4.0 with official `tessdata_fast` 4.1.0 `urd+eng` and `osd` for scanned pages. Preserve file/page hashes, methods, confidence and review state.
- **Reason:** T022 needs claim-to-page traceability without exposing private material. OCR is advisory: equations, diagrams, RTL layout and complex pages remain subject to teacher review against the retained original page.
