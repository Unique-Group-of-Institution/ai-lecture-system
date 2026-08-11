from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .content import _contained, sources_visible_to
from .models import (
    CanonicalNarrationSnapshot,
    Chapter,
    ContentSource,
    ExtractedPage,
    ExtractionVersion,
    GenerationPageSnapshot,
    GenerationRequest,
    GenerationSourceSnapshot,
    LectureWorkflow,
    NarrationStatement,
    SlideClaim,
    SlideDraft,
    SlideRevision,
    SourceReference,
)
from .roles import TEACHER_ROLE


GENERATOR_KEY = "deterministic-extractive-v1"
LANGUAGES = {"ENGLISH", "URDU", "BILINGUAL"}
TONES = {"NEUTRAL", "FORMAL", "CONVERSATIONAL"}


@dataclass(frozen=True)
class GenerationActorContext:
    """Provider-independent authorization facts supplied by an application adapter."""

    actor_id: int
    permitted_course_ids: frozenset[int]
    permitted_source_ids: frozenset[int]
    can_generate: bool
    can_review: bool


@dataclass(frozen=True)
class GroundedText:
    text: str
    page_snapshot_id: int
    start_offset: int
    end_offset: int


@dataclass(frozen=True)
class GeneratedSlide:
    title: str
    claims: tuple[GroundedText, ...]
    narration: tuple[GroundedText, ...]


class GroundedGenerator(Protocol):
    key: str

    def generate(self, pages: tuple[GenerationPageSnapshot, ...], guidelines: dict) -> tuple[GeneratedSlide, ...]: ...


def actor_context_for_user(user) -> GenerationActorContext:
    """Django-auth adapter. The domain service below never receives a session or User."""

    is_teacher = bool(
        user.is_authenticated
        and user.groups.filter(name=TEACHER_ROLE).exists()
        and user.has_perm("lectures.add_generationrequest")
    )
    course_ids = frozenset(user.courses_taught.filter(is_active=True).values_list("pk", flat=True)) if is_teacher else frozenset()
    source_ids = frozenset(sources_visible_to(user).values_list("pk", flat=True)) if is_teacher else frozenset()
    return GenerationActorContext(
        actor_id=user.pk or 0,
        permitted_course_ids=course_ids,
        permitted_source_ids=source_ids,
        can_generate=is_teacher,
        can_review=is_teacher and user.has_perm("lectures.change_slidedraft"),
    )


def _bounded_text(value, field: str, maximum: int, *, required: bool = False) -> str:
    if not isinstance(value, str):
        raise ValidationError({field: "Must be text."})
    value = unicodedata.normalize("NFC", value.strip())
    if required and not value:
        raise ValidationError({field: "This field is required."})
    if len(value) > maximum:
        raise ValidationError({field: f"Must contain at most {maximum} characters."})
    if any(unicodedata.category(char) in {"Cc", "Cs"} and char not in "\n\t" for char in value):
        raise ValidationError({field: "Contains unsupported Unicode control characters."})
    return value


def validate_guidelines(raw) -> dict:
    if not isinstance(raw, dict) or set(raw) - {
        "learning_objective", "audience_level", "slide_count", "language", "tone", "teaching_emphasis"
    }:
        raise ValidationError("Invalid generation guidelines.")
    slide_count = raw.get("slide_count", 5)
    if isinstance(slide_count, bool) or not isinstance(slide_count, int) or not 1 <= slide_count <= 30:
        raise ValidationError({"slide_count": "Must be an integer from 1 through 30."})
    language = raw.get("language", "BILINGUAL")
    tone = raw.get("tone", "NEUTRAL")
    if language not in LANGUAGES:
        raise ValidationError({"language": "Unsupported language preference."})
    if tone not in TONES:
        raise ValidationError({"tone": "Unsupported tone."})
    return {
        "learning_objective": _bounded_text(raw.get("learning_objective", ""), "learning_objective", 2000, required=True),
        "audience_level": _bounded_text(raw.get("audience_level", ""), "audience_level", 100, required=True),
        "slide_count": slide_count,
        "language": language,
        "tone": tone,
        "teaching_emphasis": _bounded_text(raw.get("teaching_emphasis", ""), "teaching_emphasis", 1000),
    }


