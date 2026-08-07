from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .content import register_upload, sources_visible_to
from .models import Chapter, ContentSource


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
        requested = {int(value) for value in body.get("source_ids", [])}
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
