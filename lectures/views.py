from __future__ import annotations

import json
import re

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.conf import settings
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .content import register_upload, sources_visible_to
from .generation import actor_context_for_user, approve_slide, caption_for_slide, create_generation, revise_slide
from .models import (
    Chapter, ContentSource, GenerationRequest, LectureWorkflow, RecordingTake, SlideDraft, WorkflowJob,
)
from .recording import (
    RecordingConflict, complete_recording, create_take, open_recording, recording_path,
    recordings_visible_to, select_take,
)
from .workflow import (
    WorkflowConflict, cancel_job, claim_job, complete_job, create_workflow, fail_job,
    jobs_visible_to, submit_job, transition_workflow,
    workflow_actor_for_user, workflows_visible_to,
)


def _safe_json(payload, *, status=200):
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    encoded = encoded.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return HttpResponse(encoded, status=status, content_type="application/json; charset=utf-8", headers={"X-Content-Type-Options": "nosniff"})


def _body(request):
    try:
        if int(request.headers.get("Content-Length", "0") or 0) > settings.GENERATION_MAX_REQUEST_BYTES:
            raise ValueError
        raw = request.body
        if len(raw) > settings.GENERATION_MAX_REQUEST_BYTES:
            raise ValueError
        value = json.loads(raw or "{}")
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValidationError("Invalid bounded JSON request.") from exc


def _workflow_body(request):
    try:
        if int(request.headers.get("Content-Length", "0") or 0) > settings.WORKFLOW_MAX_REQUEST_BYTES:
            raise ValueError
        raw = request.body
        if len(raw) > settings.WORKFLOW_MAX_REQUEST_BYTES:
            raise ValueError
        value = json.loads(raw or "{}")
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValidationError("Invalid bounded JSON request.") from exc


def _validation_message(exc):
    if isinstance(exc, ValidationError):
        return exc.messages[0] if exc.messages else "Invalid workflow request."
    return "Workflow record is unavailable."


def _workflow_error(exc):
    if isinstance(exc, PermissionDenied):
        return _safe_json({"error": str(exc)}, status=403)
    if isinstance(exc, WorkflowConflict):
        return _safe_json({"error": _validation_message(exc)}, status=409)
    if isinstance(exc, ValidationError):
        return _safe_json({"error": _validation_message(exc)}, status=400)
    return _safe_json({"error": "Workflow record is unavailable."}, status=404)


def _recording_error(exc):
    if isinstance(exc, PermissionDenied):
        return _safe_json({"error": "Recording operation is not authorized."}, status=403)
    if isinstance(exc, (RecordingConflict, WorkflowConflict)):
        return _safe_json({"error": _validation_message(exc)}, status=409)
    if isinstance(exc, ValidationError):
        return _safe_json({"error": _validation_message(exc)}, status=400)
    return _safe_json({"error": "Recording record is unavailable."}, status=404)


def _exact_fields(body, required, optional=()):
    if not isinstance(body, dict) or not set(required).issubset(body) or set(body) - set(required) - set(optional):
        raise ValidationError("Unexpected or missing request fields.")


def _workflow_payload(workflow):
    return {
        "id": workflow.pk,
        "generation_id": workflow.generation_id,
        "course_id": workflow.generation.chapter.course_id,
        "state": workflow.state,
        "version": workflow.version,
        "recording_reference": workflow.recording_reference,
        "draft_video_reference": workflow.draft_video_reference,
        "export_reference": workflow.export_reference,
        "teacher_video_approved": bool(workflow.teacher_video_approved_at),
        "final_admin_approved": bool(workflow.final_admin_approved_at),
        "created_at": workflow.created_at.isoformat(),
        "updated_at": workflow.updated_at.isoformat(),
    }


def _job_payload(job):
    return {
        "id": job.pk,
        "workflow_id": job.workflow_id,
        "job_type": job.job_type,
        "workflow_version": job.workflow_version,
        "payload": job.payload,
        "status": job.status,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "available_at": job.available_at.isoformat(),
        "leased_until": job.leased_until.isoformat() if job.leased_until else None,
        "failure_reason_code": job.failure_reason_code,
        "failure_message": job.failure_message,
        "result": job.result,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "events": [
            {
                "sequence": event.sequence,
                "actor_type": event.actor_type,
                "actor_identity_reference": event.actor_identity_reference,
                "previous_status": event.previous_status,
                "new_status": event.new_status,
                "reason_code": event.reason_code,
                "occurred_at": event.occurred_at.isoformat(),
            }
            for event in job.events.all()
        ],
    }


