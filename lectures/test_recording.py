import shutil
import uuid
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from .models import (
    CanonicalNarrationSnapshot,
    Chapter,
    ContentSource,
    Course,
    ExtractionVersion,
    GenerationRequest,
    GenerationSourceSnapshot,
    LectureWorkflow,
    RecordingCompletion,
    RecordingSelection,
    RecordingSelectionEvent,
    RecordingTake,
    SlideDraft,
    SlideRevision,
    WorkflowAuditEvent,
)
from .recording import (
    RecordingConflict,
    complete_recording,
    create_take,
    open_recording,
    select_take,
)
from .roles import assign_teacher, ensure_roles
from .workflow import (
    create_workflow,
    invalidate_workflow_for_slide_revision,
    recording_approval_fingerprint,
    workflow_actor_for_user,
)


WEBM = b"\x1aE\xdf\xa3" + b"synthetic-audio-only" * 8


class InterruptedUpload(SimpleUploadedFile):
    def chunks(self, chunk_size=None):
        yield WEBM[:32]
        raise OSError("synthetic interrupted stream")


class TeacherRecordingPortalTests(TestCase):
    def setUp(self):
        ensure_roles()
        self.teacher = assign_teacher(User.objects.create_user("teacher-t040", password="test-password"))
        self.other = assign_teacher(User.objects.create_user("other-t040", password="test-password"))
        self.course = Course.objects.create(
            code="SYN-T040", title="Synthetic Recording", class_name="Class 9",
            subject_name="Physics · طبیعیات", teacher=self.teacher,
        )
        self.chapter = Chapter.objects.create(course=self.course, number=2, title="Synthetic Waves")
        self.generation = self._generation(self.teacher, self.chapter, "primary")
        self.actor = workflow_actor_for_user(self.teacher)
        self.other_actor = workflow_actor_for_user(self.other)
        self.workflow = create_workflow(
            actor=self.actor, generation_id=self.generation.pk, idempotency_key="workflow:t040"
        )
        fingerprint = recording_approval_fingerprint(self.workflow)
        self.workflow.state = LectureWorkflow.State.TEACHER_SLIDE_NARRATION_APPROVED
        self.workflow.version = 3
        self.workflow.slide_approval_fingerprint = fingerprint
        self.workflow._domain_service_write = True
        self.workflow.save()
        del self.workflow._domain_service_write
        WorkflowAuditEvent.objects.create(
            workflow=self.workflow, sequence=2, actor_type="SYSTEM_WORKER",
            actor_identity_reference="worker:synthetic-t040", previous_state="SOURCE_CONTENT_READY",
            new_state="SLIDE_NARRATION_DRAFT", reason_code="DRAFT_AVAILABLE",
            idempotency_key="workflow:t040:draft",
        )
        WorkflowAuditEvent.objects.create(
            workflow=self.workflow, sequence=3, actor_type="TEACHER",
            actor_identity_reference=f"user:{self.teacher.pk}", previous_state="SLIDE_NARRATION_DRAFT",
            new_state="TEACHER_SLIDE_NARRATION_APPROVED",
            reason_code="TEACHER_APPROVED_CURRENT_DRAFT", idempotency_key="workflow:t040:approved",
        )
        self.root = Path("data/recordings") / f"synthetic-test-{uuid.uuid4().hex}"
        self.settings_override = override_settings(
            RECORDING_STORAGE_ROOT=self.root,
            RECORDING_MAX_UPLOAD_BYTES=1024,
            RECORDING_MIN_DURATION_MS=250,
            RECORDING_MAX_DURATION_MS=60_000,
            RECORDING_MAX_REQUEST_BYTES=65_536,
        )
        self.settings_override.enable()

    def tearDown(self):
        self.settings_override.disable()
        if self.root.exists():
            shutil.rmtree(self.root)

    def _generation(self, teacher, chapter, suffix):
        generation = GenerationRequest.objects.create(
            chapter=chapter, requested_by=teacher, guidelines={"synthetic": True},
            generator_key="synthetic-t040", input_sha256=(suffix.encode().hex() + "0" * 64)[:64],
            status=GenerationRequest.Status.APPROVED,
        )
        source = ContentSource.objects.create(
            chapter=chapter, source_type=ContentSource.SourceType.INSTITUTIONAL,
            access_scope=ContentSource.AccessScope.AUTHORIZED_TEACHERS,
            title=f"Synthetic source {suffix}", rights_confirmed=True,
            rights_confirmed_by=teacher, processing_state=ContentSource.ProcessingState.READY,
        )
        extraction = ExtractionVersion.objects.create(
            source=source, version=1, status=ExtractionVersion.Status.COMPLETE,
            extractor="synthetic-t040",
        )
        GenerationSourceSnapshot.objects.create(
            generation=generation, source=source, extraction=extraction,
            source_file_sha256="a" * 64, extraction_version=1, source_title=source.title,
        )
        for position in (1, 2):
            slide = SlideDraft.objects.create(generation=generation, position=position)
            revision = SlideRevision.objects.create(
                slide=slide, version=1, title=f"Synthetic slide {position}",
                created_by_actor_id=teacher.pk,
            )
            CanonicalNarrationSnapshot.objects.create(
                revision=revision, text=f"Synthetic Urdu English narration {position} · اردو",
                text_sha256=str(position) * 64, approved_by_actor_id=teacher.pk,
            )
            slide.approved_revision = revision
            slide.save(update_fields=("approved_revision",))
        return generation

    def upload(self, name="take.webm", content=WEBM, media_type="audio/webm"):
        return SimpleUploadedFile(name, content, content_type=media_type)

    def open(self):
        self.workflow.refresh_from_db()
        return open_recording(
            actor=self.actor, workflow_id=self.workflow.pk, expected_version=self.workflow.version
        )

    def take(self, slide, **kwargs):
        slide.refresh_from_db()
        return create_take(
            actor=self.actor, workflow_id=self.workflow.pk, slide_id=slide.pk,
            expected_revision_id=slide.approved_revision_id,
            upload=kwargs.pop("upload", self.upload()), duration_ms=kwargs.pop("duration_ms", 1200),
            filename=kwargs.pop("filename", "take.webm"),
            media_type=kwargs.pop("media_type", "audio/webm"), **kwargs,
        )

    def test_recording_requires_current_approval_and_exact_assigned_teacher(self):
        slide = self.generation.slides.first()
        with self.assertRaises(ValidationError):
            self.take(slide)
        with self.assertRaises(PermissionDenied):
            open_recording(
                actor=self.other_actor, workflow_id=self.workflow.pk, expected_version=self.workflow.version
            )
        opened = self.open()
        self.assertEqual(opened.state, LectureWorkflow.State.RECORDING_PENDING)
        with self.assertRaises(PermissionDenied):
            create_take(
                actor=self.other_actor, workflow_id=self.workflow.pk, slide_id=slide.pk,
                expected_revision_id=slide.approved_revision_id, upload=self.upload(), duration_ms=1000,
                filename="take.webm", media_type="audio/webm",
            )
        event = self.workflow.audit_events.get(sequence=4)
        self.assertEqual(event.reason_code, "TEACHER_OPENED_RECORDING")
        self.assertEqual(event.actor_type, "TEACHER")

    def test_takes_and_retakes_are_immutable_separate_and_selection_is_audited(self):
        self.open()
        slide = self.generation.slides.first()
        first = self.take(slide)
        second = create_take(
            actor=self.actor, workflow_id=self.workflow.pk, slide_id=slide.pk,
            expected_revision_id=slide.approved_revision_id, upload=self.upload(content=WEBM + b"retake"),
            duration_ms=1800, filename="retake.webm", media_type="audio/webm",
        )
        self.assertEqual((first.take_number, second.take_number), (1, 2))
        self.assertNotEqual(first.storage_key, second.storage_key)
        self.assertTrue((self.root / Path(first.storage_key)).exists())
        selection = RecordingSelection.objects.get(workflow=self.workflow, slide=slide)
        self.assertEqual(selection.current_take, second)
        self.assertEqual(list(selection.events.values_list("take_id", flat=True)), [first.pk, second.pk])
        first.duration_ms = 9999
        with self.assertRaises(ValueError):
            first.save()
        with self.assertRaises(ValueError):
            first.delete()
        select_take(
            actor=self.actor, workflow_id=self.workflow.pk, slide_id=slide.pk, take_id=first.pk,
            expected_revision_id=slide.approved_revision_id,
        )
        selection.refresh_from_db()
        self.assertEqual(selection.current_take, first)
        self.assertEqual(RecordingSelectionEvent.objects.filter(selection=selection).count(), 3)

    def test_upload_validation_and_interruption_leave_no_take_or_partial_file(self):
        self.open()
        slide = self.generation.slides.first()
        invalid = (
            dict(upload=self.upload(name="take.exe"), filename="take.exe"),
            dict(upload=self.upload(content=b"not-webm-content"), filename="take.webm"),
            dict(upload=self.upload(media_type="audio/mpeg"), media_type="audio/mpeg"),
            dict(upload=self.upload(), duration_ms=100),
            dict(upload=self.upload(content=WEBM * 20)),
        )
        for case in invalid:
            with self.subTest(case=case), self.assertRaises(ValidationError):
                self.take(slide, **case)
        interrupted = InterruptedUpload("take.webm", WEBM, content_type="audio/webm")
        with self.assertRaises(OSError):
            self.take(slide, upload=interrupted)
        self.assertFalse(RecordingTake.objects.exists())
        self.assertFalse(any(path.is_file() for path in self.root.rglob("*.part")))

    def test_failed_selection_rolls_back_take_and_removes_promoted_file(self):
        self.open()
        slide = self.generation.slides.first()
        with patch("lectures.recording.select_take", side_effect=ValidationError("synthetic failure")):
            with self.assertRaises(ValidationError):
                self.take(slide)
        self.assertFalse(RecordingTake.objects.exists())
        self.assertFalse(any(path.is_file() for path in self.root.rglob("*.webm")))
        self.assertFalse(any(path.is_file() for path in self.root.rglob("*.part")))

    def test_slide_revision_makes_old_take_stale_without_removing_audit_history(self):
        self.open()
        slide = self.generation.slides.first()
        old_take = self.take(slide)
        revision = SlideRevision.objects.create(
            slide=slide, version=2, title="Synthetic revised slide", created_by_actor_id=self.teacher.pk
        )
        CanonicalNarrationSnapshot.objects.create(
            revision=revision, text="Revised synthetic narration", text_sha256="b" * 64,
            approved_by_actor_id=self.teacher.pk,
        )
        slide.current_version = 2
        slide.approved_revision = revision
        slide.save(update_fields=("current_version", "approved_revision"))
        invalidate_workflow_for_slide_revision(
            workflow=LectureWorkflow.objects.get(pk=self.workflow.pk),
            actor_identity_reference=f"user:{self.teacher.pk}", slide_id=slide.pk,
            revision_version=2,
        )
        self.workflow.refresh_from_db()
        self.assertEqual(self.workflow.state, LectureWorkflow.State.SLIDE_NARRATION_DRAFT)
        with self.assertRaises((ValidationError, RecordingConflict)):
            create_take(
                actor=self.actor, workflow_id=self.workflow.pk, slide_id=slide.pk,
                expected_revision_id=old_take.slide_revision_id, upload=self.upload(), duration_ms=1000,
                filename="stale.webm", media_type="audio/webm",
            )
        self.assertTrue(RecordingTake.objects.filter(pk=old_take.pk).exists())
        self.assertTrue((self.root / Path(old_take.storage_key)).exists())

    def test_completion_requires_current_selected_take_for_every_slide_and_is_auditable(self):
        opened = self.open()
        slides = list(self.generation.slides.order_by("position"))
        self.take(slides[0])
        revision_ids = [slide.approved_revision_id for slide in slides]
        with self.assertRaises(ValidationError):
            complete_recording(
                actor=self.actor, workflow_id=self.workflow.pk, expected_version=opened.version,
                expected_revision_ids=revision_ids,
            )
        self.take(slides[1])
        completion = complete_recording(
            actor=self.actor, workflow_id=self.workflow.pk, expected_version=opened.version,
            expected_revision_ids=revision_ids,
        )
        self.workflow.refresh_from_db()
        self.assertEqual(self.workflow.state, LectureWorkflow.State.RECORDING_READY)
        self.assertEqual(self.workflow.recording_reference, completion.reference)
        self.assertEqual(completion.items.count(), 2)
        event = self.workflow.audit_events.get(sequence=5)
        self.assertEqual((event.actor_type, event.reason_code), ("TEACHER", "TEACHER_COMPLETED_RECORDING"))
        completion.reference = "recording:changed"
        with self.assertRaises(ValueError):
            completion.save()

    def test_cross_course_ui_api_media_and_csrf_are_isolated(self):
        self.open()
        slide = self.generation.slides.first()
        take = self.take(slide)
        teacher_client = Client(enforce_csrf_checks=True)
        teacher_client.login(username="teacher-t040", password="test-password")
        detail = teacher_client.get(f"/teacher/recordings/{self.workflow.pk}/")
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Synthetic Urdu English narration")
        csrf = detail.cookies["csrftoken"].value
        without_csrf = teacher_client.post(
            f"/api/recordings/{self.workflow.pk}/slides/{slide.pk}/select/",
            data='{"take_id":1,"expected_revision_id":1}', content_type="application/json",
        )
        self.assertEqual(without_csrf.status_code, 403)
        media = teacher_client.get(f"/teacher/recording-takes/{take.pk}/media/")
        self.assertEqual(media.status_code, 200)
        media.close()
        other_client = Client()
        other_client.login(username="other-t040", password="test-password")
        self.assertEqual(other_client.get(f"/teacher/recordings/{self.workflow.pk}/").status_code, 404)
        denied_media = other_client.get(f"/teacher/recording-takes/{take.pk}/media/")
        self.assertEqual(denied_media.status_code, 404)
        response = teacher_client.post(
            f"/api/recordings/{self.workflow.pk}/slides/{slide.pk}/select/",
            data=f'{{"take_id":{take.pk},"expected_revision_id":{slide.approved_revision_id}}}',
            content_type="application/json", HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_stale_and_private_api_errors_are_bounded(self):
        self.open()
        client = Client()
        client.login(username="teacher-t040", password="test-password")
        response = client.post(
            f"/api/recordings/{self.workflow.pk}/complete/",
            data={"expected_version": 999, "expected_revision_ids": []},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertNotIn(str(self.root), response.content.decode())
        self.assertNotIn("storage_key", response.content.decode())

    def test_postgresql_portable_recording_models_avoid_backend_specific_fields(self):
        model_names = (
            "RecordingTake", "RecordingSelection", "RecordingSelectionEvent",
            "RecordingCompletion", "RecordingCompletionItem",
        )
        migration = Path("lectures/migrations/0007_teacher_recording_portal.py").read_text(encoding="utf-8")
        for name in model_names:
            self.assertIn(name, migration)
        for unsupported in ("ArrayField", "HStoreField", "postgres.fields", "RunSQL"):
            self.assertNotIn(unsupported, migration)
