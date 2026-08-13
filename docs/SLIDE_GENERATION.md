# T022 Source-grounded Slide and Narration Foundation

## Phase-1 generator

T022 uses `deterministic-extractive-v1`, a standard-library, local-only reference generator. It
splits reviewed UTF-8 page text at sentence and line boundaries, bounds long spans, assigns the
spans deterministically to an approximate number of slides, and uses the same grounded spans as
the initial per-slide narration. The same ordered snapshots and normalized guidelines produce the
same input hash and draft content.

The generator does not summarize semantically, translate, infer, answer questions or invent bridge
text. Language and tone preferences are recorded for review but do not authorize translation or
rewriting. If no supported text exists, an output item is empty, a source range is invalid, or an
item differs from its cited immutable source span, generation fails closed. These limitations make
the implementation a safe Phase-1 reference and synthetic verification path, not a claim of
AI-quality instructional design.

## Grounding and immutable provenance

A `GenerationRequest` records normalized bounded guidelines, generator key and a SHA-256 digest of
the complete ordered input identity. Each selected source receives a `GenerationSourceSnapshot`
with the source-file hash and exact extraction version. Every eligible `ExtractedPage` becomes a
`GenerationPageSnapshot` containing the reviewed text and its existing hash. Later source or
extraction versions therefore cannot silently remap an existing draft.

Each ordered `SlideClaim` and `NarrationStatement` has at least one `SourceReference` to a page
snapshot, page number and exact character range. The service verifies that the range equals the
stored statement and its hash both when creating a revision and when approving it. Titles are
presentation labels; factual slide content belongs in grounded claims. Missing or changed
provenance blocks approval.

Only rights-confirmed READY sources from the selected chapter are eligible. Their extraction must
be COMPLETE, every OCR page must already carry teacher approval, page bytes must match the T021
hash, and all request, page and total-text resource ceilings must pass. T021 visibility is applied
at the Django boundary and checked again through the internal actor context.

## Teacher revision and approval

Generated slides begin unapproved at revision 1. A revision is append-only and receives the next
version while the slide row is transactionally locked. Phase 1 teacher edits remain extractive:
each submitted claim and narration statement must identify one exact supported source range.
Unsupported prose is rejected instead of being silently accepted as factual content.

Only the teacher who owns the selected course and generation request may revise or approve. A new
revision clears the slide's prior approval and recalculates the request state. Administrators have
read-only inspection in Django admin and cannot substitute their approval for the teacher's.

When a T030 `LectureWorkflow` exists, the same revision transaction also invalidates its stored
slide-approval fingerprint, clears downstream readiness/approval references, returns the workflow
to `SLIDE_NARRATION_DRAFT`, and writes an immutable audit event. Recording and later transitions
therefore cannot rely on a stale T022 approval.

Approval revalidates every claim and narration reference, points the slide at the approved current
revision, and writes an immutable `CanonicalNarrationSnapshot` with approver, time and content hash.
Older canonical snapshots remain as history after a later edit. The caption API returns text only
when the slide currently points to that approved revision; therefore future captions/transcripts
can originate only from approved narration.

## Authentication-provider boundary

The generation domain receives a frozen `GenerationActorContext`: internal actor ID, permitted
course IDs, permitted source IDs and explicit generation/review capabilities. It never receives a
Django request, session, group, CRM table or provider token. `actor_context_for_user` is the current
Django application adapter and continues to enforce T010 permissions and T021 visibility.

A future CRM/SSO adapter may authenticate externally, map the principal to the existing internal
actor/course/source authorization facts, and construct the same context. It must not pass CRM
sessions into generation or change the provenance/revision/approval models. CRM integration is
explicitly deferred and was not implemented in T022.

## Replaceable provider and prompt-injection boundary

`GroundedGenerator` is a small provider protocol returning structured slides and grounded text
ranges. A future separately authorized provider can implement it without changing snapshots,
references, revisions or approvals. No model, runtime, dependency, network call or external content
transfer is used by T022.

Extracted text and teacher guidelines are data, never executable instructions. Requests have strict
types, allowlisted enum values, Unicode/control-character validation and byte/character/count
ceilings. Responses are structured JSON, use a non-sniffable content type and escape HTML-significant
characters. Before enabling any future LLM provider, the adapter must additionally isolate source
text from system policy, treat embedded instructions as quoted source data, require grounded
structured output with exact snapshot references, re-run the same deterministic provenance
validator, fail closed on unsupported output, prevent tool/network access by default, and obtain
separate privacy and provider authorization before any content leaves the local system.

## API foundation

- `GET|POST /api/generations/` lists owned requests or creates a grounded draft.
- `GET /api/generations/<id>/` returns the owned current draft and provenance.
- `POST /api/slides/<id>/revisions/` creates a supported teacher revision.
- `POST /api/slides/<id>/approve/` approves the current grounded revision.
- `GET /api/slides/<id>/caption/` returns only current approved canonical narration.

This task does not include a production frontend, background queue, recording portal, PPTX/video
rendering, voice cloning, CRM integration or upload. SQLite remains suitable for sequential Phase-1
use. T030 now supplies the separately documented queue/state foundation in
`docs/WORKFLOW_QUEUE.md`; PostgreSQL and controlled workers remain required before concurrent
multi-teacher processing.