def _trusted_http_worker_actor():
    """Fail closed until a server-authenticated worker adapter is separately configured."""

    raise PermissionDenied("Trusted HTTP worker authentication is not configured.")


def _revision_payload(revision):
    def items(rows):
        return [{
            "id": row.pk, "position": row.position, "text": row.text,
            "sources": [{
                "page_snapshot_id": ref.page_snapshot_id,
                "source_title": ref.page_snapshot.source_snapshot.source_title,
                "page_number": ref.page_snapshot.page_number,
                "start_offset": ref.start_offset, "end_offset": ref.end_offset,
            } for ref in row.references.select_related("page_snapshot__source_snapshot")],
        } for row in rows]
    return {"id": revision.pk, "version": revision.version, "title": revision.title,
            "claims": items(revision.claims.all()), "narration": items(revision.narration_statements.all())}


def _generation_payload(generation, *, detail=False):
    payload = {"id": generation.pk, "chapter_id": generation.chapter_id, "status": generation.status,
               "generator_key": generation.generator_key, "input_sha256": generation.input_sha256,
               "guidelines": generation.guidelines}
    if detail:
        payload["slides"] = [{
            "id": slide.pk, "position": slide.position, "current_version": slide.current_version,
            "approved_revision_id": slide.approved_revision_id,
            "revision": _revision_payload(slide.revisions.get(version=slide.current_version)),
        } for slide in generation.slides.all()]
    return payload


def _source_payload(source: ContentSource) -> dict:
    return {
        "id": source.pk,
        "title": source.title,
        "source_type": source.source_type,
        "access_scope": source.access_scope,
        "chapter_id": source.chapter_id,
        "course_id": source.chapter.course_id,
        "page_count": source.page_count,
        "processing_state": source.processing_state,
        "rights_confirmed": source.rights_confirmed,
    }


@login_required
@require_http_methods(["GET", "POST"])
def content_sources(request):
    if request.method == "GET":
        return JsonResponse({"sources": [_source_payload(item) for item in sources_visible_to(request.user)]})
    try:
        upload = request.FILES["file"]
        chapter = Chapter.objects.select_related("course").get(pk=request.POST.get("chapter_id"))
        source = register_upload(
            actor=request.user,
            chapter=chapter,
            title=request.POST.get("title", ""),
            source_type=request.POST.get("source_type", ""),
            rights_confirmed=request.POST.get("rights_confirmed", "").lower() in {"1", "true", "yes"},
            upload=upload,
            filename=upload.name,
        )
        return JsonResponse(_source_payload(source), status=201)
    except (KeyError, ValueError, Chapter.DoesNotExist, ValidationError, PermissionDenied) as exc:
        return JsonResponse({"error": str(exc)}, status=400 if not isinstance(exc, PermissionDenied) else 403)


@login_required
@require_http_methods(["POST"])
def content_selection(request):
    try:
        body = json.loads(request.body or "{}")
        if not isinstance(body, dict):
            raise ValueError
        source_ids = body.get("source_ids", [])
        if not isinstance(source_ids, list) or any(
            isinstance(value, bool)
            or not isinstance(value, (int, str))
            or (isinstance(value, str) and re.fullmatch(r"[1-9][0-9]*", value) is None)
            for value in source_ids
        ):
            raise ValueError
        requested = {int(value) for value in source_ids}
        if any(value <= 0 for value in requested):
            raise ValueError
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid source selection."}, status=400)
    visible = sources_visible_to(request.user).filter(
        pk__in=requested,
        rights_confirmed=True,
        processing_state=ContentSource.ProcessingState.READY,
    )
    if set(visible.values_list("pk", flat=True)) != requested:
        return JsonResponse({"error": "Selection includes an unauthorized source."}, status=403)
    return JsonResponse({"sources": [_source_payload(item) for item in visible]})


