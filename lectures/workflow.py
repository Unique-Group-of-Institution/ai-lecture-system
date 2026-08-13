from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.utils import timezone

from .models import (
    Course,
    GenerationRequest,
    LectureWorkflow,
    WorkflowAuditEvent,
    WorkflowJob,
    WorkflowJobEvent,
)
from .roles import ADMINISTRATOR_ROLE, TEACHER_ROLE


ACTOR_TEACHER = "TEACHER"
ACTOR_ADMINISTRATOR = "ADMINISTRATOR"
ACTOR_SYSTEM_WORKER = "SYSTEM_WORKER"

CAP_WORKFLOW_CREATE = "WORKFLOW_CREATE"
CAP_WORKFLOW_INSPECT = "WORKFLOW_INSPECT"
CAP_TEACHER_APPROVAL = "TEACHER_APPROVAL"
CAP_ADMIN_APPROVAL = "ADMIN_APPROVAL"
CAP_SYSTEM_TRANSITION = "SYSTEM_TRANSITION"
CAP_QUEUE_SUBMIT = "QUEUE_SUBMIT"
CAP_QUEUE_INSPECT = "QUEUE_INSPECT"
CAP_QUEUE_WORK = "QUEUE_WORK"
CAP_QUEUE_CANCEL = "QUEUE_CANCEL"
ALL_CAPABILITIES = frozenset(
    {
        CAP_WORKFLOW_CREATE,
        CAP_WORKFLOW_INSPECT,
        CAP_TEACHER_APPROVAL,
        CAP_ADMIN_APPROVAL,
        CAP_SYSTEM_TRANSITION,
        CAP_QUEUE_SUBMIT,
        CAP_QUEUE_INSPECT,
        CAP_QUEUE_WORK,
        CAP_QUEUE_CANCEL,
    }
)

SAFE_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
SAFE_REFERENCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
MAX_PAYLOAD_BYTES = 8192
MAX_REFERENCE_LIST = 100
MIN_LEASE_SECONDS = 30
MAX_LEASE_SECONDS = 3600
MAX_RETRY_DELAY_SECONDS = 3600


class WorkflowConflict(ValidationError):
    pass


class QueueConfigurationError(ValidationError):
    pass


@dataclass(frozen=True)
class WorkflowActorContext:
    """Authentication-provider-independent authorization facts for workflow services."""

    actor_type: str
    identity_reference: str
    internal_actor_id: int
    permitted_course_ids: frozenset[int]
    capabilities: frozenset[str]

    def has(self, capability: str) -> bool:
        return capability in self.capabilities


def workflow_actor_for_user(user) -> WorkflowActorContext:
    """Current Django adapter; no session, provider token, or CRM record enters the domain."""

    if not user.is_authenticated:
        return WorkflowActorContext("UNAUTHORIZED", "anonymous", 0, frozenset(), frozenset())
    identity = f"user:{user.pk}"
    if user.groups.filter(name=TEACHER_ROLE).exists():
        courses = frozenset(user.courses_taught.filter(is_active=True).values_list("pk", flat=True))
        return WorkflowActorContext(
            ACTOR_TEACHER,
            identity,
            user.pk,
            courses,
            frozenset(
                {
                    CAP_WORKFLOW_CREATE,
                    CAP_WORKFLOW_INSPECT,
                    CAP_TEACHER_APPROVAL,
                    CAP_QUEUE_SUBMIT,
                    CAP_QUEUE_INSPECT,
                    CAP_QUEUE_CANCEL,
                }
            ),
        )
    if user.groups.filter(name=ADMINISTRATOR_ROLE).exists():
        courses = frozenset(Course.objects.values_list("pk", flat=True))
        return WorkflowActorContext(
            ACTOR_ADMINISTRATOR,
            identity,
            user.pk,
            courses,
            frozenset(
                {
                    CAP_WORKFLOW_INSPECT,
                    CAP_ADMIN_APPROVAL,
                    CAP_QUEUE_SUBMIT,
                    CAP_QUEUE_INSPECT,
                    CAP_QUEUE_CANCEL,
                }
            ),
        )
    return WorkflowActorContext("UNAUTHORIZED", identity, user.pk or 0, frozenset(), frozenset())


def system_worker_context(*, identity_reference: str, permitted_course_ids) -> WorkflowActorContext:
    return WorkflowActorContext(
        ACTOR_SYSTEM_WORKER,
        _safe_token(identity_reference, "worker identity"),
        0,
        frozenset(_positive_ids(permitted_course_ids, "permitted courses", maximum=10_000)),
        frozenset(
            {
                CAP_WORKFLOW_INSPECT,
                CAP_SYSTEM_TRANSITION,
                CAP_QUEUE_SUBMIT,
                CAP_QUEUE_INSPECT,
                CAP_QUEUE_WORK,
                CAP_QUEUE_CANCEL,
            }
        ),
    )


