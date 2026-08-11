# T030 Workflow Queue and Approval Foundation

## Boundary

T030 stores workflow state, bounded coordination jobs, safe identifier references and immutable
audit history. It does not record audio, render video, create exports, clone voices or upload
anything. T040, T050, T060 and T070 remain separate tasks. Payload text is treated only as data;
jobs never contain executable commands, arbitrary code, credentials or filesystem paths.

The domain receives a frozen `WorkflowActorContext` containing an actor type, an opaque identity
reference, an internal actor mapping, permitted course IDs and explicit capabilities. Django group
and user lookup occurs only in the current application adapter. CRM sessions, CRM tables and
provider tokens are not domain dependencies; CRM integration remains deferred.

## State machine and gates

| Current state | Permitted next state | Required actor | Additional gate |
|---|---|---|---|
| `SOURCE_CONTENT_READY` | `SLIDE_NARRATION_DRAFT` | system worker | matching successful draft-coordination job |
| `SLIDE_NARRATION_DRAFT` | `TEACHER_SLIDE_NARRATION_APPROVED` | assigned teacher | every current slide revision is teacher-approved |
| `TEACHER_SLIDE_NARRATION_APPROVED` | `RECORDING_PENDING` | system worker | stored approval fingerprint still matches every current slide revision |
| `RECORDING_PENDING` | `RECORDING_READY` | system worker | matching successful recording-readiness job and safe reference |
| `RECORDING_READY` | `DRAFT_VIDEO_PENDING` | system worker | current slide approval remains valid |
| `DRAFT_VIDEO_PENDING` | `DRAFT_VIDEO_READY` | system worker | matching successful video-readiness job and safe reference |
| `DRAFT_VIDEO_READY` | `TEACHER_VIDEO_REVISION_REQUESTED` | assigned teacher | current slide approval remains valid |
| `DRAFT_VIDEO_READY` | `TEACHER_VIDEO_APPROVED` | assigned teacher | current slide approval remains valid |
| `TEACHER_VIDEO_REVISION_REQUESTED` | `DRAFT_VIDEO_PENDING` | system worker | explicit resubmission reason |
| `TEACHER_VIDEO_APPROVED` | `FINAL_ADMIN_APPROVED` | administrator | teacher video approval timestamp and identity exist |
| `FINAL_ADMIN_APPROVED` | `EXPORT_READY` | system worker | matching successful export-readiness job, final admin approval and safe reference |

No other forward, backward or skipped transition is accepted. Administrators cannot grant the
teacher approvals, teachers cannot grant final administrator approval, and neither role can
impersonate a system transition. A current-state version must accompany every transition, so stale
requests fail closed. Transition idempotency keys are unique per workflow and duplicates are
rejected.

Teacher slide approval stores a SHA-256 fingerprint of every slide ID, current version and approved
revision. Any later T022 slide revision clears that approval and all downstream readiness/approval
references, moves the workflow explicitly back to `SLIDE_NARRATION_DRAFT`, and writes a
`SLIDE_REVISION_INVALIDATED` audit event. This is the only controlled backward movement; it prevents
a stale approval from authorizing recording or later stages.

## Audit model

Workflow creation and every state change create one ordered `WorkflowAuditEvent` in the same
database transaction. Each event records the actor type, opaque identity reference, previous state,
new state, allowlisted reason code, idempotency key and database timestamp. `(workflow, sequence)`
and `(workflow, idempotency_key)` are unique.

Queue status changes have equivalent ordered `WorkflowJobEvent` records. Audit/event foreign keys
use `PROTECT`; model mutation/deletion is rejected, the JSON APIs expose inspection only, and all
workflow/queue admin registrations are read-only. Workflow and job model updates are also rejected
outside the domain services, preventing ordinary API/admin/model code from bypassing the gates.

## Queue contract

The database-backed queue has four explicit coordination-only job types:

| Job type | Exact payload |
|---|---|
| `SLIDE_NARRATION_DRAFT` | `{"generation_id": positive_integer}` |
| `RECORDING_READINESS` | `{"approved_slide_revision_ids": [bounded positive integers]}` |
| `DRAFT_VIDEO_READINESS` | `{"recording_reference": "bounded-safe-reference"}` |
| `EXPORT_READINESS` | `{"draft_video_reference": "bounded-safe-reference"}` |

Unexpected fields, malformed JSON, booleans used as IDs, duplicate IDs, unsupported enums,
oversized JSON, path-like strings and unsafe references are rejected. The complete canonical JSON
payload is hashed and bound to the exact workflow version that accepted it.
`(workflow, job_type, idempotency_key)` is unique; the same submission returns the existing job
only when its payload hash, workflow version and retry policy match.

Jobs move through `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED` or `CANCELLED`. Claiming is
transactional, increments the bounded attempt count and assigns a bounded worker identity plus a
30-to-3600-second lease. PostgreSQL uses row locks with `SKIP LOCKED` when supported. Completion
requires the active unexpired lease and is idempotent for the same completion key and result.

Retryable failure returns a job to `PENDING` only while attempts remain. Retry delay is bounded;
reason codes are allowlisted and messages reject path/credential-like data. An expired lease is
transactionally requeued when attempts remain or becomes terminal `FAILED` at the retry limit.
Only pending jobs can be cancelled. Failed, cancelled and stale-version jobs never satisfy a
state-transition job gate, and completing a job never advances a workflow automatically.

## SQLite and PostgreSQL

SQLite is explicitly restricted to one sequential Phase-1 application worker. The setting
`WORKFLOW_SQLITE_SINGLE_WORKER=True` documents and enforces this mode; disabling it rejects queue
claiming. SQLite transactions do not provide a safe production multi-worker claim guarantee.

Before concurrent or multi-teacher production operation, migrate to PostgreSQL and introduce a
controlled worker deployment. The ORM schema uses portable fields, constraints and indexes. The
PostgreSQL claim path uses transactional row locking and `SKIP LOCKED`; deployment-level worker
count, shutdown, monitoring and database connection controls still require separate operational
approval.

## Minimal API foundation

- `GET|POST /api/workflows/` inspects scoped workflows or creates one from a T022 generation.
- `GET /api/workflows/<id>/` inspects current safe state and references.
- `POST /api/workflows/<id>/transition/` requests a versioned permitted transition.
- `GET /api/workflows/<id>/audit/` inspects immutable transition history.
- `GET|POST /api/workflow-jobs/` inspects scoped jobs or submits a validated job.
- `POST /api/workflow-jobs/claim/` provides the privileged local worker claim primitive.
- `POST /api/workflow-jobs/<id>/complete/` completes an actively leased job idempotently.
- `POST /api/workflow-jobs/<id>/fail/` records bounded retryable or terminal failure.
- `POST /api/workflow-jobs/<id>/cancel/` cancels a pending job.

The current HTTP worker adapter requires an authenticated administrator before constructing a
system-worker context. This is an administration foundation, not a processing engine or a claim
that Django login is the only future authentication provider.