@login_required
@require_http_methods(["GET", "POST"])
def generations(request):
    context = actor_context_for_user(request.user)
    if not context.can_generate:
        return _safe_json({"error": "Generation is not authorized."}, status=403)
    if request.method == "GET":
        rows = GenerationRequest.objects.filter(requested_by_id=context.actor_id).select_related("chapter")
        return _safe_json({"generations": [_generation_payload(row) for row in rows]})
    try:
        body = _body(request)
        generation = create_generation(
            actor=context, chapter_id=body.get("chapter_id"), source_ids=body.get("source_ids"),
            guidelines=body.get("guidelines"),
        )
        return _safe_json(_generation_payload(generation, detail=True), status=201)
    except PermissionDenied as exc:
        return _safe_json({"error": str(exc)}, status=403)
    except (ValidationError, Chapter.DoesNotExist) as exc:
        return _safe_json({"error": str(exc)}, status=400)


@login_required
@require_http_methods(["GET"])
def generation_detail(request, generation_id):
    context = actor_context_for_user(request.user)
    generation = GenerationRequest.objects.filter(pk=generation_id, requested_by_id=context.actor_id).first()
    if generation is None:
        return _safe_json({"error": "Generation is unavailable."}, status=403)
    return _safe_json(_generation_payload(generation, detail=True))


@login_required
@require_http_methods(["POST"])
def slide_revisions(request, slide_id):
    try:
        body = _body(request)
        revision = revise_slide(
            actor=actor_context_for_user(request.user), slide_id=slide_id, title=body.get("title"),
            claims=body.get("claims"), narration=body.get("narration"),
        )
        return _safe_json(_revision_payload(revision), status=201)
    except PermissionDenied as exc:
        return _safe_json({"error": str(exc)}, status=403)
    except (ValidationError, SlideDraft.DoesNotExist) as exc:
        return _safe_json({"error": str(exc)}, status=400)


@login_required
@require_http_methods(["POST"])
def slide_approval(request, slide_id):
    try:
        snapshot = approve_slide(actor=actor_context_for_user(request.user), slide_id=slide_id)
        return _safe_json({"slide_id": slide_id, "approved_revision_id": snapshot.revision_id,
                           "canonical_narration_sha256": snapshot.text_sha256})
    except PermissionDenied as exc:
        return _safe_json({"error": str(exc)}, status=403)
    except (ValidationError, SlideDraft.DoesNotExist) as exc:
        return _safe_json({"error": str(exc)}, status=400)


@login_required
@require_http_methods(["GET"])
def slide_caption(request, slide_id):
    try:
        snapshot = caption_for_slide(actor=actor_context_for_user(request.user), slide_id=slide_id)
        return _safe_json({"slide_id": slide_id, "revision_id": snapshot.revision_id,
                           "text": snapshot.text, "sha256": snapshot.text_sha256})
    except PermissionDenied as exc:
        return _safe_json({"error": str(exc)}, status=403)
    except SlideDraft.DoesNotExist:
        return _safe_json({"error": "Slide is unavailable."}, status=403)


@login_required
@require_http_methods(["GET", "POST"])
def workflows(request):
    actor = workflow_actor_for_user(request.user)
    if request.method == "GET":
        rows = workflows_visible_to(actor).select_related("generation__chapter__course")
        return _safe_json({"workflows": [_workflow_payload(row) for row in rows]})
    try:
        body = _workflow_body(request)
        _exact_fields(body, {"generation_id", "idempotency_key"})
        workflow = create_workflow(
            actor=actor,
            generation_id=body["generation_id"],
            idempotency_key=body["idempotency_key"],
        )
        workflow = LectureWorkflow.objects.select_related("generation__chapter__course").get(pk=workflow.pk)
        return _safe_json(_workflow_payload(workflow), status=201)
    except (PermissionDenied, ValidationError, GenerationRequest.DoesNotExist) as exc:
        return _workflow_error(exc)


@login_required
@require_http_methods(["GET"])
def workflow_detail(request, workflow_id):
    workflow = workflows_visible_to(workflow_actor_for_user(request.user)).select_related(
        "generation__chapter__course"
    ).filter(pk=workflow_id).first()
    if workflow is None:
        return _safe_json({"error": "Workflow record is unavailable."}, status=403)
    return _safe_json(_workflow_payload(workflow))