def workflows_visible_to(actor: WorkflowActorContext):
    if not actor.has(CAP_WORKFLOW_INSPECT):
        return LectureWorkflow.objects.none()
    rows = LectureWorkflow.objects.filter(
        generation__chapter__course_id__in=actor.permitted_course_ids
    )
    if actor.actor_type == ACTOR_TEACHER:
        rows = rows.filter(
            generation__requested_by_id=actor.internal_actor_id,
            generation__chapter__course__teacher_id=actor.internal_actor_id,
        )
    return rows


def jobs_visible_to(actor: WorkflowActorContext):
    if not actor.has(CAP_QUEUE_INSPECT):
        return WorkflowJob.objects.none()
    rows = WorkflowJob.objects.filter(
        workflow__generation__chapter__course_id__in=actor.permitted_course_ids
    )
    if actor.actor_type == ACTOR_TEACHER:
        rows = rows.filter(
            workflow__generation__requested_by_id=actor.internal_actor_id,
            workflow__generation__chapter__course__teacher_id=actor.internal_actor_id,
        )
    return rows


def _safe_token(value, field: str) -> str:
    if not isinstance(value, str) or not SAFE_TOKEN.fullmatch(value) or ".." in value:
        raise ValidationError(f"Invalid {field}.")
    return value


def _safe_reference(value, field: str, *, required: bool = True) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"Invalid {field}.")
    value = value.strip()
    if not value and not required:
        return ""
    if not SAFE_REFERENCE.fullmatch(value) or ".." in value:
        raise ValidationError(f"Invalid {field}.")
    return value


def _positive_int(value, field: str, *, minimum: int = 1, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValidationError(f"Invalid {field}.")
    if maximum is not None and value > maximum:
        raise ValidationError(f"Invalid {field}.")
    return value


def _positive_ids(values, field: str, *, maximum: int) -> tuple[int, ...]:
    if (
        not isinstance(values, (list, tuple, set, frozenset))
        or not values
        or len(values) > maximum
        or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in values)
    ):
        raise ValidationError(f"Invalid {field}.")
    result = tuple(values)
    if len(set(result)) != len(result):
        raise ValidationError(f"Invalid {field}.")
    return result


def _bounded_json(value, field: str) -> tuple[dict, str]:
    if not isinstance(value, dict):
        raise ValidationError(f"Invalid {field}.")
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Invalid {field}.") from exc
    if len(encoded) > MAX_PAYLOAD_BYTES:
        raise ValidationError(f"Invalid {field}.")
    return value, hashlib.sha256(encoded).hexdigest()


def _course_id(workflow: LectureWorkflow) -> int:
    return workflow.generation.chapter.course_id


def _validate_actor(actor: WorkflowActorContext) -> None:
    if not isinstance(actor, WorkflowActorContext) or actor.actor_type not in {
        ACTOR_TEACHER,
        ACTOR_ADMINISTRATOR,
        ACTOR_SYSTEM_WORKER,
    }:
        raise PermissionDenied("Invalid workflow actor context.")
    _safe_token(actor.identity_reference, "actor identity")
    if (
        isinstance(actor.internal_actor_id, bool)
        or not isinstance(actor.internal_actor_id, int)
        or actor.internal_actor_id < 0
        or (actor.actor_type != ACTOR_SYSTEM_WORKER and actor.internal_actor_id == 0)
        or not isinstance(actor.permitted_course_ids, frozenset)
        or any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in actor.permitted_course_ids
        )
        or not isinstance(actor.capabilities, frozenset)
        or not actor.capabilities.issubset(ALL_CAPABILITIES)
    ):
        raise ValidationError("Invalid workflow actor context.")


def _require_course(actor: WorkflowActorContext, workflow: LectureWorkflow, capability: str) -> None:
    _validate_actor(actor)
    if not actor.has(capability) or _course_id(workflow) not in actor.permitted_course_ids:
        raise PermissionDenied("Workflow operation is not authorized.")
    if actor.actor_type == ACTOR_TEACHER and (
        workflow.generation.requested_by_id != actor.internal_actor_id
        or workflow.generation.chapter.course.teacher_id != actor.internal_actor_id
    ):
        raise PermissionDenied("Workflow operation is not authorized for this teacher.")


def _save_workflow(workflow: LectureWorkflow) -> None:
    workflow._domain_service_write = True
    try:
        workflow.save()
    finally:
        del workflow._domain_service_write


def _save_job(job: WorkflowJob) -> None:
    job._domain_service_write = True
    try:
        job.save()
    finally:
        del job._domain_service_write


def _workflow_event(
    workflow: LectureWorkflow,
    *,
    actor: WorkflowActorContext,
    previous_state: str,
    new_state: str,
    reason_code: str,
    idempotency_key: str,
) -> WorkflowAuditEvent:
    return WorkflowAuditEvent.objects.create(
        workflow=workflow,
        sequence=workflow.version,
        actor_type=actor.actor_type,
        actor_identity_reference=actor.identity_reference,
        previous_state=previous_state,
        new_state=new_state,
        reason_code=reason_code,
        idempotency_key=idempotency_key,
    )


