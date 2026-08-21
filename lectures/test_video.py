import hashlib
import json
import shutil
import uuid
import zipfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
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
    RecordingCompletionItem,
    RecordingTake,
    SlideClaim,
    SlideDraft,
    SlideRevision,
    TeacherVideoReview,
    VideoEditDecision,
    VideoExportPackage,
    VideoRenderVersion,
)
from .roles import assign_administrator, assign_teacher, ensure_roles
from .video import (
    UnsupportedRenderEnvironment,
    VideoConflict,
    approve_spoken_edit,
    create_edit_decision,
    grant_admin_final_approval,
    process_next_readiness_job,
    process_render,
    record_teacher_video_review,
    render_video_path,
    request_export_package,
    request_initial_render,
    submit_for_teacher_review,
)
from .workflow import create_workflow, recording_approval_fingerprint, workflow_actor_for_user


SYNTHETIC_WEBM = b"\x1aE\xdf\xa3" + b"synthetic-t050-audio" * 16


class RemotionVideoAssemblyTests(TestCase):
    def setUp(self):
        ensure_roles()
        self.teacher = assign_teacher(User.objects.create_user("teacher-t050", password="test-password"))
        self.other_teacher = assign_teacher(
            User.objects.create_user("other-teacher-t050", password="test-password")
        )
        self.admin = assign_administrator(User.objects.create_user("admin-t050", password="test-password"))
        self.other_admin = assign_administrator(
            User.objects.create_user("other-admin-t050", password="test-password")
        )
        self.course = Course.objects.create(
            code="SYN-T050",
            title="Synthetic Video Assembly",
            class_name="Class 9",
            subject_name="Physics / طبیعیات",
            teacher=self.teacher,
        )
        self.chapter = Chapter.objects.create(course=self.course, number=1, title="Synthetic motion")
        self.generation = GenerationRequest.objects.create(
            chapter=self.chapter,
            requested_by=self.teacher,
            guidelines={"synthetic": True},
            generator_key="synthetic-t050",
            input_sha256="5" * 64,
            status=GenerationRequest.Status.APPROVED,
        )
        source = ContentSource.objects.create(
            chapter=self.chapter,
            source_type=ContentSource.SourceType.INSTITUTIONAL,
            access_scope=ContentSource.AccessScope.AUTHORIZED_TEACHERS,
            title="Synthetic T050 source",
            rights_confirmed=True,
            rights_confirmed_by=self.teacher,
            processing_state=ContentSource.ProcessingState.READY,
        )
        extraction = ExtractionVersion.objects.create(
            source=source,
            version=1,
            status=ExtractionVersion.Status.COMPLETE,
            extractor="synthetic-t050",
        )
        GenerationSourceSnapshot.objects.create(
            generation=self.generation,
            source=source,
            extraction=extraction,
            source_file_sha256="a" * 64,
            extraction_version=1,
            source_title=source.title,
        )
        self.slides = []
        for position in (1, 2):
            slide = SlideDraft.objects.create(generation=self.generation, position=position)
            revision = SlideRevision.objects.create(
                slide=slide,
                version=1,
                title=f"Synthetic slide {position} / مصنوعی",
                created_by_actor_id=self.teacher.pk,
            )
            SlideClaim.objects.create(
                revision=revision, position=1, text=f"Synthetic claim {position} only"
            )
            narration = f"Synthetic approved narration {position}. مصنوعی اردو عبارت۔"
            CanonicalNarrationSnapshot.objects.create(
                revision=revision,
                text=narration,
                text_sha256=hashlib.sha256(narration.encode("utf-8")).hexdigest(),
                approved_by_actor_id=self.teacher.pk,
            )
            slide.approved_revision = revision
            slide.save(update_fields=("approved_revision",))
            self.slides.append(slide)
        self.teacher_actor = workflow_actor_for_user(self.teacher)
        self.admin_actor = workflow_actor_for_user(self.admin)
        self.workflow = create_workflow(
            actor=self.teacher_actor,
            generation_id=self.generation.pk,
            idempotency_key="workflow:t050",
        )
        fingerprint = recording_approval_fingerprint(self.workflow)
        self.workflow.state = LectureWorkflow.State.RECORDING_READY
        self.workflow.version = 5
        self.workflow.slide_approval_fingerprint = fingerprint
        self.workflow._domain_service_write = True
        self.workflow.save()
        del self.workflow._domain_service_write

        token = uuid.uuid4().hex
        self.recording_root = Path("data/recordings") / f"synthetic-t050-{token}"
        self.video_root = Path("data/lectures") / f"synthetic-t050-video-{token}"
        self.export_root = Path("data/exports") / f"synthetic-t050-export-{token}"
        self.recording_root.mkdir(parents=True)
        completion = RecordingCompletion.objects.create(
            workflow=self.workflow,
            reference=f"recording:synthetic-{token[:24]}",
            slide_approval_fingerprint=fingerprint,
            completed_by=self.teacher,
        )
        for slide in self.slides:
            key = f"workflow-{self.workflow.pk}/slide-{slide.pk}/take.webm"
            path = self.recording_root / Path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            content = SYNTHETIC_WEBM + bytes([slide.position])
            path.write_bytes(content)
            take = RecordingTake.objects.create(
                workflow=self.workflow,
                slide_revision=slide.approved_revision,
                canonical_narration=slide.approved_revision.canonical_narration,
                take_number=1,
                storage_key=key,
                original_name="synthetic.webm",
                extension=".webm",
                media_type="audio/webm",
                byte_size=len(content),
                duration_ms=1500,
                sha256=hashlib.sha256(content).hexdigest(),
                recorded_by=self.teacher,
            )
            RecordingCompletionItem.objects.create(
                completion=completion,
                position=slide.position,
                slide_revision=slide.approved_revision,
                take=take,
            )
        self.workflow.recording_reference = completion.reference
        self.workflow._domain_service_write = True
        self.workflow.save(update_fields=("recording_reference",))
        del self.workflow._domain_service_write
        self.override = override_settings(
            RECORDING_STORAGE_ROOT=self.recording_root,
            VIDEO_STORAGE_ROOT=self.video_root,
            VIDEO_EXPORT_ROOT=self.export_root,
            VIDEO_RENDER_ADAPTER_ENABLED=True,
            VIDEO_RENDER_EVALUATION_ACK=True,
        )
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        for root in (self.recording_root, self.video_root, self.export_root):
            if root.exists():
                shutil.rmtree(root)

    def fake_render(self, manifest_path, output_path):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["compositionId"], "LectureAssembly")
        self.assertIn("مصنوعی", manifest["slides"][0]["title"])
        output_path.write_bytes(b"synthetic-mp4-only")

    def rendered(self):
        item = request_initial_render(actor=self.admin_actor, workflow_id=self.workflow.pk)
        with patch("lectures.video._invoke_adapter", side_effect=self.fake_render):
            process_render(item.pk)
        item.refresh_from_db()
        self.workflow.refresh_from_db()
        return item

    def ready_for_teacher(self):
        item = self.rendered()
        submit_for_teacher_review(
            actor=self.admin_actor, workflow_id=self.workflow.pk, render_id=item.pk
        )
        process_next_readiness_job()
        self.workflow.refresh_from_db()
        return item

    def test_authorization_and_immutable_input_snapshot_preserve_raw_recordings(self):
        with self.assertRaises(PermissionDenied):
            request_initial_render(actor=self.teacher_actor, workflow_id=self.workflow.pk)
        before = {path: path.read_bytes() for path in self.recording_root.rglob("*.webm")}
        render = request_initial_render(actor=self.admin_actor, workflow_id=self.workflow.pk)
        self.assertEqual(render.render_input.items.count(), 2)
        self.assertEqual(before, {path: path.read_bytes() for path in self.recording_root.rglob("*.webm")})
        render.render_input.recording_reference = "recording:changed"
        with self.assertRaises(ValueError):
            render.render_input.save()
        with self.assertRaises(ValueError):
            render.delete()

    def test_adapter_fails_closed_and_storage_paths_cannot_escape(self):
        render = request_initial_render(actor=self.admin_actor, workflow_id=self.workflow.pk)
        with override_settings(VIDEO_RENDER_ADAPTER_ENABLED=False), self.assertRaises(
            UnsupportedRenderEnvironment
        ):
            process_render(render.pk)
        VideoRenderVersion.objects.filter(pk=render.pk).update(video_storage_key="../escape.mp4")
        render.refresh_from_db()
        with self.assertRaises(ValidationError):
            render_video_path(render)
        self.assertFalse((Path("data") / "escape.mp4").exists())

    def test_visual_edits_create_new_versions_without_overwriting_history(self):
        first = self.rendered()
        first_path = render_video_path(first)
        first_bytes = first_path.read_bytes()
        decision, second = create_edit_decision(
            actor=self.admin_actor,
            workflow_id=self.workflow.pk,
            base_render_id=first.pk,
            decision_type=VideoEditDecision.DecisionType.CAPTION_LAYOUT,
            payload={"position": "top", "font_scale": 110},
        )
        self.assertEqual((decision.base_render_id, second.parent_id, second.version), (first.pk, first.pk, 2))
        with patch("lectures.video._invoke_adapter", side_effect=self.fake_render):
            process_render(second.pk)
        self.assertEqual(first_path.read_bytes(), first_bytes)
        self.assertNotEqual(first.video_storage_key, second.video_storage_key)
        with self.assertRaises(VideoConflict):
            create_edit_decision(
                actor=self.admin_actor,
                workflow_id=self.workflow.pk,
                base_render_id=first.pk,
                decision_type=VideoEditDecision.DecisionType.BRANDING,
                payload={"accent_color": "#112233", "institution_name": "Synthetic"},
            )

    def test_spoken_removal_requires_exact_timestamped_transcript_and_teacher_approval(self):
        first = self.rendered()
        narration = first.render_input.items.get(position=1)
        payload = {
            "slide_position": 1,
            "start_ms": 200,
            "end_ms": 500,
            "transcript_excerpt": "approved narration 1.",
            "narration_sha256": narration.narration_sha256,
            "reason": "Synthetic correction evidence",
        }
        with self.assertRaises(ValidationError):
            create_edit_decision(
                actor=self.admin_actor,
                workflow_id=self.workflow.pk,
                base_render_id=first.pk,
                decision_type=VideoEditDecision.DecisionType.SPOKEN_CONTENT_REMOVAL,
                payload={**payload, "transcript_excerpt": "not in the canonical narration"},
            )
        decision, derived = create_edit_decision(
            actor=self.admin_actor,
            workflow_id=self.workflow.pk,
            base_render_id=first.pk,
            decision_type=VideoEditDecision.DecisionType.SPOKEN_CONTENT_REMOVAL,
            payload=payload,
        )
        self.assertIsNone(derived)
        with self.assertRaises(PermissionDenied):
            approve_spoken_edit(
                actor=workflow_actor_for_user(self.other_teacher), decision_id=decision.pk
            )
        second = approve_spoken_edit(actor=self.teacher_actor, decision_id=decision.pk)
        self.assertEqual(second.parent_id, first.pk)
        self.assertEqual(second.applied_edits.get().decision_id, decision.pk)

    def test_review_and_export_gates_use_exact_t030_jobs_and_approval_order(self):
        render = self.ready_for_teacher()
        self.assertEqual(self.workflow.state, LectureWorkflow.State.DRAFT_VIDEO_READY)
        self.assertEqual(self.workflow.draft_video_reference, render.reference)
        with self.assertRaises(VideoConflict):
            grant_admin_final_approval(
                actor=self.admin_actor, workflow_id=self.workflow.pk, render_id=render.pk
            )
        review = record_teacher_video_review(
            actor=self.teacher_actor,
            workflow_id=self.workflow.pk,
            render_id=render.pk,
            decision=TeacherVideoReview.Decision.APPROVED,
            notes="Synthetic Urdu/English video reviewed locally.",
        )
        approval = grant_admin_final_approval(
            actor=self.admin_actor, workflow_id=self.workflow.pk, render_id=render.pk
        )
        self.assertEqual(approval.teacher_review, review)
        package = request_export_package(
            actor=self.admin_actor, workflow_id=self.workflow.pk, render_id=render.pk
        )
        self.assertEqual(package.job.job_type, "EXPORT_READINESS")
        process_next_readiness_job()
        package.refresh_from_db()
        self.workflow.refresh_from_db()
        self.assertEqual(package.status, VideoExportPackage.Status.READY)
        self.assertEqual(self.workflow.state, LectureWorkflow.State.EXPORT_READY)
        package_root = self.export_root / Path(package.storage_key)
        self.assertEqual(
            {path.name for path in package_root.iterdir()},
            {"lecture.mp4", "slides.pptx", "captions.srt", "metadata.json", "package-manifest.json"},
        )
        captions = (package_root / "captions.srt").read_text(encoding="utf-8-sig")
        self.assertIn("مصنوعی اردو عبارت", captions)
        self.assertFalse(json.loads((package_root / "metadata.json").read_text())["upload_performed"])
        self.assertTrue(zipfile.is_zipfile(package_root / "slides.pptx"))

    def test_stale_recording_or_approval_blocks_render_eligibility_but_retains_versions(self):
        first = self.rendered()
        LectureWorkflow.objects.filter(pk=self.workflow.pk).update(recording_reference="recording:stale")
        with self.assertRaises(VideoConflict):
            create_edit_decision(
                actor=self.admin_actor,
                workflow_id=self.workflow.pk,
                base_render_id=first.pk,
                decision_type=VideoEditDecision.DecisionType.TRANSITION_TIMING,
                payload={"transition_ms": 200, "hold_after_ms": 100},
            )
        self.assertTrue(render_video_path(first).exists())
        self.assertEqual(VideoRenderVersion.objects.count(), 1)

    def test_http_authorization_and_fail_closed_worker_boundary(self):
        admin_client = Client()
        admin_client.force_login(self.admin)
        response = admin_client.get("/admin/video-assembly/")
        self.assertEqual(response.status_code, 200)
        teacher_client = Client()
        teacher_client.force_login(self.teacher)
        self.assertEqual(teacher_client.post(f"/api/video/workflows/{self.workflow.pk}/renders/", data="{}", content_type="application/json").status_code, 403)
        self.assertEqual(teacher_client.get("/teacher/video-review/").status_code, 200)
        self.assertEqual(
            admin_client.post(
                "/api/workflow-jobs/claim/",
                data=json.dumps({"lease_seconds": 60}),
                content_type="application/json",
            ).status_code,
            403,
        )

    def test_edit_schema_rejects_commands_paths_and_unexpected_fields(self):
        first = self.rendered()
        invalid = (
            (VideoEditDecision.DecisionType.BRANDING, {"accent_color": "red", "institution_name": "x"}),
            (VideoEditDecision.DecisionType.TRANSITION_TIMING, {"transition_ms": "--help", "hold_after_ms": 0}),
            (VideoEditDecision.DecisionType.CAPTION_LAYOUT, {"position": "../../outside", "font_scale": 100}),
            (VideoEditDecision.DecisionType.BRANDING, {"accent_color": "#112233", "institution_name": "x", "command": "calc.exe"}),
        )
        for decision_type, payload in invalid:
            with self.subTest(decision_type=decision_type), self.assertRaises(ValidationError):
                create_edit_decision(
                    actor=self.admin_actor,
                    workflow_id=self.workflow.pk,
                    base_render_id=first.pk,
                    decision_type=decision_type,
                    payload=payload,
                )