@login_required
@require_http_methods(["POST"])
def workflow_transition(request, workflow_id):
    try:
        body = _workflow_body(request)
        _exact_fields(
            body,
            {"target_state", "reason_code", "expected_version", "idempotency_key"},
            {"job_id", "artifact_reference"},
        )
        actor = workflow_actor_for_user(request.user)
        workflow = transition_workflow(
            actor=actor,
            workflow_id=workflow_id,
            target_state=body["target_state"],
            reason_code=body["reason_code"],
            expected_version=body["expected_version"],
            idempotency_key=body["idempotency_key"],
            job_id=body.get("job_id"),
            artifact_reference=body.get("artifact_reference", ""),
        )
        workflow = LectureWorkflow.objects.select_related("generation__chapter__course").get(pk=workflow.pk)
        return _safe_json(_workflow_payload(workflow))
    except (PermissionDenied, ValidationError, LectureWorkflow.DoesNotExist, WorkflowJob.DoesNotExist) as exc:
        return _workflow_error(exc)


@login_required
@require_http_methods(["GET"])
def workflow_audit(request, workflow_id):
    workflow = workflows_visible_to(workflow_actor_for_user(request.user)).filter(pk=workflow_id).first()
    if workflow is None:
        return _safe_json({"error": "Workflow record is unavailable."}, status=403)
    return _safe_json(
        {
            "events": [
                {
                    "sequence": event.sequence,
                    "actor_type": event.actor_type,
                    "actor_identity_reference": event.actor_identity_reference,
                    "previous_state": event.previous_state,
                    "new_state": event.new_state,
                    "reason_code": event.reason_code,
                    "occurred_at": event.occurred_at.isoformat(),
                }
                for event in workflow.audit_events.all()
            ]
        }
    )


@login_required
@require_http_methods(["GET", "POST"])
def workflow_jobs(request):
    actor = workflow_actor_for_user(request.user)
    if request.method == "GET":
        rows = jobs_visible_to(actor)
        workflow_id = request.GET.get("workflow_id")
        if workflow_id:
            if not workflow_id.isdecimal() or int(workflow_id) <= 0:
                return _safe_json({"error": "Invalid workflow identifier."}, status=400)
            rows = rows.filter(workflow_id=int(workflow_id))
        return _safe_json({"jobs": [_job_payload(row) for row in rows]})
    try:
        body = _workflow_body(request)
        _exact_fields(
            body,
            {"workflow_id", "job_type", "payload", "idempotency_key"},
            {"max_attempts"},
        )
        job = submit_job(
            actor=actor,
            workflow_id=body["workflow_id"],
            job_type=body["job_type"],
            payload=body["payload"],
            idempotency_key=body["idempotency_key"],
            max_attempts=body.get("max_attempts", 3),
        )
        return _safe_json(_job_payload(job), status=201)
    except (PermissionDenied, ValidationError, LectureWorkflow.DoesNotExist) as exc:
        return _workflow_error(exc)


@login_required
@require_http_methods(["POST"])
def workflow_job_claim(request):
    try:
        body = _workflow_body(request)
        _exact_fields(body, {"lease_seconds"}, {"job_types"})
        job = claim_job(
            actor=_trusted_http_worker_actor(),
            lease_seconds=body["lease_seconds"],
            job_types=body.get("job_types"),
        )
        return _safe_json({"job": _job_payload(job) if job else None})
    except (PermissionDenied, ValidationError) as exc:
        return _workflow_error(exc)


@login_required
@require_http_methods(["POST"])
def workflow_job_complete(request, job_id):
    try:
        body = _workflow_body(request)
        _exact_fields(body, {"completion_idempotency_key", "result"})
        job = complete_job(
            actor=_trusted_http_worker_actor(),
            job_id=job_id,
            completion_idempotency_key=body["completion_idempotency_key"],
            result=body["result"],
        )
        return _safe_json(_job_payload(job))
    except (PermissionDenied, ValidationError, WorkflowJob.DoesNotExist) as exc:
        return _workflow_error(exc)


@login_required
@require_http_methods(["POST"])
def workflow_job_fail(request, job_id):
    try:
        body = _workflow_body(request)
        _exact_fields(
            body,
            {"reason_code", "message", "retryable"},
            {"retry_delay_seconds"},
        )
        job = fail_job(
            actor=_trusted_http_worker_actor(),
            job_id=job_id,
            reason_code=body["reason_code"],
            message=body["message"],
            retryable=body["retryable"],
            retry_delay_seconds=body.get("retry_delay_seconds", 0),
        )
        return _safe_json(_job_payload(job))
    except (PermissionDenied, ValidationError, WorkflowJob.DoesNotExist) as exc:
        return _workflow_error(exc)