@transaction.atomic
def create_workflow(
    *, actor: WorkflowActorContext, generation_id: int, idempotency_key: str
) -> LectureWorkflow:
    _validate_actor(actor)
    if not actor.has(CAP_WORKFLOW_CREATE) or actor.actor_type != ACTOR_TEACHER:
        raise PermissionDenied("Workflow creation is not authorized.")
    generation_id = _positive_int(generation_id, "generation identifier")
    idempotency_key = _safe_token(idempotency_key, "idempotency key")
    generation = GenerationRequest.objects.select_for_update().select_related("chapter__course").get(
        pk=generation_id
    )
    if (
        generation.chapter.course_id not in actor.permitted_course_ids
        or actor.internal_actor_id != generation.requested_by_id
        or actor.internal_actor_id != generation.chapter.course.teacher_id
        or not generation.source_snapshots.exists()
    ):
        raise PermissionDenied("Generation is outside the actor's authorized workflow context.")
    existing = LectureWorkflow.objects.select_for_update().filter(generation=generation).first()
    if existing is not None:
        event = existing.audit_events.filter(sequence=1).first()
        if event and event.idempotency_key == idempotency_key:
            return existing
        raise WorkflowConflict("A workflow already exists for this generation.")
    workflow = LectureWorkflow.objects.create(generation=generation)
    _workflow_event(
        workflow,
        actor=actor,
        previous_state="",
        new_state=workflow.state,
        reason_code="WORKFLOW_CREATED",
        idempotency_key=idempotency_key,
    )
    return workflow


