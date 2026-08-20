from __future__ import annotations

import hashlib
import os
import re
import secrets
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import transaction

from .models import (
    LectureWorkflow,
    RecordingCompletion,
    RecordingCompletionItem,
    RecordingSelection,
    RecordingSelectionEvent,
    RecordingTake,
    SlideDraft,
)
from .workflow import (
    ACTOR_TEACHER,
    CAP_TEACHER_APPROVAL,
    WorkflowActorContext,
    complete_teacher_recording_workflow,
    open_teacher_recording_workflow,
    recording_approval_fingerprint,
)


ALLOWED_MEDIA = {
    "audio/webm": {".webm"},
    "audio/ogg": {".ogg", ".opus"},
    "audio/mp4": {".m4a", ".mp4"},
    "audio/wav": {".wav"},
    "audio/x-wav": {".wav"},
}
SAFE_FILENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._ -]{0,199}")
MIN_AUDIO_BYTES = 16


def _positive_int(value, field: str, *, maximum: int | None = None) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"Invalid {field}.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Invalid {field}.") from exc
    if parsed < 1 or (maximum is not None and parsed > maximum):
        raise ValidationError(f"Invalid {field}.")
    return parsed


def _require_teacher(actor: WorkflowActorContext, workflow: LectureWorkflow) -> None:
    course = workflow.generation.chapter.course
    if (
        not isinstance(actor, WorkflowActorContext)
        or actor.actor_type != ACTOR_TEACHER
        or not actor.has(CAP_TEACHER_APPROVAL)
        or course.pk not in actor.permitted_course_ids
        or actor.internal_actor_id != course.teacher_id
        or actor.internal_actor_id != workflow.generation.requested_by_id
    ):
        raise PermissionDenied("Recording is unavailable for this teacher.")


def recordings_visible_to(actor: WorkflowActorContext):
    if not isinstance(actor, WorkflowActorContext) or actor.actor_type != ACTOR_TEACHER:
        return LectureWorkflow.objects.none()
    return LectureWorkflow.objects.filter(
        generation__requested_by_id=actor.internal_actor_id,
        generation__chapter__course__teacher_id=actor.internal_actor_id,
        generation__chapter__course_id__in=actor.permitted_course_ids,
    ).select_related("generation__chapter__course")


def _eligible_slide(workflow: LectureWorkflow, slide: SlideDraft, expected_revision_id: int):
    if workflow.state != LectureWorkflow.State.RECORDING_PENDING:
        raise ValidationError("Recording is not available in the current workflow state.")
    recording_approval_fingerprint(workflow, lock=True)
    if slide.generation_id != workflow.generation_id:
        raise PermissionDenied("Slide is unavailable for this recording.")
    expected_revision_id = _positive_int(expected_revision_id, "slide revision")
    revision = slide.approved_revision
    if (
        revision is None
        or revision.pk != expected_revision_id
        or revision.version != slide.current_version
        or revision.slide_id != slide.pk
    ):
        raise RecordingConflict("The slide approval changed. Reload before recording.")
    try:
        narration = revision.canonical_narration
    except ObjectDoesNotExist as exc:
        raise ValidationError("Current canonical narration is unavailable.") from exc
    return revision, narration


class RecordingConflict(ValidationError):
    pass


def _validate_upload(upload, *, duration_ms, filename: str, media_type: str):
    max_bytes = int(settings.RECORDING_MAX_UPLOAD_BYTES)
    max_duration = int(settings.RECORDING_MAX_DURATION_MS)
    duration_ms = _positive_int(duration_ms, "recording duration", maximum=max_duration)
    if duration_ms < int(settings.RECORDING_MIN_DURATION_MS):
        raise ValidationError("Recording duration is outside the allowed range.")
    if not isinstance(filename, str) or not SAFE_FILENAME.fullmatch(filename) or filename in {".", ".."}:
        raise ValidationError("Invalid recording filename.")
    extension = Path(filename).suffix.lower()
    if media_type not in ALLOWED_MEDIA or extension not in ALLOWED_MEDIA[media_type]:
        raise ValidationError("Unsupported recording format.")
    declared_size = getattr(upload, "size", None)
    if (
        isinstance(declared_size, bool)
        or not isinstance(declared_size, int)
        or declared_size < MIN_AUDIO_BYTES
        or declared_size > max_bytes
    ):
        raise ValidationError("Recording size is outside the allowed range.")
    return duration_ms, extension, max_bytes