@login_required
@require_http_methods(["POST"])
def workflow_job_cancel(request, job_id):
    try:
        body = _workflow_body(request)
        _exact_fields(body, set())
        job = cancel_job(actor=workflow_actor_for_user(request.user), job_id=job_id)
        return _safe_json(_job_payload(job))
    except (PermissionDenied, ValidationError, WorkflowJob.DoesNotExist) as exc:
        return _workflow_error(exc)


def _take_payload(take, *, selected=False):
    return {
        "id": take.pk,
        "take_number": take.take_number,
        "slide_revision_id": take.slide_revision_id,
        "media_type": take.media_type,
        "byte_size": take.byte_size,
        "duration_ms": take.duration_ms,
        "created_at": take.created_at.isoformat(),
        "selected": selected,
        "media_url": f"/teacher/recording-takes/{take.pk}/media/",
    }


def _recording_workflow_payload(workflow):
    selections = {
        item.slide_id: item
        for item in workflow.recording_selections.select_related("current_take").all()
    }
    slides = []
    for slide in workflow.generation.slides.select_related(
        "approved_revision__canonical_narration"
    ).prefetch_related("approved_revision__recording_takes").order_by("position"):
        revision = slide.approved_revision
        current = revision is not None and revision.version == slide.current_version
        narration = ""
        if current:
            try:
                narration = revision.canonical_narration.text
            except ObjectDoesNotExist:
                current = False
        selection = selections.get(slide.pk)
        selected_id = selection.current_take_id if selection else None
        takes = list(
            RecordingTake.objects.filter(workflow=workflow, slide_revision=revision).order_by("take_number")
        ) if revision else []
        slides.append(
            {
                "id": slide.pk,
                "position": slide.position,
                "current_version": slide.current_version,
                "approved_revision_id": revision.pk if current else None,
                "title": revision.title if current else "Approval required",
                "narration": narration,
                "eligible": current and workflow.state == LectureWorkflow.State.RECORDING_PENDING,
                "selected_take_id": selected_id if any(t.pk == selected_id for t in takes) else None,
                "takes": [_take_payload(take, selected=take.pk == selected_id) for take in takes],
            }
        )
    return {
        "id": workflow.pk,
        "state": workflow.state,
        "version": workflow.version,
        "class_name": workflow.generation.chapter.course.class_name,
        "subject_name": workflow.generation.chapter.course.subject_name,
        "course_code": workflow.generation.chapter.course.code,
        "course_title": workflow.generation.chapter.course.title,
        "chapter_number": workflow.generation.chapter.number,
        "chapter_title": workflow.generation.chapter.title,
        "can_open": workflow.state == LectureWorkflow.State.TEACHER_SLIDE_NARRATION_APPROVED,
        "can_record": workflow.state == LectureWorkflow.State.RECORDING_PENDING,
        "completed": workflow.state not in {
            LectureWorkflow.State.SOURCE_CONTENT_READY,
            LectureWorkflow.State.SLIDE_NARRATION_DRAFT,
            LectureWorkflow.State.TEACHER_SLIDE_NARRATION_APPROVED,
            LectureWorkflow.State.RECORDING_PENDING,
        },
        "slides": slides,
    }


@login_required
@require_http_methods(["GET"])
def teacher_recording_portal(request):
    actor = workflow_actor_for_user(request.user)
    workflows = list(recordings_visible_to(actor).order_by(
        "generation__chapter__course__class_name",
        "generation__chapter__course__subject_name",
        "generation__chapter__course__code",
        "generation__chapter__number",
    ))
    return render(request, "lectures/recording_portal.html", {"workflows": workflows})


@login_required
@require_http_methods(["GET"])
def teacher_recording_detail(request, workflow_id):
    actor = workflow_actor_for_user(request.user)
    workflow = recordings_visible_to(actor).filter(pk=workflow_id).first()
    if workflow is None:
        return render(request, "lectures/recording_unavailable.html", status=404)
    payload = _recording_workflow_payload(workflow)
    return render(
        request,
        "lectures/recording_detail.html",
        {"workflow": workflow, "recording_payload": payload},
    )


