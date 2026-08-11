import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path

from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import TestCase, override_settings

from .generation import (
    GenerationActorContext, actor_context_for_user, approve_slide,
    caption_for_slide, create_generation, revise_slide, validate_guidelines,
)
from .models import (
    CanonicalNarrationSnapshot, Chapter, ContentFile, ContentSource, Course,
    ExtractedPage, ExtractionVersion, GenerationPageSnapshot, GenerationRequest,
    SlideDraft, SourceReference,
)
from .roles import assign_administrator, assign_teacher, ensure_roles
from .views import _body


class SourceGroundedGenerationTests(TestCase):
    def setUp(self):
        ensure_roles()
        root = Path(__file__).resolve().parents[1] / "data" / "content-tools" / "tmp"
        root.mkdir(parents=True, exist_ok=True)
        self.storage = root / f"t022-test-{os.getpid()}-{uuid.uuid4().hex}"
        self.storage.mkdir()
        self.override = override_settings(CONTENT_STORAGE_ROOT=self.storage)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(lambda: shutil.rmtree(self.storage, ignore_errors=True))
        self.teacher = assign_teacher(User.objects.create_user("teacher-t022"))
        self.other = assign_teacher(User.objects.create_user("other-t022"))
        self.admin = assign_administrator(User.objects.create_user("admin-t022"))
        self.unassigned = User.objects.create_user("unassigned-t022")
        self.course = Course.objects.create(code="SYN-T022", title="Synthetic Physics", teacher=self.teacher)
        self.chapter = Chapter.objects.create(course=self.course, number=1, title="Synthetic motion")
        self.source = self.make_source(
            self.teacher,
            self.chapter,
            "Force changes motion. قوت حرکت کو بدلتی ہے۔ Energy is conserved.",
        )

    def make_source(self, owner, chapter, text, *, ready=True, reviewed=True, ocr=False, title="Synthetic source"):
        source = ContentSource.objects.create(
            chapter=chapter, source_type=ContentSource.SourceType.TEACHER,
            access_scope=ContentSource.AccessScope.OWNER_AND_ADMINS, owner=owner,
            title=title, rights_confirmed=True, rights_confirmed_by=owner,
            processing_state=ContentSource.ProcessingState.READY if ready else ContentSource.ProcessingState.REVIEW_REQUIRED,
            page_count=1,
        )
        source_hash = hashlib.sha256(f"file-{source.pk}".encode()).hexdigest()
        source_file = ContentFile.objects.create(
            source=source, original_name="synthetic.pdf", storage_key=f"originals/{source.pk}.pdf",
            extension=".pdf", media_type="application/pdf", byte_size=10, sha256=source_hash,
        )
        extraction = ExtractionVersion.objects.create(
            source=source, version=1,
            status=ExtractionVersion.Status.COMPLETE if reviewed else ExtractionVersion.Status.REVIEW_REQUIRED,
            extractor="synthetic-t022",
        )
        raw = text.encode("utf-8")
        key = f"derived/{source.pk}/v1/page-0001.txt"
        path = self.storage / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        ExtractedPage.objects.create(
            extraction=extraction, source_file=source_file, page_number=1,
            method=ExtractedPage.Method.OCR if ocr else ExtractedPage.Method.PDF_TEXT, text_storage_key=key,
            text_sha256=hashlib.sha256(raw).hexdigest(), character_count=len(text),
            requires_review=ocr and not reviewed,
            review_status=(ExtractedPage.ReviewStatus.APPROVED if ocr and reviewed else
                           ExtractedPage.ReviewStatus.PENDING if ocr else ExtractedPage.ReviewStatus.NOT_REQUIRED),
            reviewed_by=owner if ocr and reviewed else None,
            reviewed_at=source.created_at if ocr and reviewed else None,
        )
        return source

    def context(self, user=None, *, source_ids=None):
        user = user or self.teacher
        return GenerationActorContext(
            actor_id=user.pk, permitted_course_ids=frozenset({self.course.pk}),
            permitted_source_ids=frozenset({self.source.pk} if source_ids is None else source_ids),
            can_generate=True, can_review=True,
        )

    def guidelines(self, **changes):
        values = {
            "learning_objective": "Explain synthetic motion",
            "audience_level": "Class 10",
            "slide_count": 2,
            "language": "BILINGUAL",
            "tone": "NEUTRAL",
            "teaching_emphasis": "Use source wording",
        }
        values.update(changes)
        return values

    def generate(self, **changes):
        return create_generation(
            actor=changes.pop("actor", self.context()), chapter_id=changes.pop("chapter_id", self.chapter.pk),
            source_ids=changes.pop("source_ids", [self.source.pk]),
            guidelines=changes.pop("guidelines", self.guidelines()), **changes,
        )

    def revision_items(self, revision, relation="claims"):
        return [{
            "text": row.text, "page_snapshot_id": row.references.get().page_snapshot_id,
            "start_offset": row.references.get().start_offset, "end_offset": row.references.get().end_offset,
        } for row in getattr(revision, relation).all()]

    def test_generation_is_deterministic_and_preserves_urdu_english(self):
        first = self.generate()
        second = self.generate()
        self.assertEqual(first.input_sha256, second.input_sha256)
        first_text = list(first.slides.values_list("revisions__claims__text", flat=True))
        second_text = list(second.slides.values_list("revisions__claims__text", flat=True))
        self.assertEqual(first_text, second_text)
        self.assertIn("قوت حرکت کو بدلتی ہے۔", first_text)

    def test_every_claim_and_narration_statement_has_valid_page_provenance(self):
        generation = self.generate()
        for slide in generation.slides.all():
            revision = slide.revisions.get(version=1)
            for item in (*revision.claims.all(), *revision.narration_statements.all()):
                reference = item.references.select_related("page_snapshot").get()
                self.assertEqual(
                    reference.page_snapshot.text[reference.start_offset:reference.end_offset], item.text
                )
                self.assertEqual(reference.page_snapshot.page_number, 1)

    def test_missing_unreviewed_and_unauthorized_sources_are_rejected(self):
        unreviewed = self.make_source(self.teacher, self.chapter, "Pending OCR", ready=False, reviewed=False, ocr=True)
        with self.assertRaises(ValidationError):
            self.generate(source_ids=[unreviewed.pk], actor=self.context(source_ids={unreviewed.pk}))
        with self.assertRaises(PermissionDenied):
            self.generate(source_ids=[self.source.pk], actor=self.context(source_ids=set()))
        with self.assertRaises(PermissionDenied):
            self.generate(source_ids=[999999], actor=self.context(source_ids={999999}))

    def test_cross_teacher_and_cross_course_sources_are_rejected(self):
        other_course = Course.objects.create(code="OTHER-T022", title="Other", teacher=self.other)
        other_chapter = Chapter.objects.create(course=other_course, number=1, title="Other")
        hidden = self.make_source(self.other, other_chapter, "Other private facts")
        malicious_context = GenerationActorContext(
            actor_id=self.teacher.pk, permitted_course_ids=frozenset({self.course.pk}),
            permitted_source_ids=frozenset({hidden.pk}), can_generate=True, can_review=True,
        )
        with self.assertRaises(PermissionDenied):
            self.generate(source_ids=[hidden.pk], actor=malicious_context)
        other_context = GenerationActorContext(
            actor_id=self.other.pk, permitted_course_ids=frozenset({other_course.pk}),
            permitted_source_ids=frozenset({self.source.pk}), can_generate=True, can_review=True,
        )
        with self.assertRaises(PermissionDenied):
            self.generate(actor=other_context)

    def test_anonymous_unassigned_and_administrator_contexts_are_denied(self):
        for user in (AnonymousUser(), self.unassigned, self.admin):
            with self.subTest(user=str(user)):
                context = actor_context_for_user(user)
                self.assertFalse(context.can_generate)
                with self.assertRaises(PermissionDenied):
                    self.generate(actor=context)

    def test_guideline_types_ranges_unicode_controls_and_resource_limits(self):
        invalid = [
            self.guidelines(slide_count=True), self.guidelines(slide_count=31),
            self.guidelines(language="PUNJABI"), self.guidelines(tone="EXECUTE_SOURCE_INSTRUCTIONS"),
            self.guidelines(learning_objective="x" * 2001), self.guidelines(audience_level="bad\x00value"),
        ]
        for guidelines in invalid:
            with self.subTest(guidelines=guidelines), self.assertRaises(ValidationError):
                validate_guidelines(guidelines)
        with override_settings(GENERATION_MAX_TOTAL_CHARACTERS=5), self.assertRaises(ValidationError):
            self.generate()

    def test_slides_are_ordered_and_snapshots_preserve_extraction_version_and_hash(self):
        generation = self.generate()
        self.assertEqual(list(generation.slides.values_list("position", flat=True)), [1, 2])
        snapshot = generation.source_snapshots.get()
        self.assertEqual(snapshot.extraction_version, 1)
        self.assertEqual(snapshot.pages.get().text_sha256, self.source.extractions.get().pages.get().text_sha256)

    def test_teacher_revision_invalidates_approval_and_canonical_caption_tracks_only_approved_revision(self):
        generation = self.generate()
        slide = generation.slides.first()
        original = slide.revisions.get(version=1)
        first_caption = approve_slide(actor=self.context(), slide_id=slide.pk)
        self.assertEqual(caption_for_slide(actor=self.context(), slide_id=slide.pk), first_caption)
        revised = revise_slide(
            actor=self.context(), slide_id=slide.pk, title="Teacher revision",
            claims=self.revision_items(original), narration=self.revision_items(original, "narration_statements"),
        )
        slide.refresh_from_db()
        self.assertIsNone(slide.approved_revision_id)
        with self.assertRaises(PermissionDenied):
            caption_for_slide(actor=self.context(), slide_id=slide.pk)
        second_caption = approve_slide(actor=self.context(), slide_id=slide.pk)
        self.assertEqual(second_caption.revision, revised)
        self.assertEqual(CanonicalNarrationSnapshot.objects.filter(revision__slide=slide).count(), 2)

    def test_only_requesting_teacher_can_revise_or_approve_and_admin_cannot_replace_approval(self):
        slide = self.generate().slides.first()
        revision = slide.revisions.get()
        for actor in (self.context(self.other), actor_context_for_user(self.admin)):
            with self.subTest(actor=actor), self.assertRaises(PermissionDenied):
                revise_slide(actor=actor, slide_id=slide.pk, title="Denied",
                             claims=self.revision_items(revision), narration=self.revision_items(revision, "narration_statements"))
            with self.assertRaises(PermissionDenied):
                approve_slide(actor=actor, slide_id=slide.pk)

    def test_course_capability_is_rechecked_for_revision_approval_and_caption(self):
        slide = self.generate().slides.first()
        revision = slide.revisions.get()
        missing_course = GenerationActorContext(
            actor_id=self.teacher.pk, permitted_course_ids=frozenset(),
            permitted_source_ids=frozenset({self.source.pk}), can_generate=True, can_review=True,
        )
        with self.assertRaises(PermissionDenied):
            revise_slide(actor=missing_course, slide_id=slide.pk, title="Denied",
                         claims=self.revision_items(revision), narration=self.revision_items(revision, "narration_statements"))
        with self.assertRaises(PermissionDenied):
            approve_slide(actor=missing_course, slide_id=slide.pk)
        approve_slide(actor=self.context(), slide_id=slide.pk)
        with self.assertRaises(PermissionDenied):
            caption_for_slide(actor=missing_course, slide_id=slide.pk)

    def test_unsupported_revision_and_missing_provenance_fail_closed(self):
        slide = self.generate().slides.first()
        revision = slide.revisions.get()
        claims = self.revision_items(revision)
        claims[0]["text"] = "Invented unsupported fact"
        with self.assertRaises(ValidationError):
            revise_slide(actor=self.context(), slide_id=slide.pk, title="Unsafe", claims=claims,
                         narration=self.revision_items(revision, "narration_statements"))
        SourceReference.objects.filter(claim=revision.claims.first()).delete()
        with self.assertRaises(ValidationError):
            approve_slide(actor=self.context(), slide_id=slide.pk)

    def test_domain_generation_is_authentication_provider_independent(self):
        context = self.context()
        generation = self.generate(actor=context)
        self.assertEqual(generation.requested_by_id, context.actor_id)
        self.assertNotIn("User", repr(context))

    def test_json_api_is_scoped_structured_and_script_safe(self):
        injection = self.make_source(self.teacher, self.chapter, "<script>alert(1)</script> is source text.", title="Unsafe-looking synthetic")
        self.client.force_login(self.teacher)
        response = self.client.post(
            "/api/generations/", data=json.dumps({
                "chapter_id": self.chapter.pk, "source_ids": [injection.pk], "guidelines": self.guidelines(slide_count=1),
            }), content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertNotIn(b"<script>", response.content)
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.client.logout()
        self.assertEqual(self.client.get("/api/generations/").status_code, 302)

    def test_models_use_portable_fields_constraints_and_protected_provenance(self):
        self.assertEqual(connection.vendor, "sqlite")
        for model in (GenerationRequest, GenerationPageSnapshot, SlideDraft, SourceReference):
            self.assertFalse(model._meta.required_db_vendor)
            self.assertTrue(all(index.condition is None for index in model._meta.indexes))
        self.assertEqual(
            GenerationPageSnapshot._meta.get_field("extracted_page").remote_field.on_delete.__name__, "PROTECT"
        )

    def test_snapshots_revisions_and_generation_inputs_are_immutable(self):
        generation = self.generate()
        page = generation.source_snapshots.get().pages.get()
        page.text = "Changed"
        with self.assertRaises(ValueError):
            page.save()
        generation.guidelines = self.guidelines(slide_count=1)
        with self.assertRaises(ValueError):
            generation.save()
        revision = generation.slides.first().revisions.get()
        revision.title = "Changed"
        with self.assertRaises(ValueError):
            revision.save()

    @override_settings(GENERATION_MAX_REQUEST_BYTES=8)
    def test_request_body_limit_is_enforced_without_content_length(self):
        request = type("SyntheticRequest", (), {"headers": {}, "body": b'{"long":"value"}'})()
        with self.assertRaises(ValidationError):
            _body(request)
