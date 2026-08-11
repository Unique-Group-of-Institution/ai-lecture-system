from __future__ import annotations

import json
import re

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods

from .content import register_upload, sources_visible_to
from .generation import actor_context_for_user, approve_slide, caption_for_slide, create_generation, revise_slide
from .models import Chapter, ContentSource, GenerationRequest, SlideDraft


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
