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