def _signature_matches(media_type: str, header: bytes) -> bool:
    if media_type == "audio/webm":
        return header.startswith(b"\x1aE\xdf\xa3")
    if media_type == "audio/ogg":
        return header.startswith(b"OggS")
    if media_type in {"audio/wav", "audio/x-wav"}:
        return len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"WAVE"
    return len(header) >= 12 and header[4:8] == b"ftyp"


def _storage_root() -> Path:
    root = Path(settings.RECORDING_STORAGE_ROOT).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _contained(root: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _write_staged(upload, *, max_bytes: int, root: Path):
    staging = root / ".staging"
    staging.mkdir(parents=True, exist_ok=True)
    path = staging / f"upload-{secrets.token_hex(16)}.part"
    digest = hashlib.sha256()
    size = 0
    header = b""
    try:
        with path.open("xb") as handle:
            for chunk in upload.chunks():
                if not isinstance(chunk, bytes):
                    chunk = bytes(chunk)
                size += len(chunk)
                if size > max_bytes:
                    raise ValidationError("Recording size is outside the allowed range.")
                if len(header) < 16:
                    header += chunk[: 16 - len(header)]
                digest.update(chunk)
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        if size < MIN_AUDIO_BYTES or size != upload.size:
            raise ValidationError("Recording upload was interrupted.")
        return path, size, digest.hexdigest(), header
    except Exception:
        if path.exists():
            path.unlink()
        raise


def _promote_stage(stage: Path, *, root: Path, storage_key: str) -> Path:
    relative = PurePosixPath(storage_key)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValidationError("Invalid recording storage reference.")
    target = root.joinpath(*relative.parts)
    if not _contained(root, target):
        raise ValidationError("Invalid recording storage reference.")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValidationError("Recording storage collision.")
    os.link(stage, target)
    stage.unlink()
    return target


@transaction.atomic
def open_recording(*, actor: WorkflowActorContext, workflow_id: int, expected_version: int):
    workflow = LectureWorkflow.objects.select_for_update().select_related(
        "generation__chapter__course"
    ).get(pk=_positive_int(workflow_id, "workflow identifier"))
    _require_teacher(actor, workflow)
    return open_teacher_recording_workflow(
        actor=actor,
        workflow_id=workflow.pk,
        expected_version=_positive_int(expected_version, "workflow version"),
        idempotency_key=f"recording-open:v{expected_version}",
    )


def create_take(
    *,
    actor: WorkflowActorContext,
    workflow_id: int,
    slide_id: int,
    expected_revision_id: int,
    upload,
    duration_ms,
    filename: str,
    media_type: str,
) -> RecordingTake:
    stage = None
    promoted = None
    try:
        with transaction.atomic():
            workflow = LectureWorkflow.objects.select_for_update().select_related(
                "generation__chapter__course"
            ).get(pk=_positive_int(workflow_id, "workflow identifier"))
            _require_teacher(actor, workflow)
            slide = SlideDraft.objects.select_for_update().select_related(
                "approved_revision__canonical_narration"
            ).get(pk=_positive_int(slide_id, "slide identifier"))
            revision, narration = _eligible_slide(workflow, slide, expected_revision_id)
            duration_ms, extension, max_bytes = _validate_upload(
                upload, duration_ms=duration_ms, filename=filename, media_type=media_type
            )
            root = _storage_root()
            stage, byte_size, sha256, header = _write_staged(
                upload, max_bytes=max_bytes, root=root
            )
            if not _signature_matches(media_type, header):
                raise ValidationError("Recording content does not match its declared format.")
            take_number = (
                RecordingTake.objects.filter(workflow=workflow, slide_revision=revision).count() + 1
            )
            storage_key = (
                f"workflow-{workflow.pk}/slide-{slide.pk}/"
                f"revision-{revision.pk}-take-{take_number}-{secrets.token_hex(12)}{extension}"
            )
            take = RecordingTake.objects.create(
                workflow=workflow,
                slide_revision=revision,
                canonical_narration=narration,
                take_number=take_number,
                storage_key=storage_key,
                original_name=filename,
                extension=extension,
                media_type=media_type,
                byte_size=byte_size,
                duration_ms=duration_ms,
                sha256=sha256,
                recorded_by_id=actor.internal_actor_id,
            )
            promoted = _promote_stage(stage, root=root, storage_key=storage_key)
            select_take(
                actor=actor,
                workflow_id=workflow.pk,
                slide_id=slide.pk,
                take_id=take.pk,
                expected_revision_id=revision.pk,
            )
        return take
    except Exception:
        # A promoted file belongs to the take transaction until its database
        # commit succeeds. Remove only that exact operation-owned target if the
        # transaction or automatic selection fails.
        if promoted is not None and promoted.is_file():
            promoted.unlink()
        raise
    finally:
        if stage is not None and stage.exists():
            stage.unlink()


@transaction.atomic
def select_take(
    *, actor: WorkflowActorContext, workflow_id: int, slide_id: int, take_id: int, expected_revision_id: int
) -> RecordingSelection:
    workflow = LectureWorkflow.objects.select_for_update().select_related(
        "generation__chapter__course"
    ).get(pk=_positive_int(workflow_id, "workflow identifier"))
    _require_teacher(actor, workflow)
    slide = SlideDraft.objects.select_for_update().select_related(
        "approved_revision__canonical_narration"
    ).get(pk=_positive_int(slide_id, "slide identifier"))
    revision, _ = _eligible_slide(workflow, slide, expected_revision_id)
    take = RecordingTake.objects.filter(
        pk=_positive_int(take_id, "recording take"),
        workflow=workflow,
        slide_revision=revision,
        recorded_by_id=actor.internal_actor_id,
    ).first()
    if take is None:
        raise PermissionDenied("Recording take is unavailable for this slide.")
    selection = RecordingSelection.objects.select_for_update().filter(
        workflow=workflow, slide=slide
    ).first()
    if selection is None:
        selection = RecordingSelection.objects.create(
            workflow=workflow,
            slide=slide,
            current_take=take,
            selected_by_id=actor.internal_actor_id,
        )
    else:
        selection.current_take = take
        selection.version += 1
        selection.selected_by_id = actor.internal_actor_id
        selection._domain_service_write = True
        try:
            selection.save()
        finally:
            del selection._domain_service_write
    RecordingSelectionEvent.objects.create(
        selection=selection,
        version=selection.version,
        take=take,
        selected_by_id=actor.internal_actor_id,
    )
    return selection


@transaction.atomic
def complete_recording(
    *, actor: WorkflowActorContext, workflow_id: int, expected_version: int, expected_revision_ids
) -> RecordingCompletion:
    workflow = LectureWorkflow.objects.select_for_update().select_related(
        "generation__chapter__course"
    ).get(pk=_positive_int(workflow_id, "workflow identifier"))
    _require_teacher(actor, workflow)
    expected_version = _positive_int(expected_version, "workflow version")
    if workflow.version != expected_version:
        raise RecordingConflict("The recording workflow changed. Reload before completing.")
    fingerprint = recording_approval_fingerprint(workflow, lock=True)
    slides = list(
        workflow.generation.slides.select_for_update().select_related("approved_revision").order_by("position")
    )
    if (
        not isinstance(expected_revision_ids, list)
        or any(isinstance(value, bool) or not isinstance(value, int) for value in expected_revision_ids)
        or expected_revision_ids != [slide.approved_revision_id for slide in slides]
    ):
        raise RecordingConflict("The slide approval changed. Reload before completing.")
    selections = {
        item.slide_id: item
        for item in RecordingSelection.objects.select_for_update().select_related(
            "current_take__slide_revision"
        ).filter(workflow=workflow)
    }
    selected = []
    for slide in slides:
        selection = selections.get(slide.pk)
        if (
            selection is None
            or selection.current_take.workflow_id != workflow.pk
            or selection.current_take.slide_revision_id != slide.approved_revision_id
            or selection.current_take.recorded_by_id != actor.internal_actor_id
        ):
            raise ValidationError("Select a current recording take for every approved slide.")
        selected.append((slide, selection.current_take))
    encoded = ":".join(
        [str(workflow.pk), fingerprint, *[f"{slide.approved_revision_id}:{take.pk}:{take.sha256}" for slide, take in selected]]
    ).encode("ascii")
    reference = f"recording:bundle-{hashlib.sha256(encoded).hexdigest()[:40]}"
    completion = RecordingCompletion.objects.create(
        workflow=workflow,
        reference=reference,
        slide_approval_fingerprint=fingerprint,
        completed_by_id=actor.internal_actor_id,
    )
    for slide, take in selected:
        RecordingCompletionItem.objects.create(
            completion=completion,
            position=slide.position,
            slide_revision=slide.approved_revision,
            take=take,
        )
    complete_teacher_recording_workflow(
        actor=actor,
        workflow_id=workflow.pk,
        expected_version=workflow.version,
        idempotency_key=f"recording-complete:{completion.pk}",
        recording_reference=reference,
        expected_fingerprint=fingerprint,
    )
    return completion


def recording_path(take: RecordingTake) -> Path:
    root = _storage_root()
    relative = PurePosixPath(take.storage_key)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValidationError("Recording media is unavailable.")
    path = root.joinpath(*relative.parts)
    if not _contained(root, path) or not path.is_file():
        raise ValidationError("Recording media is unavailable.")
    return path
