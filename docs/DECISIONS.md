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