def _approval_fingerprint(workflow: LectureWorkflow, *, lock: bool = False) -> str:
    slides = workflow.generation.slides.order_by("pk")
    if lock:
        slides = slides.select_for_update()
    rows = list(
        slides.values_list(
            "pk",
            "current_version",
            "approved_revision_id",
            "approved_revision__version",
            "approved_revision__slide_id",
        )
    )
    if not rows or any(
        approved_id is None or current != approved_version or slide_id != approved_slide_id
        for slide_id, current, approved_id, approved_version, approved_slide_id in rows
    ):
        raise ValidationError("Current slide and narration revisions require teacher approval.")
    encoded = json.dumps(rows, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _require_current_slide_approval(workflow: LectureWorkflow, *, lock: bool = False) -> str:
    fingerprint = _approval_fingerprint(workflow, lock=lock)
    if workflow.slide_approval_fingerprint and workflow.slide_approval_fingerprint != fingerprint:
        raise ValidationError("Stored teacher approval is stale for the current slide revision.")
    return fingerprint


TRANSITIONS = {
    LectureWorkflow.State.SOURCE_CONTENT_READY: {LectureWorkflow.State.SLIDE_NARRATION_DRAFT},
    LectureWorkflow.State.SLIDE_NARRATION_DRAFT: {
        LectureWorkflow.State.TEACHER_SLIDE_NARRATION_APPROVED
    },
    LectureWorkflow.State.TEACHER_SLIDE_NARRATION_APPROVED: {
        LectureWorkflow.State.RECORDING_PENDING
    },
    LectureWorkflow.State.RECORDING_PENDING: {LectureWorkflow.State.RECORDING_READY},
    LectureWorkflow.State.RECORDING_READY: {LectureWorkflow.State.DRAFT_VIDEO_PENDING},
    LectureWorkflow.State.DRAFT_VIDEO_PENDING: {LectureWorkflow.State.DRAFT_VIDEO_READY},
    LectureWorkflow.State.DRAFT_VIDEO_READY: {
        LectureWorkflow.State.TEACHER_VIDEO_REVISION_REQUESTED,
        LectureWorkflow.State.TEACHER_VIDEO_APPROVED,
    },
    LectureWorkflow.State.TEACHER_VIDEO_REVISION_REQUESTED: {
        LectureWorkflow.State.DRAFT_VIDEO_PENDING
    },
    LectureWorkflow.State.TEACHER_VIDEO_APPROVED: {LectureWorkflow.State.FINAL_ADMIN_APPROVED},
    LectureWorkflow.State.FINAL_ADMIN_APPROVED: {LectureWorkflow.State.EXPORT_READY},
    LectureWorkflow.State.EXPORT_READY: set(),
}

REASON_BY_TARGET = {
    LectureWorkflow.State.SLIDE_NARRATION_DRAFT: "DRAFT_AVAILABLE",
    LectureWorkflow.State.TEACHER_SLIDE_NARRATION_APPROVED: "TEACHER_APPROVED_CURRENT_DRAFT",
    LectureWorkflow.State.RECORDING_PENDING: "RECORDING_SCHEDULED",
    LectureWorkflow.State.RECORDING_READY: "RECORDING_REFERENCE_READY",
    LectureWorkflow.State.DRAFT_VIDEO_PENDING: {"VIDEO_DRAFT_SCHEDULED", "VIDEO_RESUBMITTED"},
    LectureWorkflow.State.DRAFT_VIDEO_READY: "VIDEO_REFERENCE_READY",
    LectureWorkflow.State.TEACHER_VIDEO_REVISION_REQUESTED: "TEACHER_REQUESTED_VIDEO_REVISION",
    LectureWorkflow.State.TEACHER_VIDEO_APPROVED: "TEACHER_APPROVED_VIDEO",
    LectureWorkflow.State.FINAL_ADMIN_APPROVED: "ADMIN_APPROVED_FINAL",
    LectureWorkflow.State.EXPORT_READY: "EXPORT_HANDOFF_READY",
}

JOB_REQUIRED_BY_TARGET = {
    LectureWorkflow.State.SLIDE_NARRATION_DRAFT: WorkflowJob.JobType.SLIDE_NARRATION_DRAFT,
    LectureWorkflow.State.RECORDING_READY: WorkflowJob.JobType.RECORDING_READINESS,
    LectureWorkflow.State.DRAFT_VIDEO_READY: WorkflowJob.JobType.DRAFT_VIDEO_READINESS,
    LectureWorkflow.State.EXPORT_READY: WorkflowJob.JobType.EXPORT_READINESS,
}


def _validate_transition_actor(actor: WorkflowActorContext, target: str) -> None:
    teacher_targets = {
        LectureWorkflow.State.TEACHER_SLIDE_NARRATION_APPROVED,
        LectureWorkflow.State.TEACHER_VIDEO_REVISION_REQUESTED,
        LectureWorkflow.State.TEACHER_VIDEO_APPROVED,
    }
    if target in teacher_targets:
        if actor.actor_type != ACTOR_TEACHER or not actor.has(CAP_TEACHER_APPROVAL):
            raise PermissionDenied("This transition requires the assigned teacher.")
    elif target == LectureWorkflow.State.FINAL_ADMIN_APPROVED:
        if actor.actor_type != ACTOR_ADMINISTRATOR or not actor.has(CAP_ADMIN_APPROVAL):
            raise PermissionDenied("This transition requires an administrator.")
    elif actor.actor_type != ACTOR_SYSTEM_WORKER or not actor.has(CAP_SYSTEM_TRANSITION):
        raise PermissionDenied("This transition requires a system worker.")


def _validate_transition_job(
    workflow: LectureWorkflow, target: str, job_id
) -> tuple[WorkflowJob | None, str]:
    required_type = JOB_REQUIRED_BY_TARGET.get(target)
    if required_type is None:
        if job_id is not None:
            raise ValidationError("This transition does not accept a job reference.")
        return None, ""
    job_id = _positive_int(job_id, "job identifier")
    job = WorkflowJob.objects.select_for_update().filter(pk=job_id, workflow=workflow).first()
    if job is None or job.job_type != required_type or job.status != WorkflowJob.Status.SUCCEEDED:
        raise ValidationError("A matching successful workflow job is required.")
    if job.workflow_version != workflow.version:
        raise ValidationError("The successful workflow job belongs to a stale state version.")
    validate_job_payload(job.job_type, job.payload, workflow)
    clean_result, _ = validate_job_result(job, job.result)
    artifact_key = RESULT_ARTIFACT_KEY.get(job.job_type)
    return job, clean_result[artifact_key] if artifact_key else ""


@transaction.atomic
def transition_workflow(
    *,
    actor: WorkflowActorContext,
    workflow_id: int,
    target_state: str,
    reason_code: str,
    expected_version: int,
    idempotency_key: str,
    job_id=None,
    artifact_reference: str = "",
) -> LectureWorkflow:
    workflow_id = _positive_int(workflow_id, "workflow identifier")
    expected_version = _positive_int(expected_version, "workflow version")
    idempotency_key = _safe_token(idempotency_key, "idempotency key")
    if target_state not in LectureWorkflow.State.values:
        raise ValidationError("Invalid workflow state.")
    workflow = LectureWorkflow.objects.select_for_update().select_related(
        "generation__chapter__course"
    ).get(pk=workflow_id)
    _require_course(actor, workflow, CAP_WORKFLOW_INSPECT)
    if workflow.audit_events.filter(idempotency_key=idempotency_key).exists():
        raise WorkflowConflict("Duplicate workflow transition.")
    if workflow.version != expected_version:
        raise WorkflowConflict("Stale workflow version.")
    if target_state not in TRANSITIONS[workflow.state]:
        raise WorkflowConflict("Invalid or skipped workflow transition.")
    allowed_reason = REASON_BY_TARGET[target_state]
    if target_state == LectureWorkflow.State.DRAFT_VIDEO_PENDING:
        allowed_reason = (
            "VIDEO_RESUBMITTED"
            if workflow.state == LectureWorkflow.State.TEACHER_VIDEO_REVISION_REQUESTED
            else "VIDEO_DRAFT_SCHEDULED"
        )
    if reason_code not in ({allowed_reason} if isinstance(allowed_reason, str) else allowed_reason):
        raise ValidationError("Invalid workflow reason code.")
    _validate_transition_actor(actor, target_state)
    transition_job, authorized_artifact_reference = _validate_transition_job(
        workflow, target_state, job_id
    )

    if workflow.state not in {
        LectureWorkflow.State.SOURCE_CONTENT_READY,
        LectureWorkflow.State.SLIDE_NARRATION_DRAFT,
    } or target_state == LectureWorkflow.State.TEACHER_SLIDE_NARRATION_APPROVED:
        fingerprint = _require_current_slide_approval(workflow, lock=True)
    else:
        fingerprint = ""

    artifact_reference = _safe_reference(
        artifact_reference,
        "artifact reference",
        required=target_state
        in {
            LectureWorkflow.State.RECORDING_READY,
            LectureWorkflow.State.DRAFT_VIDEO_READY,
            LectureWorkflow.State.EXPORT_READY,
        },
    )
    if artifact_reference and target_state not in {
        LectureWorkflow.State.RECORDING_READY,
        LectureWorkflow.State.DRAFT_VIDEO_READY,
        LectureWorkflow.State.EXPORT_READY,
    }:
        raise ValidationError("This transition does not accept an artifact reference.")
    if transition_job is not None and authorized_artifact_reference:
        if artifact_reference != authorized_artifact_reference:
            raise ValidationError("Artifact reference does not match the completed workflow job.")
        artifact_reference = authorized_artifact_reference

    previous = workflow.state
    workflow.state = target_state
    workflow.version += 1
    if target_state == LectureWorkflow.State.TEACHER_SLIDE_NARRATION_APPROVED:
        workflow.slide_approval_fingerprint = fingerprint
    elif target_state == LectureWorkflow.State.RECORDING_READY:
        workflow.recording_reference = artifact_reference
    elif target_state == LectureWorkflow.State.DRAFT_VIDEO_READY:
        workflow.draft_video_reference = artifact_reference
    elif target_state == LectureWorkflow.State.TEACHER_VIDEO_REVISION_REQUESTED:
        workflow.teacher_video_approved_by = ""
        workflow.teacher_video_approved_at = None
        workflow.final_admin_approved_by = ""
        workflow.final_admin_approved_at = None
    elif target_state == LectureWorkflow.State.TEACHER_VIDEO_APPROVED:
        workflow.teacher_video_approved_by = actor.identity_reference
        workflow.teacher_video_approved_at = timezone.now()
    elif target_state == LectureWorkflow.State.FINAL_ADMIN_APPROVED:
        if not workflow.teacher_video_approved_at:
            raise ValidationError("Teacher video approval is required before final approval.")
        workflow.final_admin_approved_by = actor.identity_reference
        workflow.final_admin_approved_at = timezone.now()
    elif target_state == LectureWorkflow.State.EXPORT_READY:
        if not workflow.final_admin_approved_at:
            raise ValidationError("Final administrator approval is required before export handoff.")
        workflow.export_reference = artifact_reference
    _save_workflow(workflow)
    _workflow_event(
        workflow,
        actor=actor,
        previous_state=previous,
        new_state=target_state,
        reason_code=reason_code,
        idempotency_key=idempotency_key,
    )
    return workflow


def invalidate_workflow_for_slide_revision(
    *, workflow: LectureWorkflow | None, actor_identity_reference: str, slide_id: int, revision_version: int
) -> None:
    """Called while the workflow row is locked by the T022 revision transaction."""

    if workflow is None or workflow.state in {
        LectureWorkflow.State.SOURCE_CONTENT_READY,
        LectureWorkflow.State.SLIDE_NARRATION_DRAFT,
    }:
        return
    slide_id = _positive_int(slide_id, "slide identifier")
    revision_version = _positive_int(revision_version, "revision version")
    identity = _safe_token(actor_identity_reference, "actor identity")
    previous = workflow.state
    workflow.state = LectureWorkflow.State.SLIDE_NARRATION_DRAFT
    workflow.version += 1
    workflow.slide_approval_fingerprint = ""
    workflow.recording_reference = ""
    workflow.draft_video_reference = ""
    workflow.export_reference = ""
    workflow.teacher_video_approved_by = ""
    workflow.teacher_video_approved_at = None
    workflow.final_admin_approved_by = ""
    workflow.final_admin_approved_at = None
    _save_workflow(workflow)
    _workflow_event(
        workflow,
        actor=WorkflowActorContext(ACTOR_TEACHER, identity, 0, frozenset(), frozenset()),
        previous_state=previous,
        new_state=workflow.state,
        reason_code="SLIDE_REVISION_INVALIDATED",
        idempotency_key=f"slide-revision:{slide_id}:v{revision_version}",
    )


JOB_STATE = {
    WorkflowJob.JobType.SLIDE_NARRATION_DRAFT: LectureWorkflow.State.SOURCE_CONTENT_READY,
    WorkflowJob.JobType.RECORDING_READINESS: LectureWorkflow.State.RECORDING_PENDING,
    WorkflowJob.JobType.DRAFT_VIDEO_READINESS: LectureWorkflow.State.DRAFT_VIDEO_PENDING,
    WorkflowJob.JobType.EXPORT_READINESS: LectureWorkflow.State.FINAL_ADMIN_APPROVED,
}


def validate_job_payload(job_type: str, payload, workflow: LectureWorkflow) -> tuple[dict, str]:
    if job_type not in WorkflowJob.JobType.values:
        raise ValidationError("Invalid job type.")
    payload, digest = _bounded_json(payload, "job payload")
    if job_type == WorkflowJob.JobType.SLIDE_NARRATION_DRAFT:
        if set(payload) != {"generation_id"} or payload["generation_id"] != workflow.generation_id:
            raise ValidationError("Invalid job payload.")
        _positive_int(payload["generation_id"], "generation identifier")
    elif job_type == WorkflowJob.JobType.RECORDING_READINESS:
        if set(payload) != {"approved_slide_revision_ids"}:
            raise ValidationError("Invalid job payload.")
        supplied = _positive_ids(
            payload["approved_slide_revision_ids"],
            "approved slide revisions",
            maximum=MAX_REFERENCE_LIST,
        )
        current = tuple(
            workflow.generation.slides.order_by("pk").values_list("approved_revision_id", flat=True)
        )
        if None in current or supplied != current:
            raise ValidationError("Job payload does not reference every current approved slide revision.")
    elif job_type == WorkflowJob.JobType.DRAFT_VIDEO_READINESS:
        if set(payload) != {"recording_reference"}:
            raise ValidationError("Invalid job payload.")
        reference = _safe_reference(payload["recording_reference"], "recording reference")
        if reference != workflow.recording_reference:
            raise ValidationError("Job payload does not match the workflow recording reference.")
    else:
        if set(payload) != {"draft_video_reference"}:
            raise ValidationError("Invalid job payload.")
        reference = _safe_reference(payload["draft_video_reference"], "draft video reference")
        if reference != workflow.draft_video_reference:
            raise ValidationError("Job payload does not match the approved video reference.")
    return payload, digest


def _job_event(
    job: WorkflowJob,
    *,
    actor: WorkflowActorContext,
    previous_status: str,
    new_status: str,
    reason_code: str,
) -> WorkflowJobEvent:
    return WorkflowJobEvent.objects.create(
        job=job,
        sequence=job.events.count() + 1,
        actor_type=actor.actor_type,
        actor_identity_reference=actor.identity_reference,
        previous_status=previous_status,
        new_status=new_status,
        reason_code=reason_code,
    )


@transaction.atomic
def submit_job(
    *,
    actor: WorkflowActorContext,
    workflow_id: int,
    job_type: str,
    payload,
    idempotency_key: str,
    max_attempts: int = 3,
) -> WorkflowJob:
    workflow_id = _positive_int(workflow_id, "workflow identifier")
    idempotency_key = _safe_token(idempotency_key, "idempotency key")
    max_attempts = _positive_int(max_attempts, "maximum attempts", maximum=5)
    workflow = LectureWorkflow.objects.select_for_update().select_related(
        "generation__chapter__course"
    ).get(pk=workflow_id)
    _require_course(actor, workflow, CAP_QUEUE_SUBMIT)
    if JOB_STATE.get(job_type) != workflow.state:
        raise WorkflowConflict("Job type is not permitted in the current workflow state.")
    clean_payload, digest = validate_job_payload(job_type, payload, workflow)
    existing = WorkflowJob.objects.filter(
        workflow=workflow, job_type=job_type, idempotency_key=idempotency_key
    ).first()
    if existing is not None:
        if (
            existing.payload_sha256 == digest
            and existing.max_attempts == max_attempts
            and existing.workflow_version == workflow.version
        ):
            return existing
        raise WorkflowConflict("Idempotency key was already used with different job input.")
    now = timezone.now()
    job = WorkflowJob.objects.create(
        workflow=workflow,
        job_type=job_type,
        payload=clean_payload,
        payload_sha256=digest,
        idempotency_key=idempotency_key,
        workflow_version=workflow.version,
        max_attempts=max_attempts,
        available_at=now,
        created_by_actor_type=actor.actor_type,
        created_by_identity_reference=actor.identity_reference,
    )
    _job_event(
        job,
        actor=actor,
        previous_status="",
        new_status=job.status,
        reason_code="JOB_SUBMITTED",
    )
    return job


def _ensure_queue_backend() -> None:
    if connection.vendor == "sqlite" and not getattr(settings, "WORKFLOW_SQLITE_SINGLE_WORKER", True):
        raise QueueConfigurationError(
            "SQLite queue operation requires the Phase-1 sequential single-worker setting."
        )


def _lock_jobs(queryset):
    if connection.vendor == "postgresql" and connection.features.has_select_for_update_skip_locked:
        return queryset.select_for_update(skip_locked=True)
    return queryset.select_for_update()


def _recover_expired_leases(*, actor: WorkflowActorContext, now) -> None:
    expired = _lock_jobs(
        WorkflowJob.objects.filter(
            status=WorkflowJob.Status.RUNNING,
            leased_until__lte=now,
            workflow__generation__chapter__course_id__in=actor.permitted_course_ids,
        ).order_by("pk")
    )
    for job in expired:
        previous = job.status
        job.lease_owner = ""
        job.leased_until = None
        if job.attempts >= job.max_attempts:
            job.status = WorkflowJob.Status.FAILED
            job.failure_reason_code = "LEASE_EXPIRED"
            job.failure_message = "The worker lease expired at the retry limit."
            job.finished_at = now
            reason = "LEASE_EXPIRED_TERMINAL"
        else:
            job.status = WorkflowJob.Status.PENDING
            job.available_at = now
            reason = "LEASE_EXPIRED_REQUEUED"
        _save_job(job)
        _job_event(
            job,
            actor=actor,
            previous_status=previous,
            new_status=job.status,
            reason_code=reason,
        )


@transaction.atomic
def claim_job(
    *,
    actor: WorkflowActorContext,
    lease_seconds: int,
    job_types: list[str] | None = None,
    now=None,
) -> WorkflowJob | None:
    _validate_actor(actor)
    if actor.actor_type != ACTOR_SYSTEM_WORKER or not actor.has(CAP_QUEUE_WORK):
        raise PermissionDenied("Job claiming requires a system worker.")
    _ensure_queue_backend()
    lease_seconds = _positive_int(
        lease_seconds,
        "lease duration",
        minimum=MIN_LEASE_SECONDS,
        maximum=MAX_LEASE_SECONDS,
    )
    if job_types is not None:
        if (
            not isinstance(job_types, list)
            or not job_types
            or len(job_types) > len(WorkflowJob.JobType.values)
            or any(value not in WorkflowJob.JobType.values for value in job_types)
            or len(set(job_types)) != len(job_types)
        ):
            raise ValidationError("Invalid job type filter.")
    now = now or timezone.now()
    _recover_expired_leases(actor=actor, now=now)
    query = WorkflowJob.objects.filter(
        status=WorkflowJob.Status.PENDING,
        available_at__lte=now,
        workflow__generation__chapter__course_id__in=actor.permitted_course_ids,
    )
    if job_types:
        query = query.filter(job_type__in=job_types)
    job = _lock_jobs(query.order_by("available_at", "created_at", "pk")).first()
    if job is None:
        return None
    previous = job.status
    job.status = WorkflowJob.Status.RUNNING
    job.attempts += 1
    job.lease_owner = actor.identity_reference
    job.leased_until = now + timedelta(seconds=lease_seconds)
    job.started_at = now
    job.failure_reason_code = ""
    job.failure_message = ""
    _save_job(job)
    _job_event(
        job,
        actor=actor,
        previous_status=previous,
        new_status=job.status,
        reason_code="JOB_CLAIMED",
    )
    return job


def _validate_running_lease(job: WorkflowJob, actor: WorkflowActorContext, now) -> None:
    _validate_actor(actor)
    if (
        actor.actor_type != ACTOR_SYSTEM_WORKER
        or not actor.has(CAP_QUEUE_WORK)
        or job.workflow.generation.chapter.course_id not in actor.permitted_course_ids
        or job.lease_owner != actor.identity_reference
        or job.leased_until is None
        or job.leased_until <= now
    ):
        raise PermissionDenied("The active job lease is unavailable to this worker.")


RESULT_ARTIFACT_KEY = {
    WorkflowJob.JobType.RECORDING_READINESS: "recording_reference",
    WorkflowJob.JobType.DRAFT_VIDEO_READINESS: "draft_video_reference",
    WorkflowJob.JobType.EXPORT_READINESS: "export_reference",
}


def validate_job_result(job: WorkflowJob, result) -> tuple[dict, str]:
    """Validate a bounded completion result against its locked job context."""

    result, digest = _bounded_json(result, "job result")
    common_fields = {"job_id", "job_type", "workflow_id", "workflow_version"}
    if job.job_type == WorkflowJob.JobType.SLIDE_NARRATION_DRAFT:
        if set(result) != common_fields | {"generation_id"}:
            raise ValidationError("Invalid job result.")
        generation_id = _positive_int(result["generation_id"], "generation identifier")
        if generation_id != job.workflow.generation_id:
            raise ValidationError("Job result does not match its workflow context.")
    else:
        artifact_key = RESULT_ARTIFACT_KEY.get(job.job_type)
        if artifact_key is None or set(result) != common_fields | {artifact_key}:
            raise ValidationError("Invalid job result.")
        _safe_reference(result[artifact_key], "artifact reference")
    job_id = _positive_int(result.get("job_id"), "job identifier")
    if result.get("job_type") != job.job_type:
        raise ValidationError("Job result does not match its workflow context.")
    workflow_id = _positive_int(result.get("workflow_id"), "workflow identifier")
    workflow_version = _positive_int(result.get("workflow_version"), "workflow version")
    if (
        job_id != job.pk
        or workflow_id != job.workflow_id
        or workflow_version != job.workflow_version
    ):
        raise ValidationError("Job result does not match its workflow context.")
    return result, digest


@transaction.atomic
def complete_job(
    *,
    actor: WorkflowActorContext,
    job_id: int,
    completion_idempotency_key: str,
    result,
    now=None,
) -> WorkflowJob:
    job_id = _positive_int(job_id, "job identifier")
    completion_idempotency_key = _safe_token(completion_idempotency_key, "completion idempotency key")
    now = now or timezone.now()
    job = WorkflowJob.objects.select_for_update().select_related(
        "workflow__generation__chapter__course"
    ).get(pk=job_id)
    _validate_actor(actor)
    if (
        actor.actor_type != ACTOR_SYSTEM_WORKER
        or not actor.has(CAP_QUEUE_WORK)
        or job.workflow.generation.chapter.course_id not in actor.permitted_course_ids
        or job.lease_owner != actor.identity_reference
    ):
        raise PermissionDenied("Job completion is unavailable to this worker.")
    clean_result, _ = validate_job_result(job, result)
    if job.status == WorkflowJob.Status.SUCCEEDED:
        if job.completion_idempotency_key == completion_idempotency_key and job.result == clean_result:
            return job
        raise WorkflowConflict("Job was already completed with different completion input.")
    if job.status != WorkflowJob.Status.RUNNING:
        raise WorkflowConflict("Only a running job can be completed.")
    _validate_running_lease(job, actor, now)
    previous = job.status
    job.status = WorkflowJob.Status.SUCCEEDED
    job.completion_idempotency_key = completion_idempotency_key
    job.result = clean_result
    job.leased_until = None
    job.finished_at = now
    _save_job(job)
    _job_event(
        job,
        actor=actor,
        previous_status=previous,
        new_status=job.status,
        reason_code="JOB_COMPLETED",
    )
    return job


FAILURE_CODES = {
    "WORKER_ERROR",
    "TIMEOUT",
    "RESOURCE_LIMIT",
    "DEPENDENCY_UNAVAILABLE",
    "INVALID_INPUT",
}


def _privacy_safe_message(value) -> str:
    if not isinstance(value, str):
        raise ValidationError("Invalid failure message.")
    value = value.strip()
    lowered = value.casefold()
    if (
        not value
        or len(value) > 300
        or "/" in value
        or "\\" in value
        or re.search(r"[A-Za-z]:", value)
        or any(token in lowered for token in ("password", "secret", "token=", "api_key", "credential"))
    ):
        raise ValidationError("Invalid failure message.")
    return value


@transaction.atomic
def fail_job(
    *,
    actor: WorkflowActorContext,
    job_id: int,
    reason_code: str,
    message: str,
    retryable: bool,
    retry_delay_seconds: int = 0,
    now=None,
) -> WorkflowJob:
    job_id = _positive_int(job_id, "job identifier")
    if reason_code not in FAILURE_CODES or not isinstance(retryable, bool):
        raise ValidationError("Invalid job failure details.")
    message = _privacy_safe_message(message)
    retry_delay_seconds = _positive_int(
        retry_delay_seconds,
        "retry delay",
        minimum=0,
        maximum=MAX_RETRY_DELAY_SECONDS,
    )
    now = now or timezone.now()
    job = WorkflowJob.objects.select_for_update().get(pk=job_id)
    if job.status != WorkflowJob.Status.RUNNING:
        raise WorkflowConflict("Only a running job can fail.")
    _validate_running_lease(job, actor, now)
    previous = job.status
    job.failure_reason_code = reason_code
    job.failure_message = message
    job.lease_owner = ""
    job.leased_until = None
    if retryable and job.attempts < job.max_attempts:
        job.status = WorkflowJob.Status.PENDING
        job.available_at = now + timedelta(seconds=retry_delay_seconds)
        event_reason = "JOB_RETRY_SCHEDULED"
    else:
        job.status = WorkflowJob.Status.FAILED
        job.finished_at = now
        event_reason = "JOB_FAILED_TERMINAL"
    _save_job(job)
    _job_event(
        job,
        actor=actor,
        previous_status=previous,
        new_status=job.status,
        reason_code=event_reason,
    )
    return job


@transaction.atomic
def cancel_job(*, actor: WorkflowActorContext, job_id: int) -> WorkflowJob:
    job_id = _positive_int(job_id, "job identifier")
    job = WorkflowJob.objects.select_for_update().select_related(
        "workflow__generation__chapter__course"
    ).get(pk=job_id)
    _require_course(actor, job.workflow, CAP_QUEUE_CANCEL)
    if job.status == WorkflowJob.Status.CANCELLED:
        return job
    if job.status != WorkflowJob.Status.PENDING:
        raise WorkflowConflict("Only a pending job can be cancelled.")
    previous = job.status
    job.status = WorkflowJob.Status.CANCELLED
    job.finished_at = timezone.now()
    _save_job(job)
    _job_event(
        job,
        actor=actor,
        previous_status=previous,
        new_status=job.status,
        reason_code="JOB_CANCELLED",
    )
    return job
