from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import shutil
import subprocess
import threading
import time
import zipfile
from xml.sax.saxutils import escape
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    AdminFinalVideoApproval,
    Course,
    LectureWorkflow,
    RecordingCompletion,
    SpokenContentEditApproval,
    TeacherVideoReview,
    VideoEditDecision,
    VideoExportPackage,
    VideoRenderAppliedEdit,
    VideoRenderInput,
    VideoRenderInputItem,
    VideoRenderRecovery,
    VideoRenderVersion,
    VideoReviewSubmission,
    WorkflowJob,
)
from .recording import recording_path
from .workflow import (
    ACTOR_ADMINISTRATOR,
    ACTOR_TEACHER,
    WorkflowActorContext,
    claim_job,
    complete_job,
    fail_job,
    recording_approval_fingerprint,
    submit_job,
    system_worker_context,
    transition_workflow,
)


HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX_COLOR = re.compile(r"#[0-9A-Fa-f]{6}\Z")
MAX_PROCESS_OUTPUT = 1_000_000


class VideoConflict(ValidationError):
    pass


class UnsupportedRenderEnvironment(ValidationError):
    pass


def _positive(value, field: str, *, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValidationError(f"Invalid {field}.")
    if maximum is not None and value > maximum:
        raise ValidationError(f"Invalid {field}.")
    return value


def _exact(value, fields: set[str], field: str = "edit decision") -> dict:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValidationError(f"Invalid {field}.")
    return value


def _canonical(value) -> bytes:
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    except (TypeError, ValueError) as exc:
        raise ValidationError("Invalid bounded video data.") from exc
    if len(encoded) > settings.VIDEO_RENDER_MAX_REQUEST_BYTES:
        raise ValidationError("Video data exceeds the safe limit.")
    return encoded


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            size += len(chunk)
            if size > settings.VIDEO_RENDER_MAX_OUTPUT_BYTES:
                raise ValidationError("Local video artifact exceeds the safe limit.")
            digest.update(chunk)
    return digest.hexdigest(), size


def _require_admin(actor: WorkflowActorContext, workflow: LectureWorkflow) -> None:
    if (
        actor.actor_type != ACTOR_ADMINISTRATOR
        or workflow.generation.chapter.course_id not in actor.permitted_course_ids
    ):
        raise PermissionDenied("Video administration is not authorized.")


def _require_teacher(actor: WorkflowActorContext, workflow: LectureWorkflow) -> None:
    course = workflow.generation.chapter.course
    if (
        actor.actor_type != ACTOR_TEACHER
        or actor.internal_actor_id != course.teacher_id
        or actor.internal_actor_id != workflow.generation.requested_by_id
        or course.pk not in actor.permitted_course_ids
    ):
        raise PermissionDenied("Video review is unavailable for this teacher.")


def video_workflows_visible_to(actor: WorkflowActorContext):
    rows = LectureWorkflow.objects.filter(
        generation__chapter__course_id__in=actor.permitted_course_ids
    )
    if actor.actor_type == ACTOR_ADMINISTRATOR:
        return rows
    if actor.actor_type == ACTOR_TEACHER:
        return rows.filter(
            generation__requested_by_id=actor.internal_actor_id,
            generation__chapter__course__teacher_id=actor.internal_actor_id,
        )
    return LectureWorkflow.objects.none()


def _contained(root: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _root(setting_name: str) -> Path:
    root = Path(getattr(settings, setting_name)).resolve()
    data_root = (Path(settings.BASE_DIR) / "data").resolve()
    if not _contained(data_root, root):
        raise UnsupportedRenderEnvironment("Video storage must remain in project-local ignored data.")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _storage_path(root: Path, key: str, *, must_exist: bool = False) -> Path:
    if not isinstance(key, str):
        raise ValidationError("Invalid video storage reference.")
    relative = PurePosixPath(key)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValidationError("Invalid video storage reference.")
    path = root.joinpath(*relative.parts)
    if not _contained(root, path) or (must_exist and not path.is_file()):
        raise ValidationError("Video artifact is unavailable.")
    return path


def render_video_path(render: VideoRenderVersion) -> Path:
    return _storage_path(_root("VIDEO_STORAGE_ROOT"), render.video_storage_key, must_exist=True)


def _completion_for(workflow: LectureWorkflow) -> RecordingCompletion:
    completion = (
        RecordingCompletion.objects.filter(
            workflow=workflow, reference=workflow.recording_reference
        )
        .order_by("-pk")
        .first()
    )
    if completion is None:
        raise ValidationError("The immutable recording completion is unavailable.")
    return completion


def _snapshot_input(workflow: LectureWorkflow, actor: WorkflowActorContext) -> VideoRenderInput:
    fingerprint = recording_approval_fingerprint(workflow, lock=True)
    if fingerprint != workflow.slide_approval_fingerprint:
        raise VideoConflict("The slide approval is stale.")
    completion = _completion_for(workflow)
    if completion.slide_approval_fingerprint != fingerprint:
        raise VideoConflict("The recording completion is stale.")
    completion_items = list(
        completion.items.select_related(
            "slide_revision__slide",
            "slide_revision__canonical_narration",
            "take__canonical_narration",
        ).prefetch_related("slide_revision__claims")
    )
    slides = list(workflow.generation.slides.select_related("approved_revision").order_by("position"))
    if not slides or len(completion_items) != len(slides):
        raise ValidationError("Recording inputs do not cover every approved slide.")
    snapshots = []
    for slide, item in zip(slides, completion_items, strict=True):
        revision = slide.approved_revision
        if (
            revision is None
            or item.position != slide.position
            or item.slide_revision_id != revision.pk
            or item.take.slide_revision_id != revision.pk
            or item.take.canonical_narration_id != revision.canonical_narration.pk
        ):
            raise VideoConflict("The recording selection is stale.")
        path = recording_path(item.take)
        digest, size = _file_sha(path)
        if digest != item.take.sha256 or size != item.take.byte_size:
            raise ValidationError("A source recording failed its integrity check.")
        snapshots.append(
            {
                "position": item.position,
                "revision_id": revision.pk,
                "narration_id": revision.canonical_narration.pk,
                "take_id": item.take_id,
                "take_sha256": item.take.sha256,
                "duration_ms": item.take.duration_ms,
                "title": revision.title,
                "claims": [claim.text for claim in revision.claims.order_by("position")],
                "narration": revision.canonical_narration.text,
                "narration_sha256": revision.canonical_narration.text_sha256,
                "storage_key": item.take.storage_key,
            }
        )
    encoded = _canonical(
        {
            "workflow_id": workflow.pk,
            "recording_reference": completion.reference,
            "slide_approval_fingerprint": fingerprint,
            "items": snapshots,
        }
    )
    digest = _sha(encoded)
    render_input = VideoRenderInput.objects.filter(input_sha256=digest).first()
    if render_input is not None:
        return render_input
    render_input = VideoRenderInput.objects.create(
        workflow=workflow,
        recording_completion=completion,
        workflow_version=workflow.version,
        slide_approval_fingerprint=fingerprint,
        recording_reference=completion.reference,
        input_sha256=digest,
        created_by_id=actor.internal_actor_id,
    )
    for snapshot in snapshots:
        VideoRenderInputItem.objects.create(
            render_input=render_input,
            position=snapshot["position"],
            slide_revision_id=snapshot["revision_id"],
            canonical_narration_id=snapshot["narration_id"],
            take_id=snapshot["take_id"],
            title_snapshot=snapshot["title"],
            claims_snapshot=snapshot["claims"],
            narration_snapshot=snapshot["narration"],
            narration_sha256=snapshot["narration_sha256"],
            take_sha256=snapshot["take_sha256"],
            take_duration_ms=snapshot["duration_ms"],
            take_storage_key=snapshot["storage_key"],
        )
    return render_input


def _input_is_current(render_input: VideoRenderInput, workflow: LectureWorkflow) -> None:
    fingerprint = recording_approval_fingerprint(workflow, lock=True)
    if (
        fingerprint != render_input.slide_approval_fingerprint
        or fingerprint != workflow.slide_approval_fingerprint
        or workflow.recording_reference != render_input.recording_reference
    ):
        raise VideoConflict("Render inputs are stale.")
    completion = _completion_for(workflow)
    if completion.pk != render_input.recording_completion_id:
        raise VideoConflict("The recording completion changed.")
    items = list(
        render_input.items.select_related(
            "take", "slide_revision__canonical_narration", "canonical_narration"
        ).prefetch_related("slide_revision__claims").order_by("position")
    )
    completion_items = list(completion.items.order_by("position"))
    if [(x.position, x.slide_revision_id, x.take_id) for x in completion_items] != [
        (x.position, x.slide_revision_id, x.take_id) for x in items
    ]:
        raise VideoConflict("The recording selection changed.")
    for item in items:
        revision = item.slide_revision
        narration = revision.canonical_narration
        claims = [claim.text for claim in revision.claims.order_by("position")]
        if (
            item.canonical_narration_id != narration.pk
            or item.take.slide_revision_id != revision.pk
            or item.take.canonical_narration_id != narration.pk
            or item.title_snapshot != revision.title
            or item.claims_snapshot != claims
            or item.narration_snapshot != narration.text
            or item.narration_sha256 != narration.text_sha256
            or _sha(item.narration_snapshot.encode("utf-8")) != item.narration_sha256
            or item.take_storage_key != item.take.storage_key
            or item.take_duration_ms != item.take.duration_ms
        ):
            raise VideoConflict("The approved slide, narration, or selected take changed.")
        digest, size = _file_sha(recording_path(item.take))
        if digest != item.take_sha256 or digest != item.take.sha256 or size != item.take.byte_size:
            raise ValidationError("A source recording failed its integrity check.")


def _new_render(
    *, workflow: LectureWorkflow, render_input: VideoRenderInput, actor: WorkflowActorContext, parent=None
) -> VideoRenderVersion:
    version = workflow.video_render_versions.count() + 1
    reference_digest = _sha(
        f"{workflow.pk}:{version}:{render_input.input_sha256}".encode("ascii")
    )[:40]
    reference = f"video:draft-{reference_digest}"
    base = f"workflow-{workflow.pk}/render-v{version}-{reference_digest}"
    return VideoRenderVersion.objects.create(
        workflow=workflow,
        render_input=render_input,
        version=version,
        parent=parent,
        reference=reference,
        manifest_storage_key=f"{base}/manifest.json",
        video_storage_key=f"{base}/lecture.mp4",
        requested_by_id=actor.internal_actor_id,
    )


@transaction.atomic
def request_initial_render(*, actor: WorkflowActorContext, workflow_id: int) -> VideoRenderVersion:
    workflow = LectureWorkflow.objects.select_for_update().select_related(
        "generation__chapter__course"
    ).get(pk=_positive(workflow_id, "workflow identifier"))
    _require_admin(actor, workflow)
    if workflow.state != LectureWorkflow.State.RECORDING_READY:
        raise VideoConflict("A new initial render is unavailable in the current workflow state.")
    if workflow.video_render_versions.exists():
        raise VideoConflict("The initial render already exists.")
    return _new_render(workflow=workflow, render_input=_snapshot_input(workflow, actor), actor=actor)


def _validate_edit_payload(decision_type: str, payload: dict, base: VideoRenderVersion) -> dict:
    if decision_type == VideoEditDecision.DecisionType.BRANDING:
        payload = _exact(payload, {"accent_color", "institution_name"})
        if not HEX_COLOR.fullmatch(payload["accent_color"] or ""):
            raise ValidationError("Invalid branding edit.")
        name = payload["institution_name"]
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
            raise ValidationError("Invalid branding edit.")
        return {"accent_color": payload["accent_color"].upper(), "institution_name": name.strip()}
    if decision_type == VideoEditDecision.DecisionType.CAPTION_LAYOUT:
        payload = _exact(payload, {"position", "font_scale"})
        if payload["position"] not in {"top", "bottom"}:
            raise ValidationError("Invalid caption layout edit.")
        scale = _positive(payload["font_scale"], "caption font scale", maximum=130)
        if scale < 80:
            raise ValidationError("Invalid caption layout edit.")
        return {"position": payload["position"], "font_scale": scale}
    if decision_type == VideoEditDecision.DecisionType.TRANSITION_TIMING:
        payload = _exact(payload, {"transition_ms", "hold_after_ms"})
        transition_ms = payload["transition_ms"]
        hold_after_ms = payload["hold_after_ms"]
        if (
            isinstance(transition_ms, bool)
            or not isinstance(transition_ms, int)
            or not 0 <= transition_ms <= 1000
            or isinstance(hold_after_ms, bool)
            or not isinstance(hold_after_ms, int)
            or not 0 <= hold_after_ms <= 5000
        ):
            raise ValidationError("Invalid transition timing edit.")
        return payload
    if decision_type == VideoEditDecision.DecisionType.SPOKEN_CONTENT_REMOVAL:
        payload = _exact(
            payload,
            {
                "slide_position",
                "start_ms",
                "end_ms",
                "transcript_excerpt",
                "narration_sha256",
                "reason",
            },
        )
        position = _positive(payload["slide_position"], "slide position", maximum=100)
        item = base.render_input.items.filter(position=position).first()
        if item is None:
            raise ValidationError("Invalid spoken-content evidence.")
        start_ms, end_ms = payload["start_ms"], payload["end_ms"]
        if (
            isinstance(start_ms, bool)
            or not isinstance(start_ms, int)
            or start_ms < 0
            or isinstance(end_ms, bool)
            or not isinstance(end_ms, int)
            or end_ms <= start_ms
            or end_ms > item.take_duration_ms
        ):
            raise ValidationError("Invalid spoken-content timestamps.")
        excerpt = payload["transcript_excerpt"]
        reason = payload["reason"]
        if (
            not isinstance(excerpt, str)
            or not excerpt.strip()
            or len(excerpt.strip()) > 500
            or item.narration_snapshot.count(excerpt.strip()) != 1
            or payload["narration_sha256"] != item.narration_sha256
            or not isinstance(reason, str)
            or not reason.strip()
            or len(reason.strip()) > 300
        ):
            raise ValidationError("Spoken-content removal requires exact transcript evidence.")
        return {
            **payload,
            "transcript_excerpt": excerpt.strip(),
            "reason": reason.strip(),
        }
    raise ValidationError("Unsupported video edit decision.")


def _copy_edits(base: VideoRenderVersion, render: VideoRenderVersion, decision) -> None:
    existing = list(base.applied_edits.select_related("decision").order_by("position"))
    for applied in existing:
        VideoRenderAppliedEdit.objects.create(
            render=render, decision=applied.decision, position=applied.position
        )
    VideoRenderAppliedEdit.objects.create(render=render, decision=decision, position=len(existing) + 1)


def _derive_render(
    *, actor: WorkflowActorContext, workflow: LectureWorkflow, base: VideoRenderVersion, decision
) -> VideoRenderVersion:
    if decision.decision_type == VideoEditDecision.DecisionType.SPOKEN_CONTENT_REMOVAL:
        try:
            approval = decision.spoken_approval
        except ObjectDoesNotExist as exc:
            raise ValidationError("Teacher approval is required for spoken-content removal.") from exc
        if approval.approved_by_id != workflow.generation.chapter.course.teacher_id:
            raise ValidationError("Teacher approval is invalid for this course.")
    render = _new_render(
        workflow=workflow, render_input=base.render_input, actor=actor, parent=base
    )
    _copy_edits(base, render, decision)
    return render


@transaction.atomic
def recover_failed_render(
    *, actor: WorkflowActorContext, workflow_id: int, failed_render_id: int, reason: str
) -> VideoRenderVersion:
    workflow = LectureWorkflow.objects.select_for_update().select_related(
        "generation__chapter__course"
    ).get(pk=_positive(workflow_id, "workflow identifier"))
    _require_admin(actor, workflow)
    if workflow.state != LectureWorkflow.State.DRAFT_VIDEO_PENDING:
        raise VideoConflict("Failed-render recovery is unavailable in the current workflow state.")
    if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 300:
        raise ValidationError("A bounded recovery reason is required.")
    failed = workflow.video_render_versions.select_for_update().select_related(
        "render_input"
    ).filter(
        pk=_positive(failed_render_id, "failed render"),
        status=VideoRenderVersion.Status.FAILED,
    ).first()
    if failed is None:
        raise VideoConflict("Only an immutable failed render can be recovered.")
    latest = workflow.video_render_versions.order_by("-version").first()
    if latest is None or latest.pk != failed.pk:
        raise VideoConflict("Only the latest failed render can be recovered.")
    if VideoRenderRecovery.objects.filter(failed_render=failed).exists():
        raise VideoConflict("Recovery was already requested for this failed render.")
    _input_is_current(failed.render_input, workflow)
    replacement = _new_render(
        workflow=workflow, render_input=failed.render_input, actor=actor, parent=failed
    )
    for applied in failed.applied_edits.select_related("decision").order_by("position"):
        VideoRenderAppliedEdit.objects.create(
            render=replacement, decision=applied.decision, position=applied.position
        )
    VideoRenderRecovery.objects.create(
        workflow=workflow,
        failed_render=failed,
        replacement_render=replacement,
        requested_by_id=actor.internal_actor_id,
        reason=reason.strip(),
    )
    return replacement


@transaction.atomic
def create_edit_decision(
    *, actor: WorkflowActorContext, workflow_id: int, base_render_id: int, decision_type: str, payload
):
    workflow = LectureWorkflow.objects.select_for_update().select_related(
        "generation__chapter__course"
    ).get(pk=_positive(workflow_id, "workflow identifier"))
    _require_admin(actor, workflow)
    if workflow.state not in {
        LectureWorkflow.State.DRAFT_VIDEO_PENDING,
        LectureWorkflow.State.TEACHER_VIDEO_REVISION_REQUESTED,
    }:
        raise VideoConflict("Video edits are unavailable in the current workflow state.")
    base = workflow.video_render_versions.select_for_update().filter(
        pk=_positive(base_render_id, "base render"), status=VideoRenderVersion.Status.SUCCEEDED
    ).first()
    latest = workflow.video_render_versions.order_by("-version").first()
    if base is None or latest is None or base.pk != latest.pk:
        raise VideoConflict("Edits must derive from the latest successful render.")
    _input_is_current(base.render_input, workflow)
    clean = _validate_edit_payload(decision_type, payload, base)
    decision = VideoEditDecision.objects.create(
        workflow=workflow,
        base_render=base,
        decision_type=decision_type,
        payload=clean,
        payload_sha256=_sha(_canonical(clean)),
        decided_by_id=actor.internal_actor_id,
    )
    render = None
    if decision_type != VideoEditDecision.DecisionType.SPOKEN_CONTENT_REMOVAL:
        render = _derive_render(actor=actor, workflow=workflow, base=base, decision=decision)
    return decision, render


@transaction.atomic
def approve_spoken_edit(*, actor: WorkflowActorContext, decision_id: int):
    decision = VideoEditDecision.objects.select_for_update().select_related(
        "workflow__generation__chapter__course", "base_render__render_input"
    ).get(pk=_positive(decision_id, "edit decision"))
    workflow = decision.workflow
    _require_teacher(actor, workflow)
    if decision.decision_type != VideoEditDecision.DecisionType.SPOKEN_CONTENT_REMOVAL:
        raise ValidationError("This edit does not accept spoken-content approval.")
    if hasattr(decision, "spoken_approval"):
        raise VideoConflict("The spoken-content edit is already approved.")
    latest = workflow.video_render_versions.order_by("-version").first()
    if latest is None or latest.pk != decision.base_render_id:
        raise VideoConflict("The spoken-content edit belongs to a stale render.")
    SpokenContentEditApproval.objects.create(
        decision=decision, approved_by_id=actor.internal_actor_id
    )
    admin_actor = WorkflowActorContext(
        ACTOR_ADMINISTRATOR,
        f"approved-edit:{decision.pk}",
        decision.decided_by_id,
        frozenset({workflow.generation.chapter.course_id}),
        frozenset(),
    )
    return _derive_render(actor=admin_actor, workflow=workflow, base=latest, decision=decision)


def render_environment_supported() -> bool:
    host = settings.VIDEO_RENDER_EXECUTION_HOST
    try:
        loopback = host == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = False
    return bool(
        settings.VIDEO_RENDER_ADAPTER_ENABLED
        and settings.VIDEO_RENDER_EVALUATION_ACK
        and settings.VIDEO_RENDER_DEPLOYMENT_MODE == "local-evaluation"
        and loopback
        and not settings.VIDEO_RENDER_RAILWAY_ENVIRONMENT
    )


def _trusted_worker(workflow: LectureWorkflow) -> WorkflowActorContext:
    if not render_environment_supported():
        raise UnsupportedRenderEnvironment(
            "The trusted local evaluation render adapter is not enabled."
        )
    return system_worker_context(
        identity_reference="t050-local-render-worker",
        permitted_course_ids=[workflow.generation.chapter.course_id],
    )


def _save_render(render: VideoRenderVersion, **fields) -> None:
    for name, value in fields.items():
        setattr(render, name, value)
    render._domain_service_write = True
    try:
        render.save(update_fields=(*fields.keys(),))
    finally:
        del render._domain_service_write


def _render_config(render: VideoRenderVersion) -> dict:
    config = {
        "accentColor": "#0057B8",
        "institutionName": "Unique Group of Institutions",
        "captionPosition": "bottom",
        "captionFontScale": 100,
        "transitionMs": 300,
        "holdAfterMs": 0,
        "cuts": {},
    }
    for applied in render.applied_edits.select_related("decision").order_by("position"):
        decision, payload = applied.decision, applied.decision.payload
        if decision.decision_type == VideoEditDecision.DecisionType.BRANDING:
            config["accentColor"] = payload["accent_color"]
            config["institutionName"] = payload["institution_name"]
        elif decision.decision_type == VideoEditDecision.DecisionType.CAPTION_LAYOUT:
            config["captionPosition"] = payload["position"]
            config["captionFontScale"] = payload["font_scale"]
        elif decision.decision_type == VideoEditDecision.DecisionType.TRANSITION_TIMING:
            config["transitionMs"] = payload["transition_ms"]
            config["holdAfterMs"] = payload["hold_after_ms"]
        else:
            key = str(payload["slide_position"])
            config["cuts"].setdefault(key, []).append(
                {
                    "startMs": payload["start_ms"],
                    "endMs": payload["end_ms"],
                    "transcriptExcerpt": payload["transcript_excerpt"],
                    "evidenceSha256": payload["narration_sha256"],
                }
            )
    for cuts in config["cuts"].values():
        cuts.sort(key=lambda cut: cut["startMs"])
        if any(left["endMs"] > right["startMs"] for left, right in zip(cuts, cuts[1:])):
            raise ValidationError("Spoken-content edit timestamps overlap.")
    return config


def _build_manifest(render: VideoRenderVersion) -> tuple[Path, Path]:
    root = _root("VIDEO_STORAGE_ROOT")
    manifest_path = _storage_path(root, render.manifest_storage_key)
    output_path = _storage_path(root, render.video_storage_key)
    if manifest_path.exists() or output_path.exists() or output_path.with_suffix(".mp4.part").exists():
        raise ValidationError("Immutable render destination already exists.")
    manifest_path.parent.mkdir(parents=True, exist_ok=False)
    public_dir = manifest_path.parent / "public"
    audio_dir = public_dir / "audio"
    audio_dir.mkdir(parents=True)
    slides = []
    config = _render_config(render)
    timeline_cursor = 0
    fps = 30
    hold_frames = _ms_to_frames(config["holdAfterMs"], fps)
    for item in render.render_input.items.select_related("take").order_by("position"):
        extension = item.take.extension.lower()
        target = audio_dir / f"slide-{item.position}{extension}"
        source = recording_path(item.take)
        shutil.copyfile(source, target)
        copied_sha, copied_size = _file_sha(target)
        if copied_sha != item.take_sha256 or copied_size != item.take.byte_size:
            raise ValidationError("Staged recording failed its integrity check.")
        caption = item.narration_snapshot
        for cut in config["cuts"].get(str(item.position), []):
            caption = caption.replace(cut["transcriptExcerpt"], "", 1).strip()
        cuts = config["cuts"].get(str(item.position), [])
        intervals = _kept_intervals(item.take_duration_ms, cuts)
        narration_frames = sum(
            max(1, _ms_to_frames(end_ms - start_ms, fps))
            for start_ms, end_ms in intervals
        )
        duration_in_frames = max(1, narration_frames + hold_frames)
        slides.append(
            {
                "position": item.position,
                "title": item.title_snapshot,
                "claims": item.claims_snapshot,
                "caption": caption,
                "audioSrc": f"audio/{target.name}",
                "durationMs": item.take_duration_ms,
                "cuts": cuts,
                "timelineStartFrame": timeline_cursor,
                "narrationFrames": narration_frames,
                "durationInFrames": duration_in_frames,
            }
        )
        timeline_cursor += duration_in_frames
    manifest = {
        "schemaVersion": 1,
        "compositionId": "LectureAssembly",
        "fps": 30,
        "width": 1920,
        "height": 1080,
        "renderReference": render.reference,
        "publicDir": str(public_dir.resolve()),
        "slides": slides,
        "branding": {
            "accentColor": config["accentColor"],
            "institutionName": config["institutionName"],
        },
        "captions": {
            "position": config["captionPosition"],
            "fontScale": config["captionFontScale"],
        },
        "transitionMs": config["transitionMs"],
        "holdAfterMs": config["holdAfterMs"],
        "totalDurationInFrames": timeline_cursor,
    }
    manifest_path.write_bytes(_canonical(manifest))
    return manifest_path, output_path


def _run_bounded(command: list[str], *, cwd: Path, timeout: int) -> None:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={
            **os.environ,
            "REMOTION_TELEMETRY_DISABLED": "1",
            "NO_PROXY": "localhost,127.0.0.1,::1",
        },
        shell=False,
    )
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    overflow = threading.Event()

    def drain(name, pipe):
        try:
            while chunk := pipe.read(16_384):
                remaining = MAX_PROCESS_OUTPUT - len(buffers[name])
                if len(chunk) > remaining:
                    buffers[name].extend(chunk[: max(0, remaining)])
                    overflow.set()
                    return
                buffers[name].extend(chunk)
        finally:
            pipe.close()

    readers = [
        threading.Thread(target=drain, args=(name, pipe), daemon=True)
        for name, pipe in (("stdout", process.stdout), ("stderr", process.stderr))
    ]
    for reader in readers:
        reader.start()
    deadline = time.monotonic() + timeout
    timed_out = False
    while process.poll() is None:
        if overflow.wait(0.05):
            break
        if time.monotonic() >= deadline:
            timed_out = True
            break
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    for reader in readers:
        reader.join(5)
    if any(reader.is_alive() for reader in readers) or overflow.is_set():
        raise RuntimeError("Local renderer output exceeded the safe boundary.")
    if timed_out:
        raise TimeoutError("Local renderer exceeded the safe time limit.")
    if process.returncode:
        raise RuntimeError("Local renderer failed safely.")


def _invoke_adapter(manifest_path: Path, output_path: Path) -> None:
    project = Path(settings.REMOTION_PROJECT_ROOT).resolve()
    expected_project = (Path(settings.BASE_DIR) / "remotion").resolve()
    if project != expected_project:
        raise UnsupportedRenderEnvironment("The Remotion project boundary is invalid.")
    node = shutil.which("node")
    script = project / "scripts" / "render.mjs"
    if not node or not script.is_file():
        raise UnsupportedRenderEnvironment("The trusted local Remotion adapter is unavailable.")
    _run_bounded(
        [node, str(script), str(manifest_path), str(output_path)],
        cwd=project,
        timeout=settings.VIDEO_RENDER_TIMEOUT_SECONDS,
    )


def process_render(render_id: int) -> VideoRenderVersion:
    render = VideoRenderVersion.objects.select_related(
        "workflow__generation__chapter__course", "render_input"
    ).get(pk=_positive(render_id, "render identifier"))
    worker = _trusted_worker(render.workflow)
    if render.status != VideoRenderVersion.Status.PENDING:
        raise VideoConflict("Only a pending render can be processed.")
    workflow = render.workflow
    if workflow.state in {
        LectureWorkflow.State.RECORDING_READY,
        LectureWorkflow.State.TEACHER_VIDEO_REVISION_REQUESTED,
    }:
        transition_workflow(
            actor=worker,
            workflow_id=workflow.pk,
            target_state=LectureWorkflow.State.DRAFT_VIDEO_PENDING,
            reason_code=(
                "VIDEO_RESUBMITTED"
                if workflow.state == LectureWorkflow.State.TEACHER_VIDEO_REVISION_REQUESTED
                else "VIDEO_DRAFT_SCHEDULED"
            ),
            expected_version=workflow.version,
            idempotency_key=f"t050-render-pending:{render.pk}",
        )
        workflow.refresh_from_db()
    if workflow.state != LectureWorkflow.State.DRAFT_VIDEO_PENDING:
        raise VideoConflict("Render processing is unavailable in the current workflow state.")
    try:
        _input_is_current(render.render_input, workflow)
    except VideoConflict:
        _save_render(
            render,
            status=VideoRenderVersion.Status.STALE,
            failure_reason_code="STALE_INPUT",
            completed_at=timezone.now(),
        )
        raise
    _save_render(render, status=VideoRenderVersion.Status.RUNNING, started_at=timezone.now())
    try:
        manifest_path, output_path = _build_manifest(render)
        _invoke_adapter(manifest_path, output_path)
        digest, size = _file_sha(output_path)
        if size < 1:
            raise RuntimeError("Local renderer produced no video.")
        _save_render(
            render,
            status=VideoRenderVersion.Status.SUCCEEDED,
            video_sha256=digest,
            byte_size=size,
            completed_at=timezone.now(),
        )
    except Exception:
        render.refresh_from_db()
        if render.status == VideoRenderVersion.Status.RUNNING:
            _save_render(
                render,
                status=VideoRenderVersion.Status.FAILED,
                failure_reason_code="LOCAL_RENDER_FAILED",
                completed_at=timezone.now(),
            )
        raise
    return render


@transaction.atomic
def submit_for_teacher_review(
    *, actor: WorkflowActorContext, workflow_id: int, render_id: int
) -> VideoReviewSubmission:
    workflow = LectureWorkflow.objects.select_for_update().select_related(
        "generation__chapter__course"
    ).get(pk=_positive(workflow_id, "workflow identifier"))
    _require_admin(actor, workflow)
    if workflow.state != LectureWorkflow.State.DRAFT_VIDEO_PENDING:
        raise VideoConflict("Teacher review submission is unavailable.")
    render = workflow.video_render_versions.select_for_update().filter(
        pk=_positive(render_id, "render identifier"), status=VideoRenderVersion.Status.SUCCEEDED
    ).first()
    latest = workflow.video_render_versions.order_by("-version").first()
    if render is None or latest is None or render.pk != latest.pk:
        raise VideoConflict("Only the latest successful render can enter teacher review.")
    _input_is_current(render.render_input, workflow)
    job = submit_job(
        actor=actor,
        workflow_id=workflow.pk,
        job_type=WorkflowJob.JobType.DRAFT_VIDEO_READINESS,
        payload={"recording_reference": workflow.recording_reference},
        idempotency_key=f"t050-video-review:{render.pk}",
        max_attempts=1,
    )
    return VideoReviewSubmission.objects.create(
        render=render, job=job, submitted_by_id=actor.internal_actor_id
    )


def _process_review_job(job: WorkflowJob, worker: WorkflowActorContext) -> None:
    submission = VideoReviewSubmission.objects.select_related("render__render_input").filter(
        job=job
    ).first()
    if submission is None:
        fail_job(
            actor=worker,
            job_id=job.pk,
            reason_code="INVALID_INPUT",
            message="No trusted T050 review submission matches this job.",
            retryable=False,
        )
        return
    workflow = job.workflow
    render = submission.render
    try:
        latest = workflow.video_render_versions.order_by("-version").first()
        if latest is None or latest.pk != render.pk or render.status != VideoRenderVersion.Status.SUCCEEDED:
            raise VideoConflict("The submitted render is stale.")
        _input_is_current(render.render_input, workflow)
        complete_job(
            actor=worker,
            job_id=job.pk,
            completion_idempotency_key=f"t050-video-ready:{render.pk}",
            result={
                "job_id": job.pk,
                "job_type": job.job_type,
                "workflow_id": workflow.pk,
                "workflow_version": job.workflow_version,
                "draft_video_reference": render.reference,
            },
        )
        transition_workflow(
            actor=worker,
            workflow_id=workflow.pk,
            target_state=LectureWorkflow.State.DRAFT_VIDEO_READY,
            reason_code="VIDEO_REFERENCE_READY",
            expected_version=workflow.version,
            idempotency_key=f"t050-video-ready-transition:{render.pk}",
            job_id=job.pk,
            artifact_reference=render.reference,
        )
    except Exception:
        job.refresh_from_db()
        if job.status == WorkflowJob.Status.RUNNING:
            fail_job(
                actor=worker,
                job_id=job.pk,
                reason_code="INVALID_INPUT",
                message="The T050 review evidence became stale or invalid.",
                retryable=False,
            )
        raise


@transaction.atomic
def record_teacher_video_review(
    *, actor: WorkflowActorContext, workflow_id: int, render_id: int, decision: str, notes: str
) -> TeacherVideoReview:
    workflow = LectureWorkflow.objects.select_for_update().select_related(
        "generation__chapter__course"
    ).get(pk=_positive(workflow_id, "workflow identifier"))
    _require_teacher(actor, workflow)
    if decision not in TeacherVideoReview.Decision.values:
        raise ValidationError("Invalid teacher video decision.")
    if not isinstance(notes, str) or len(notes.strip()) > 500:
        raise ValidationError("Invalid teacher review notes.")
    render = workflow.video_render_versions.select_for_update().filter(
        pk=_positive(render_id, "render identifier"),
        reference=workflow.draft_video_reference,
        status=VideoRenderVersion.Status.SUCCEEDED,
    ).first()
    if workflow.state != LectureWorkflow.State.DRAFT_VIDEO_READY or render is None:
        raise VideoConflict("The current draft is unavailable for teacher review.")
    _input_is_current(render.render_input, workflow)
    target = (
        LectureWorkflow.State.TEACHER_VIDEO_APPROVED
        if decision == TeacherVideoReview.Decision.APPROVED
        else LectureWorkflow.State.TEACHER_VIDEO_REVISION_REQUESTED
    )
    transition_workflow(
        actor=actor,
        workflow_id=workflow.pk,
        target_state=target,
        reason_code=(
            "TEACHER_APPROVED_VIDEO"
            if decision == TeacherVideoReview.Decision.APPROVED
            else "TEACHER_REQUESTED_VIDEO_REVISION"
        ),
        expected_version=workflow.version,
        idempotency_key=f"t050-teacher-review:{render.pk}:{decision.lower()}",
    )
    return TeacherVideoReview.objects.create(
        render=render,
        decision=decision,
        notes=notes.strip(),
        reviewed_by_id=actor.internal_actor_id,
    )


@transaction.atomic
def grant_admin_final_approval(
    *, actor: WorkflowActorContext, workflow_id: int, render_id: int
) -> AdminFinalVideoApproval:
    workflow = LectureWorkflow.objects.select_for_update().select_related(
        "generation__chapter__course"
    ).get(pk=_positive(workflow_id, "workflow identifier"))
    _require_admin(actor, workflow)
    render = workflow.video_render_versions.select_for_update().filter(
        pk=_positive(render_id, "render identifier"),
        reference=workflow.draft_video_reference,
        status=VideoRenderVersion.Status.SUCCEEDED,
    ).first()
    if workflow.state != LectureWorkflow.State.TEACHER_VIDEO_APPROVED or render is None:
        raise VideoConflict("Teacher approval of the current render is required.")
    try:
        review = render.teacher_review
    except ObjectDoesNotExist as exc:
        raise ValidationError("Teacher video approval evidence is unavailable.") from exc
    if (
        review.decision != TeacherVideoReview.Decision.APPROVED
        or review.reviewed_by_id != workflow.generation.chapter.course.teacher_id
    ):
        raise ValidationError("Teacher video approval evidence is invalid.")
    _input_is_current(render.render_input, workflow)
    transition_workflow(
        actor=actor,
        workflow_id=workflow.pk,
        target_state=LectureWorkflow.State.FINAL_ADMIN_APPROVED,
        reason_code="ADMIN_APPROVED_FINAL",
        expected_version=workflow.version,
        idempotency_key=f"t050-admin-final:{render.pk}",
    )
    return AdminFinalVideoApproval.objects.create(
        render=render, teacher_review=review, approved_by_id=actor.internal_actor_id
    )


@transaction.atomic
def request_export_package(
    *, actor: WorkflowActorContext, workflow_id: int, render_id: int
) -> VideoExportPackage:
    workflow = LectureWorkflow.objects.select_for_update().select_related(
        "generation__chapter__course"
    ).get(pk=_positive(workflow_id, "workflow identifier"))
    _require_admin(actor, workflow)
    render = workflow.video_render_versions.select_for_update().filter(
        pk=_positive(render_id, "render identifier"),
        reference=workflow.draft_video_reference,
        status=VideoRenderVersion.Status.SUCCEEDED,
    ).first()
    if workflow.state != LectureWorkflow.State.FINAL_ADMIN_APPROVED or render is None:
        raise VideoConflict("Final administrator approval is required before export.")
    try:
        approval = render.admin_final_approval
    except ObjectDoesNotExist as exc:
        raise ValidationError("Final approval evidence is unavailable.") from exc
    _input_is_current(render.render_input, workflow)
    job = submit_job(
        actor=actor,
        workflow_id=workflow.pk,
        job_type=WorkflowJob.JobType.EXPORT_READINESS,
        payload={"draft_video_reference": render.reference},
        idempotency_key=f"t050-export:{render.pk}",
        max_attempts=1,
    )
    version = workflow.video_export_packages.count() + 1
    digest = _sha(f"{workflow.pk}:{render.pk}:{version}:{render.video_sha256}".encode("ascii"))[:40]
    return VideoExportPackage.objects.create(
        workflow=workflow,
        render=render,
        admin_approval=approval,
        job=job,
        version=version,
        reference=f"export:package-{digest}",
        storage_key=f"workflow-{workflow.pk}/package-v{version}-{digest}",
        requested_by_id=actor.internal_actor_id,
    )


def _srt_timestamp(milliseconds: int) -> str:
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def _ms_to_frames(milliseconds: int, fps: int) -> int:
    return max(0, (milliseconds * fps + 500) // 1000)


def _frames_to_ms(frames: int, fps: int) -> int:
    return (frames * 1000 + fps // 2) // fps


def _kept_intervals(duration_ms: int, cuts: list[dict]) -> list[tuple[int, int]]:
    intervals = []
    cursor = 0
    for cut in cuts:
        if cut["startMs"] > cursor:
            intervals.append((cursor, cut["startMs"]))
        cursor = cut["endMs"]
    if cursor < duration_ms:
        intervals.append((cursor, duration_ms))
    return intervals


def _build_srt(manifest: dict) -> str:
    blocks = []
    fps = manifest["fps"]
    for index, slide in enumerate(manifest["slides"], 1):
        start = _frames_to_ms(slide["timelineStartFrame"], fps)
        end = _frames_to_ms(
            slide["timelineStartFrame"] + slide["durationInFrames"], fps
        )
        blocks.append(
            f"{index}\n{_srt_timestamp(start)} --> {_srt_timestamp(end)}\n"
            f"{slide['caption']}\n"
        )
    return "\n".join(blocks)


def _build_pptx(path: Path, render_input: VideoRenderInput) -> None:
    items = list(render_input.items.order_by("position"))
    slide_ids = "".join(
        f'<p:sldId id="{255 + index}" r:id="rId{index}"/>' for index in range(1, len(items) + 1)
    )
    presentation_rels = "".join(
        f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{index}.xml"/>'
        for index in range(1, len(items) + 1)
    )
    overrides = "".join(
        f'<Override PartName="/ppt/slides/slide{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for index in range(1, len(items) + 1)
    )
    content_types = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/><Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/><Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/><Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>{overrides}</Types>'''
    presentation = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId{len(items)+1}"/></p:sldMasterIdLst><p:sldIdLst>{slide_ids}</p:sldIdLst><p:sldSz cx="12192000" cy="6858000" type="screen16x9"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>'''
    root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/></Relationships>'''
    presentation_rels = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{presentation_rels}<Relationship Id="rId{len(items)+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/></Relationships>'''
    master = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld><p:sldLayoutIdLst><p:sldLayoutId id="1" r:id="rId1"/></p:sldLayoutIdLst><p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles></p:sldMaster>'''
    master_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/></Relationships>'''
    layout = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1"><p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld></p:sldLayout>'''
    layout_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/></Relationships>'''
    theme = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Synthetic local theme"><a:themeElements><a:clrScheme name="Local"><a:dk1><a:srgbClr val="172B4D"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="102A43"/></a:dk2><a:lt2><a:srgbClr val="F5F7FA"/></a:lt2><a:accent1><a:srgbClr val="0B6BCB"/></a:accent1><a:accent2><a:srgbClr val="087F5B"/></a:accent2><a:accent3><a:srgbClr val="8A5B00"/></a:accent3><a:accent4><a:srgbClr val="60758A"/></a:accent4><a:accent5><a:srgbClr val="6AA9E9"/></a:accent5><a:accent6><a:srgbClr val="A61B1B"/></a:accent6><a:hlink><a:srgbClr val="0563C1"/></a:hlink><a:folHlink><a:srgbClr val="954F72"/></a:folHlink></a:clrScheme><a:fontScheme name="Local"><a:majorFont><a:latin typeface="Arial"/><a:ea typeface=""/><a:cs typeface="Arial"/></a:majorFont><a:minorFont><a:latin typeface="Arial"/><a:ea typeface=""/><a:cs typeface="Arial"/></a:minorFont></a:fontScheme><a:fmtScheme name="Local"><a:fillStyleLst/><a:lnStyleLst/><a:effectStyleLst/><a:bgFillStyleLst/></a:fmtScheme></a:themeElements></a:theme>'''
    slide_rel = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/></Relationships>'''
    with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("ppt/presentation.xml", presentation)
        archive.writestr("ppt/_rels/presentation.xml.rels", presentation_rels)
        archive.writestr("ppt/slideMasters/slideMaster1.xml", master)
        archive.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", master_rels)
        archive.writestr("ppt/slideLayouts/slideLayout1.xml", layout)
        archive.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", layout_rels)
        archive.writestr("ppt/theme/theme1.xml", theme)
        for index, item in enumerate(items, 1):
            claims = " • ".join(str(value) for value in item.claims_snapshot)
            title = escape(item.title_snapshot)
            body = escape(claims)
            slide = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr><p:sp><p:nvSpPr><p:cNvPr id="2" name="Title"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="700000" y="600000"/><a:ext cx="10800000" cy="1200000"/></a:xfrm><a:noFill/></p:spPr><p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="ur-PK" sz="3000" b="1"/><a:t>{title}</a:t></a:r></a:p></p:txBody></p:sp><p:sp><p:nvSpPr><p:cNvPr id="3" name="Claims"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="900000" y="2100000"/><a:ext cx="10400000" cy="3600000"/></a:xfrm><a:noFill/></p:spPr><p:txBody><a:bodyPr wrap="square"/><a:lstStyle/><a:p><a:r><a:rPr lang="ur-PK" sz="2200"/><a:t>{body}</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>'''
            archive.writestr(f"ppt/slides/slide{index}.xml", slide)
            archive.writestr(f"ppt/slides/_rels/slide{index}.xml.rels", slide_rel)


def _save_export(package: VideoExportPackage, **fields) -> None:
    for name, value in fields.items():
        setattr(package, name, value)
    package._domain_service_write = True
    try:
        package.save(update_fields=(*fields.keys(),))
    finally:
        del package._domain_service_write


def _assemble_export(package: VideoExportPackage) -> None:
    root = _root("VIDEO_EXPORT_ROOT")
    final_dir = _storage_path(root, package.storage_key)
    staging = final_dir.with_name(f".{final_dir.name}.staging")
    if final_dir.exists() or staging.exists():
        raise ValidationError("Immutable export destination already exists.")
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.mkdir()
    try:
        source_video = render_video_path(package.render)
        manifest_path = _storage_path(
            _root("VIDEO_STORAGE_ROOT"), package.render.manifest_storage_key, must_exist=True
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        video_target = staging / "lecture.mp4"
        shutil.copyfile(source_video, video_target)
        (staging / "captions.srt").write_text(_build_srt(manifest), encoding="utf-8-sig")
        metadata = {
            "schema_version": 1,
            "title": package.workflow.generation.chapter.title,
            "course": package.workflow.generation.chapter.course.title,
            "render_reference": package.render.reference,
            "teacher_video_approved_at": package.admin_approval.teacher_review.reviewed_at.isoformat(),
            "admin_final_approved_at": package.admin_approval.approved_at.isoformat(),
            "upload_performed": False,
            "evaluation_only": True,
        }
        (staging / "metadata.json").write_bytes(_canonical(metadata))
        _build_pptx(staging / "slides.pptx", package.render.render_input)
        files = []
        for path in sorted(staging.iterdir()):
            digest, size = _file_sha(path)
            files.append({"name": path.name, "sha256": digest, "byte_size": size})
        package_manifest = {
            "schema_version": 1,
            "export_reference": package.reference,
            "files": files,
            "local_only": True,
            "upload_performed": False,
        }
        encoded = _canonical(package_manifest)
        (staging / "package-manifest.json").write_bytes(encoded)
        staging.rename(final_dir)
        _save_export(
            package,
            status=VideoExportPackage.Status.READY,
            manifest_sha256=_sha(encoded),
            completed_at=timezone.now(),
        )
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def _process_export_job(job: WorkflowJob, worker: WorkflowActorContext) -> None:
    package = VideoExportPackage.objects.select_related(
        "render__render_input", "admin_approval__teacher_review"
    ).filter(job=job).first()
    if package is None:
        fail_job(
            actor=worker,
            job_id=job.pk,
            reason_code="INVALID_INPUT",
            message="No trusted T050 export package matches this job.",
            retryable=False,
        )
        return
    _save_export(package, status=VideoExportPackage.Status.RUNNING)
    try:
        _input_is_current(package.render.render_input, job.workflow)
        _assemble_export(package)
        complete_job(
            actor=worker,
            job_id=job.pk,
            completion_idempotency_key=f"t050-export-ready:{package.pk}",
            result={
                "job_id": job.pk,
                "job_type": job.job_type,
                "workflow_id": job.workflow_id,
                "workflow_version": job.workflow_version,
                "export_reference": package.reference,
            },
        )
        transition_workflow(
            actor=worker,
            workflow_id=job.workflow_id,
            target_state=LectureWorkflow.State.EXPORT_READY,
            reason_code="EXPORT_HANDOFF_READY",
            expected_version=job.workflow.version,
            idempotency_key=f"t050-export-transition:{package.pk}",
            job_id=job.pk,
            artifact_reference=package.reference,
        )
    except Exception:
        package.refresh_from_db()
        if package.status == VideoExportPackage.Status.RUNNING:
            _save_export(
                package,
                status=VideoExportPackage.Status.FAILED,
                failure_reason_code="LOCAL_EXPORT_FAILED",
                completed_at=timezone.now(),
            )
        job.refresh_from_db()
        if job.status == WorkflowJob.Status.RUNNING:
            fail_job(
                actor=worker,
                job_id=job.pk,
                reason_code="WORKER_ERROR",
                message="The local export package failed safely.",
                retryable=False,
            )
        raise


def process_next_readiness_job() -> WorkflowJob | None:
    course_ids = list(Course.objects.filter(is_active=True).values_list("pk", flat=True))
    if not render_environment_supported():
        raise UnsupportedRenderEnvironment("The trusted local evaluation render adapter is not enabled.")
    if not course_ids:
        return None
    worker = system_worker_context(
        identity_reference="t050-local-render-worker", permitted_course_ids=course_ids
    )
    job = claim_job(
        actor=worker,
        lease_seconds=3600,
        job_types=[
            WorkflowJob.JobType.DRAFT_VIDEO_READINESS,
            WorkflowJob.JobType.EXPORT_READINESS,
        ],
    )
    if job is None:
        return None
    job = WorkflowJob.objects.select_related("workflow__generation__chapter__course").get(pk=job.pk)
    if job.job_type == WorkflowJob.JobType.DRAFT_VIDEO_READINESS:
        _process_review_job(job, worker)
    else:
        _process_export_job(job, worker)
    return job