@login_required
@require_http_methods(["POST"])
def recording_open_api(request, workflow_id):
    try:
        body = _workflow_body(request)
        _exact_fields(body, {"expected_version"})
        workflow = open_recording(
            actor=workflow_actor_for_user(request.user),
            workflow_id=workflow_id,
            expected_version=body["expected_version"],
        )
        return _safe_json(_recording_workflow_payload(workflow))
    except (PermissionDenied, ValidationError, LectureWorkflow.DoesNotExist) as exc:
        return _recording_error(exc)


@login_required
@require_http_methods(["POST"])
def recording_take_upload_api(request, workflow_id, slide_id):
    try:
        try:
            content_length = int(request.headers.get("Content-Length", "0") or 0)
        except (TypeError, ValueError) as exc:
            raise ValidationError("Invalid recording request size.") from exc
        if content_length <= 0 or content_length > settings.RECORDING_MAX_REQUEST_BYTES:
            raise ValidationError("Recording request size is outside the allowed range.")
        if set(request.POST) != {"expected_revision_id", "duration_ms"} or set(request.FILES) != {"audio"}:
            raise ValidationError("Unexpected or missing recording fields.")
        upload = request.FILES["audio"]
        media_type = (upload.content_type or "").split(";", 1)[0].strip().lower()
        take = create_take(
            actor=workflow_actor_for_user(request.user),
            workflow_id=workflow_id,
            slide_id=slide_id,
            expected_revision_id=request.POST["expected_revision_id"],
            upload=upload,
            duration_ms=request.POST["duration_ms"],
            filename=upload.name,
            media_type=media_type,
        )
        return _safe_json(_take_payload(take, selected=True), status=201)
    except (PermissionDenied, ValidationError, LectureWorkflow.DoesNotExist, SlideDraft.DoesNotExist, OSError) as exc:
        return _recording_error(exc)


@login_required
@require_http_methods(["POST"])
def recording_take_select_api(request, workflow_id, slide_id):
    try:
        body = _workflow_body(request)
        _exact_fields(body, {"take_id", "expected_revision_id"})
        selection = select_take(
            actor=workflow_actor_for_user(request.user),
            workflow_id=workflow_id,
            slide_id=slide_id,
            take_id=body["take_id"],
            expected_revision_id=body["expected_revision_id"],
        )
        return _safe_json(
            {"slide_id": slide_id, "selected_take_id": selection.current_take_id, "version": selection.version}
        )
    except (PermissionDenied, ValidationError, LectureWorkflow.DoesNotExist, SlideDraft.DoesNotExist) as exc:
        return _recording_error(exc)


@login_required
@require_http_methods(["POST"])
def recording_complete_api(request, workflow_id):
    try:
        body = _workflow_body(request)
        _exact_fields(body, {"expected_version", "expected_revision_ids"})
        completion = complete_recording(
            actor=workflow_actor_for_user(request.user),
            workflow_id=workflow_id,
            expected_version=body["expected_version"],
            expected_revision_ids=body["expected_revision_ids"],
        )
        completion.workflow.refresh_from_db()
        return _safe_json(
            {
                "reference": completion.reference,
                "completed_at": completion.completed_at.isoformat(),
                "workflow": _recording_workflow_payload(completion.workflow),
            }
        )
    except (PermissionDenied, ValidationError, LectureWorkflow.DoesNotExist) as exc:
        return _recording_error(exc)


@login_required
@require_http_methods(["GET"])
def recording_take_media(request, take_id):
    try:
        actor = workflow_actor_for_user(request.user)
        take = RecordingTake.objects.select_related(
            "workflow__generation__chapter__course"
        ).get(pk=take_id)
        if not recordings_visible_to(actor).filter(pk=take.workflow_id).exists():
            raise PermissionDenied
        path = recording_path(take)
        response = FileResponse(path.open("rb"), content_type=take.media_type)
        response["Content-Disposition"] = f'inline; filename="slide-take-{take.take_number}{take.extension}"'
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
    except (PermissionDenied, ValidationError, RecordingTake.DoesNotExist, OSError):
        return _safe_json({"error": "Recording media is unavailable."}, status=404)