class DeterministicExtractiveGenerator:
    key = GENERATOR_KEY

    @staticmethod
    def _units(page: GenerationPageSnapshot):
        text = page.text
        starts = [0]
        for match in re.finditer(r"(?<=[.!?۔؟])\s+|\n+", text):
            starts.append(match.end())
        starts.append(len(text))
        for left, right in zip(starts, starts[1:]):
            while left < right and text[left].isspace():
                left += 1
            while right > left and text[right - 1].isspace():
                right -= 1
            while right - left > 600:
                cut = text.rfind(" ", left, left + 601)
                cut = cut if cut > left else left + 600
                yield GroundedText(text[left:cut], page.pk, left, cut)
                left = cut
                while left < right and text[left].isspace():
                    left += 1
            if right > left:
                yield GroundedText(text[left:right], page.pk, left, right)

    def generate(self, pages, guidelines):
        units = [unit for page in pages for unit in self._units(page) if unit.text]
        if not units:
            raise ValidationError("Reviewed sources contain no supported text; generation failed closed.")
        maximum = settings.GENERATION_MAX_CLAIMS
        units = units[:maximum]
        count = min(guidelines["slide_count"], len(units))
        buckets = [[] for _ in range(count)]
        for index, unit in enumerate(units):
            buckets[min(index * count // len(units), count - 1)].append(unit)
        return tuple(
            GeneratedSlide(
                title=f"Source-grounded slide {position}",
                claims=tuple(bucket),
                narration=tuple(bucket),
            )
            for position, bucket in enumerate(buckets, start=1)
        )


def _load_reviewed_pages(source: ContentSource) -> tuple[ExtractionVersion, list[tuple[ExtractedPage, str]]]:
    if not source.rights_confirmed or source.processing_state != ContentSource.ProcessingState.READY:
        raise ValidationError("Every selected source must be authorized and fully reviewed.")
    extraction = source.extractions.order_by("-version").first()
    if extraction is None or extraction.status != ExtractionVersion.Status.COMPLETE:
        raise ValidationError("Every selected source must have a complete reviewed extraction.")
    pages = list(extraction.pages.select_related("source_file").order_by("page_number"))
    if not pages or any(
        page.requires_review
        or page.source_file_id != source.original_file.pk
        or (page.method == ExtractedPage.Method.OCR and page.review_status != ExtractedPage.ReviewStatus.APPROVED)
        for page in pages
    ):
        raise ValidationError("Every selected source page must be fully reviewed.")
    loaded = []
    for page in pages:
        path = _contained(page.text_storage_key)
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise ValidationError("Reviewed source text is unavailable.") from exc
        if len(raw) > settings.GENERATION_MAX_PAGE_TEXT_BYTES or hashlib.sha256(raw).hexdigest() != page.text_sha256:
            raise ValidationError("Reviewed source text failed integrity or resource checks.")
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValidationError("Reviewed source text is not valid UTF-8.") from exc
        _bounded_text(text, "source_text", settings.GENERATION_MAX_PAGE_CHARACTERS, required=True)
        loaded.append((page, text))
    return extraction, loaded


@transaction.atomic
def create_generation(*, actor: GenerationActorContext, chapter_id: int, source_ids, guidelines, generator: GroundedGenerator | None = None) -> GenerationRequest:
    if not actor.can_generate:
        raise PermissionDenied("Generation is not authorized for this actor context.")
    if isinstance(chapter_id, bool) or not isinstance(chapter_id, int) or chapter_id <= 0:
        raise ValidationError("Invalid chapter selection.")
    if not isinstance(source_ids, list) or not source_ids or len(source_ids) > settings.GENERATION_MAX_SOURCES or any(
        isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in source_ids
    ) or len(set(source_ids)) != len(source_ids):
        raise ValidationError("Invalid source selection.")
    clean_guidelines = validate_guidelines(guidelines)
    chapter = Chapter.objects.select_related("course").get(pk=chapter_id)
    if chapter.course_id not in actor.permitted_course_ids or chapter.course.teacher_id != actor.actor_id:
        raise PermissionDenied("Chapter is outside the actor's authorized course context.")
    if not set(source_ids).issubset(actor.permitted_source_ids):
        raise PermissionDenied("Selection includes an unauthorized source.")
    sources = list(ContentSource.objects.select_related("original_file").filter(pk__in=source_ids).order_by("pk"))
    if len(sources) != len(source_ids) or any(source.chapter_id != chapter.pk for source in sources):
        raise PermissionDenied("Every source must belong to the selected chapter.")
    loaded_sources = []
    total_characters = 0
    for source in sources:
        extraction, pages = _load_reviewed_pages(source)
        total_characters += sum(len(text) for _, text in pages)
        if total_characters > settings.GENERATION_MAX_TOTAL_CHARACTERS:
            raise ValidationError("Selected reviewed text exceeds the generation resource limit.")
        loaded_sources.append((source, extraction, pages))
    digest_payload = {
        "chapter_id": chapter.pk,
        "guidelines": clean_guidelines,
        "sources": [(source.pk, extraction.version, [page.text_sha256 for page, _ in pages]) for source, extraction, pages in loaded_sources],
    }
    digest = hashlib.sha256(json.dumps(digest_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    provider = generator or DeterministicExtractiveGenerator()
    provider_key = _bounded_text(provider.key, "generator_key", 64, required=True)
    request = GenerationRequest.objects.create(
        chapter=chapter, requested_by_id=actor.actor_id, guidelines=clean_guidelines,
        generator_key=provider_key, input_sha256=digest,
    )
    page_snapshots = []
    for source, extraction, pages in loaded_sources:
        source_snapshot = GenerationSourceSnapshot.objects.create(
            generation=request, source=source, extraction=extraction,
            source_file_sha256=source.original_file.sha256,
            extraction_version=extraction.version, source_title=source.title,
        )
        for page, text in pages:
            page_snapshots.append(GenerationPageSnapshot.objects.create(
                source_snapshot=source_snapshot, extracted_page=page, page_number=page.page_number,
                text=text, text_sha256=page.text_sha256,
            ))
    generated = provider.generate(tuple(page_snapshots), clean_guidelines)
    if not generated:
        raise ValidationError("Generator returned no grounded slides.")
    for position, result in enumerate(generated, start=1):
        if not result.claims or not result.narration:
            raise ValidationError("Unsupported generator output failed closed.")
        slide = SlideDraft.objects.create(generation=request, position=position)
        revision = SlideRevision.objects.create(slide=slide, version=1, title=_bounded_text(result.title, "title", 200, required=True), created_by_actor_id=actor.actor_id)
        _store_grounded_items(revision, result.claims, result.narration)
    return request


def _store_grounded_items(revision, claims, narration):
    allowed_pages = {
        page.pk: page for page in GenerationPageSnapshot.objects.filter(source_snapshot__generation=revision.slide.generation)
    }
    for model, related, items in ((SlideClaim, "claim", claims), (NarrationStatement, "narration_statement", narration)):
        for position, item in enumerate(items, start=1):
            page = allowed_pages.get(item.page_snapshot_id)
            if page is None or not (0 <= item.start_offset < item.end_offset <= len(page.text)):
                raise ValidationError("Source reference is outside the immutable input snapshot.")
            supported = page.text[item.start_offset:item.end_offset]
            text = _bounded_text(item.text, "text", 600, required=True)
            if text != supported:
                raise ValidationError("Unsupported content failed closed.")
            target = model.objects.create(revision=revision, position=position, text=text)
            SourceReference.objects.create(
                **{related: target}, page_snapshot=page, start_offset=item.start_offset, end_offset=item.end_offset,
                supported_text_sha256=hashlib.sha256(supported.encode()).hexdigest(),
            )


def _parse_revision_items(raw, field):
    if not isinstance(raw, list) or not raw or len(raw) > settings.GENERATION_MAX_CLAIMS:
        raise ValidationError({field: "Must be a non-empty bounded list."})
    result = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"text", "page_snapshot_id", "start_offset", "end_offset"}:
            raise ValidationError({field: "Every item requires text and one source range."})
        values = (item["page_snapshot_id"], item["start_offset"], item["end_offset"])
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise ValidationError({field: "Source ranges must be integers."})
        result.append(GroundedText(item["text"], *values))
    return tuple(result)


@transaction.atomic
def revise_slide(*, actor: GenerationActorContext, slide_id: int, title, claims, narration) -> SlideRevision:
    workflow = LectureWorkflow.objects.select_for_update().filter(
        generation__slides__pk=slide_id
    ).first()
    slide = SlideDraft.objects.select_for_update().select_related("generation__chapter").get(pk=slide_id)
    if (
        not actor.can_review
        or slide.generation.requested_by_id != actor.actor_id
        or slide.generation.chapter.course_id not in actor.permitted_course_ids
    ):
        raise PermissionDenied("Only the requesting teacher may revise this slide.")
    version = slide.current_version + 1
    revision = SlideRevision.objects.create(
        slide=slide, version=version, title=_bounded_text(title, "title", 200, required=True),
        created_by_actor_id=actor.actor_id,
    )
    _store_grounded_items(revision, _parse_revision_items(claims, "claims"), _parse_revision_items(narration, "narration"))
    slide.current_version = version
    slide.approved_revision = None
    slide.save(update_fields=("current_version", "approved_revision"))
    from .workflow import invalidate_workflow_for_slide_revision

    invalidate_workflow_for_slide_revision(
        workflow=workflow,
        actor_identity_reference=f"user:{actor.actor_id}",
        slide_id=slide.pk,
        revision_version=version,
    )
    _refresh_generation_status(slide.generation_id)
    return revision


def _verify_revision_grounding(revision):
    for relation in (revision.claims.all(), revision.narration_statements.all()):
        if not relation.exists():
            raise ValidationError("Approval requires factual content and narration.")
        for item in relation:
            references = list(item.references.select_related("page_snapshot"))
            if not references:
                raise ValidationError("Approval requires provenance for every statement.")
            for reference in references:
                supported = reference.page_snapshot.text[reference.start_offset:reference.end_offset]
                if supported != item.text or hashlib.sha256(supported.encode()).hexdigest() != reference.supported_text_sha256:
                    raise ValidationError("Approval failed because provenance is invalid.")


@transaction.atomic
def approve_slide(*, actor: GenerationActorContext, slide_id: int) -> CanonicalNarrationSnapshot:
    slide = SlideDraft.objects.select_for_update().select_related("generation__chapter").get(pk=slide_id)
    if (
        not actor.can_review
        or slide.generation.requested_by_id != actor.actor_id
        or slide.generation.chapter.course_id not in actor.permitted_course_ids
    ):
        raise PermissionDenied("Only the requesting teacher may approve this slide.")
    revision = slide.revisions.get(version=slide.current_version)
    _verify_revision_grounding(revision)
    narration = "\n".join(revision.narration_statements.values_list("text", flat=True))
    snapshot, created = CanonicalNarrationSnapshot.objects.get_or_create(
        revision=revision,
        defaults={"text": narration, "text_sha256": hashlib.sha256(narration.encode()).hexdigest(), "approved_by_actor_id": actor.actor_id},
    )
    expected_hash = hashlib.sha256(narration.encode()).hexdigest()
    if not created and (snapshot.text != narration or snapshot.text_sha256 != expected_hash):
        raise ValidationError("Existing canonical narration failed integrity validation.")
    slide.approved_revision = revision
    slide.save(update_fields=("approved_revision",))
    _refresh_generation_status(slide.generation_id)
    return snapshot


def _refresh_generation_status(generation_id):
    request = GenerationRequest.objects.select_for_update().get(pk=generation_id)
    total = request.slides.count()
    approved = request.slides.filter(approved_revision__isnull=False).count()
    request.status = GenerationRequest.Status.APPROVED if total and approved == total else (
        GenerationRequest.Status.PARTIALLY_APPROVED if approved else GenerationRequest.Status.GENERATED
    )
    request.save(update_fields=("status", "updated_at"))


def caption_for_slide(*, actor: GenerationActorContext, slide_id: int) -> CanonicalNarrationSnapshot:
    slide = SlideDraft.objects.select_related("generation__chapter", "approved_revision").get(pk=slide_id)
    if (
        not actor.can_review
        or slide.generation.requested_by_id != actor.actor_id
        or slide.generation.chapter.course_id not in actor.permitted_course_ids
        or slide.approved_revision_id is None
    ):
        raise PermissionDenied("No authorized approved narration is available.")
    return slide.approved_revision.canonical_narration
