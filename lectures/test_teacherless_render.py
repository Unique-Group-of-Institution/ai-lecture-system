import hashlib
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .models import (
    CanonicalNarrationSnapshot,
    Chapter,
    ContentSource,
    Course,
    ExtractionVersion,
    GenerationRequest,
    GenerationSourceSnapshot,
    SlideClaim,
    SlideDraft,
    SlideRevision,
    TeacherlessRender,
)
from .roles import assign_administrator, assign_teacher, ensure_roles
from .teacherless_render import (
    _mp4_duration_ms,
    _resolve_relative,
    process_teacherless_render,
    request_teacherless_render,
    teacherless_render_payload,
)
from .video import RenderPipelineError, UnsupportedRenderEnvironment

from datetime import timedelta

RENDER_ENV = dict(
    VIDEO_RENDER_ADAPTER_ENABLED=True,
    VIDEO_RENDER_EVALUATION_ACK=True,
    VIDEO_RENDER_DEPLOYMENT_MODE="local-evaluation",
    VIDEO_RENDER_EXECUTION_HOST="127.0.0.1",
    VIDEO_RENDER_RAILWAY_ENVIRONMENT=False,
)


def stub_manifest():
    return {
        "schemaVersion": 1,
        "compositionId": "TeacherlessLecture",
        "fps": 30,
        "width": 1920,
        "height": 1080,
        "renderReference": "test-reference",
        "branding": {
            "institutionName": "UGI",
            "accentColor": "#1F6FEB",
            "backgroundColor": "#0D1117",
        },
        "scenes": [
            {
                "id": "scene-1",
                "kind": "concept",
                "title": "Current / کرنٹ",
                "durationMs": 1000,
                "elements": [],
                "animations": [],
                "narration": {
                    "text": "First synthetic narration.",
                    "language": "SOURCE",
                    "estimatedDurationMs": 700,
                },
            },
            {
                "id": "scene-2",
                "kind": "recap",
                "title": "Recap",
                "durationMs": 1500,
                "elements": [],
                "animations": [],
                "narration": {
                    "text": "Second synthetic narration.",
                    "language": "SOURCE",
                    "estimatedDurationMs": 900,
                },
            },
        ],
        "qa": {},
    }


class StubSpeechProvider:
    key = "stub-tts"

    def synthesize(self, *, scene_id, text, language, output_path):
        class Artifact:
            duration_ms = 600

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"RIFF-fake-wav")
        return Artifact()


class TeacherlessFixtureMixin:
    def build_approved_generation(self, teacher):
        source = ContentSource.objects.create(
            chapter=self.chapter,
            source_type=ContentSource.SourceType.INSTITUTIONAL,
            access_scope=ContentSource.AccessScope.AUTHORIZED_TEACHERS,
            title="Synthetic teacherless source",
            rights_confirmed=True,
            rights_confirmed_by=teacher,
            processing_state=ContentSource.ProcessingState.READY,
        )
        extraction = ExtractionVersion.objects.create(
            source=source,
            version=1,
            status=ExtractionVersion.Status.COMPLETE,
            extractor="synthetic-teacherless",
        )
        GenerationSourceSnapshot.objects.create(
            generation=self.generation,
            source=source,
            extraction=extraction,
            source_file_sha256="a" * 64,
            extraction_version=1,
            source_title=source.title,
        )
        for position in (1, 2):
            slide = SlideDraft.objects.create(generation=self.generation, position=position)
            revision = SlideRevision.objects.create(
                slide=slide,
                version=1,
                title=f"Synthetic slide {position} / مصنوعی",
                created_by_actor_id=teacher.pk,
            )
            SlideClaim.objects.create(
                revision=revision, position=1, text=f"Synthetic claim {position} only"
            )
            narration = f"Synthetic approved narration {position}. مصنوعی اردو عبارت۔"
            CanonicalNarrationSnapshot.objects.create(
                revision=revision,
                text=narration,
                text_sha256=hashlib.sha256(narration.encode("utf-8")).hexdigest(),
                approved_by_actor_id=teacher.pk,
            )
            slide.approved_revision = revision
            slide.save(update_fields=("approved_revision",))

    def create_approved_generation(self, teacher, *, status=GenerationRequest.Status.APPROVED):
        course = Course.objects.create(
            code="SYN-TL",
            title="Synthetic Teacherless Course",
            class_name="Class 9",
            subject_name="Physics / طبیعیات",
            teacher=teacher,
        )
        self.course = course
        self.chapter = Chapter.objects.create(course=course, number=1, title="Synthetic current")
        self.generation = GenerationRequest.objects.create(
            chapter=self.chapter,
            requested_by=teacher,
            guidelines={"synthetic": True},
            generator_key="synthetic-teacherless",
            input_sha256="5" * 64,
            status=status,
        )
        if status == GenerationRequest.Status.APPROVED:
            self.build_approved_generation(teacher)


class TeacherlessRequestTests(TeacherlessFixtureMixin, TestCase):
    def setUp(self):
        ensure_roles()
        self.teacher = assign_teacher(User.objects.create_user("teacher-tl", password="test-password"))
        self.other_teacher = assign_teacher(
            User.objects.create_user("other-teacher-tl", password="test-password")
        )
        self.admin = assign_administrator(User.objects.create_user("admin-tl", password="test-password"))
        self.create_approved_generation(self.teacher)
        self.override = override_settings(**RENDER_ENV)
        self.override.enable()
        self.addCleanup(self.override.disable)

    def test_owner_can_queue_first_pending_version(self):
        render = request_teacherless_render(self.generation.pk, self.teacher)
        self.assertEqual(render.status, TeacherlessRender.Status.PENDING)
        self.assertEqual(render.version, 1)
        self.assertEqual(render.reference, f"teacherless-g{self.generation.pk}-v1")
        self.assertEqual(render.requested_by_id, self.teacher.pk)

    def test_pending_request_is_idempotent(self):
        first = request_teacherless_render(self.generation.pk, self.teacher)
        second = request_teacherless_render(self.generation.pk, self.teacher)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(TeacherlessRender.objects.filter(generation=self.generation).count(), 1)

    def test_unauthorized_teacher_is_rejected(self):
        with self.assertRaises(PermissionDenied):
            request_teacherless_render(self.generation.pk, self.other_teacher)

    def test_course_teacher_authorization_is_stored_on_the_row(self):
        render = request_teacherless_render(self.generation.pk, self.admin)
        self.assertEqual(render.requested_by_id, self.admin.pk)
        self.assertEqual(render.generation.chapter.course.teacher_id, self.teacher.pk)

    def test_non_approved_generation_is_rejected(self):
        self.generation.status = GenerationRequest.Status.GENERATED
        self.generation.save(update_fields=("status",))
        with self.assertRaises(ValidationError):
            request_teacherless_render(self.generation.pk, self.teacher)

    def test_missing_generation_raises_does_not_exist(self):
        with self.assertRaises(GenerationRequest.DoesNotExist):
            request_teacherless_render(999_999, self.teacher)

    def test_unsupported_environment_is_rejected(self):
        with override_settings(VIDEO_RENDER_ADAPTER_ENABLED=False):
            with self.assertRaises(UnsupportedRenderEnvironment):
                request_teacherless_render(self.generation.pk, self.teacher)

    def test_fresh_running_render_is_reused(self):
        render = request_teacherless_render(self.generation.pk, self.teacher)
        render._domain_service_write = True
        render.status = TeacherlessRender.Status.RUNNING
        render.started_at = timezone.now()
        render.save()
        del render._domain_service_write
        again = request_teacherless_render(self.generation.pk, self.teacher)
        self.assertEqual(again.pk, render.pk)
        self.assertEqual(again.status, TeacherlessRender.Status.RUNNING)

    def test_stale_running_render_is_marked_failed_and_requeued(self):
        render = request_teacherless_render(self.generation.pk, self.teacher)
        render._domain_service_write = True
        render.status = TeacherlessRender.Status.RUNNING
        render.started_at = timezone.now() - timedelta(
            seconds=settings.VIDEO_RENDER_TIMEOUT_SECONDS + 60
        )
        render.save()
        del render._domain_service_write
        retry = request_teacherless_render(self.generation.pk, self.teacher)
        render.refresh_from_db()
        self.assertEqual(render.status, TeacherlessRender.Status.FAILED)
        self.assertEqual(render.failure_reason_code, "RENDER_STALE")
        self.assertNotEqual(retry.pk, render.pk)
        self.assertEqual(retry.status, TeacherlessRender.Status.PENDING)
        self.assertEqual(retry.version, 2)

    def test_failed_render_allows_new_version_and_succeeded_is_returned_as_is(self):
        first = request_teacherless_render(self.generation.pk, self.teacher)
        first._domain_service_write = True
        first.status = TeacherlessRender.Status.FAILED
        first.save()
        del first._domain_service_write
        second = request_teacherless_render(self.generation.pk, self.teacher)
        self.assertEqual(second.version, 2)
        second._domain_service_write = True
        second.status = TeacherlessRender.Status.SUCCEEDED
        second.save()
        del second._domain_service_write
        third = request_teacherless_render(self.generation.pk, self.teacher)
        self.assertEqual(third.pk, second.pk)
        self.assertEqual(third.status, TeacherlessRender.Status.SUCCEEDED)

    def test_render_rows_are_immutable_outside_the_service(self):
        render = request_teacherless_render(self.generation.pk, self.teacher)
        render.status = TeacherlessRender.Status.FAILED
        with self.assertRaises(ValueError):
            render.save()
        with self.assertRaises(ValueError):
            render.delete()


class TeacherlessPathTests(TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_traversal_and_absolute_references_are_rejected(self):
        for bad in ("../escape", "a/../../b", str(self.root), "", "C:/x", "..\\x"):
            with self.subTest(reference=bad), self.assertRaises(ValidationError):
                _resolve_relative(self.root, bad, must_exist=False)

    def test_valid_relative_reference_resolves(self):
        target = self.root / "generation-1" / "manifest.json"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"{}")
        self.assertEqual(_resolve_relative(self.root, "generation-1/manifest.json", must_exist=True), target)

    def test_missing_file_is_rejected_when_required(self):
        with self.assertRaises(ValidationError):
            _resolve_relative(self.root, "generation-1/absent.json", must_exist=True)

    def test_mp4_duration_parses_real_branding_media(self):
        intro = Path(settings.DATA_ROOT).resolve() / "assets" / "intro-outro" / "intro.mp4"
        if not intro.is_file():
            self.skipTest("PO branding media is not present in this checkout.")
        duration = _mp4_duration_ms(intro)
        self.assertGreaterEqual(duration, 250)
        self.assertLessEqual(duration, 60_000)

    def test_mp4_duration_rejects_out_of_range_values(self):
        def encode(duration, timescale=1000):
            body = (
                bytes([0]) + b"\x00\x00\x00" + b"\x00" * 8
                + timescale.to_bytes(4, "big") + duration.to_bytes(4, "big")
            )
            return b"junkmvhd" + body

        good = self.root / "good.mp4"
        good.write_bytes(encode(5000))
        self.assertEqual(_mp4_duration_ms(good), 5000)

        too_long = self.root / "long.mp4"
        too_long.write_bytes(encode(120_000))
        with self.assertRaises(ValidationError):
            _mp4_duration_ms(too_long)

        no_header = self.root / "bare.mp4"
        no_header.write_bytes(b"no mvhd box here")
        with self.assertRaises(ValidationError):
            _mp4_duration_ms(no_header)


class TeacherlessProcessTests(TeacherlessFixtureMixin, TestCase):
    def setUp(self):
        ensure_roles()
        self.teacher = assign_teacher(User.objects.create_user("teacher-tl-proc", password="test-password"))
        self.create_approved_generation(self.teacher)
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.env = override_settings(**RENDER_ENV)
        self.env.enable()
        self.addCleanup(self.env.disable)
        self.patches = [
            patch("lectures.teacherless_render.teacherless_root", return_value=self.root),
            patch("lectures.teacherless_render.compile_teacherless_manifest", side_effect=lambda gid: stub_manifest()),
            patch("lectures.teacherless_render.WindowsSystemSpeechProvider", StubSpeechProvider),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def fake_renderer(self, failure=None):
        def run(argv, *, cwd, timeout):
            if failure is not None:
                raise failure
            output = Path(argv[-1])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"synthetic-teacherless-mp4")

        return run

    def run_pipeline(self, failure=None):
        render = request_teacherless_render(self.generation.pk, self.teacher)
        with patch("lectures.teacherless_render._run_bounded", side_effect=self.fake_renderer(failure)):
            result = process_teacherless_render(render.pk)
        result.refresh_from_db()
        return result

    def test_successful_pipeline_persists_manifest_captions_and_video(self):
        render = self.run_pipeline()
        self.assertEqual(render.status, TeacherlessRender.Status.SUCCEEDED)
        self.assertEqual(render.scene_count, 2)
        self.assertGreaterEqual(render.duration_ms, 2500)
        manifest_path = self.root / render.manifest_relative_path
        video_path = self.root / render.video_relative_path
        self.assertTrue(manifest_path.is_file())
        self.assertTrue(video_path.is_file())
        self.assertTrue((manifest_path.parent / "captions.srt").is_file())
        encoded = manifest_path.read_bytes()
        self.assertEqual(render.manifest_sha256, hashlib.sha256(encoded).hexdigest())
        self.assertEqual(
            render.video_sha256, hashlib.sha256(video_path.read_bytes()).hexdigest()
        )
        self.assertEqual(render.byte_size, video_path.stat().st_size)
        import json

        manifest = json.loads(encoded)
        self.assertEqual(manifest["compositionId"], "TeacherlessLecture")
        self.assertEqual(manifest["narration"]["ttsProvider"], "stub-tts")
        self.assertEqual(manifest["narration"]["status"], "AUDIO_READY")
        for scene in manifest["scenes"]:
            audio = manifest_path.parent / "public" / scene["narrationAudioSrc"]
            self.assertTrue(audio.is_file())
            self.assertGreaterEqual(scene["durationMs"], 900)
        self.assertEqual(manifest.get("publicDir"), str(manifest_path.parent / "public"))

    def test_renderer_failure_records_reason_and_detail(self):
        render = self.run_pipeline(
            failure=RenderPipelineError("LOCAL_RENDER_FAILED", "Remotion exited with code 7")
        )
        self.assertEqual(render.status, TeacherlessRender.Status.FAILED)
        self.assertEqual(render.failure_reason_code, "LOCAL_RENDER_FAILED")
        self.assertIn("Remotion exited", render.failure_detail)
        self.assertIsNone(render.byte_size)

    def test_completed_render_is_not_reprocessed(self):
        render = self.run_pipeline()
        with patch("lectures.teacherless_render._run_bounded") as bounded:
            again = process_teacherless_render(render.pk)
        bounded.assert_not_called()
        self.assertEqual(again.status, TeacherlessRender.Status.SUCCEEDED)
        self.assertEqual(
            TeacherlessRender.objects.filter(generation=self.generation).count(), 1
        )

    def test_manifest_omits_render_scale_by_default(self):
        import json
        import os as _os

        clean_env = {key: value for key, value in _os.environ.items() if key != "AI_LECTURE_TEACHERLESS_RENDER_SCALE"}
        with patch.dict(_os.environ, clean_env, clear=True):
            render = self.run_pipeline()
        manifest = json.loads((self.root / render.manifest_relative_path).read_bytes())
        self.assertNotIn("renderScale", manifest)

    def test_downscaled_render_scale_is_written_to_manifest(self):
        import json
        import os as _os

        with patch.dict(_os.environ, {"AI_LECTURE_TEACHERLESS_RENDER_SCALE": str(2 / 3)}):
            render = self.run_pipeline()
        manifest = json.loads((self.root / render.manifest_relative_path).read_bytes())
        self.assertAlmostEqual(manifest["renderScale"], 2 / 3, places=9)

    def test_unsupported_environment_fails_the_queued_row(self):
        render = request_teacherless_render(self.generation.pk, self.teacher)
        with override_settings(VIDEO_RENDER_DEPLOYMENT_MODE="production"):
            result = process_teacherless_render(render.pk)
        result.refresh_from_db()
        self.assertEqual(result.status, TeacherlessRender.Status.FAILED)
        self.assertEqual(result.failure_reason_code, "RENDER_ENVIRONMENT")

    def test_production_media_is_attached_when_branding_assets_exist(self):
        assets = Path(settings.DATA_ROOT).resolve() / "assets"
        if not (assets / "intro-outro" / "intro.mp4").is_file():
            self.skipTest("PO branding media is not present in this checkout.")
        render = self.run_pipeline()
        import json

        manifest = json.loads((self.root / render.manifest_relative_path).read_bytes())
        production = manifest["production"]
        self.assertEqual(production["introSrc"], "branding/intro.mp4")
        self.assertGreaterEqual(production["introDurationMs"], 250)
        self.assertTrue(
            ((self.root / render.manifest_relative_path).parent / "public" / "branding" / "intro.mp4").is_file()
        )

    def test_payload_exposes_media_only_when_succeeded(self):
        render = request_teacherless_render(self.generation.pk, self.teacher)
        payload = teacherless_render_payload(render)
        self.assertIsNone(payload["media_url"])
        self.assertEqual(payload["status"], "PENDING")
        render = self.run_pipeline()
        payload = teacherless_render_payload(render)
        self.assertEqual(payload["media_url"], f"/teacherless/renders/{render.pk}/media/")
        self.assertEqual(payload["scene_count"], 2)


class TeacherlessViewTests(TeacherlessFixtureMixin, TestCase):
    def setUp(self):
        ensure_roles()
        self.teacher = assign_teacher(User.objects.create_user("teacher-tl-view", password="test-password"))
        self.other_teacher = assign_teacher(
            User.objects.create_user("other-teacher-tl-view", password="test-password")
        )
        self.admin = assign_administrator(User.objects.create_user("admin-tl-view", password="test-password"))
        self.create_approved_generation(self.teacher)
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.env = override_settings(**RENDER_ENV)
        self.env.enable()
        self.addCleanup(self.env.disable)
        root_patch = patch("lectures.teacherless_render.teacherless_root", return_value=self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)
        self.client = Client()
        self.client.force_login(self.teacher)

    def post_render(self, client=None, generation_id=None):
        return (client or self.client).post(
            f"/api/teacherless/generations/{generation_id or self.generation.pk}/render/",
            data="{}",
            content_type="application/json",
        )

    def make_succeeded(self):
        render = request_teacherless_render(self.generation.pk, self.teacher)
        video = self.root / "lecture.mp4"
        video.write_bytes(b"synthetic-teacherless-mp4")
        render._domain_service_write = True
        render.status = TeacherlessRender.Status.SUCCEEDED
        render.video_relative_path = "lecture.mp4"
        render.save()
        del render._domain_service_write
        return render

    def test_anonymous_requests_redirect_to_login(self):
        response = Client().get(f"/api/teacherless/generations/{self.generation.pk}/render/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_owner_post_queues_pending_render(self):
        with patch("lectures.views.start_teacherless_render") as starter:
            response = self.post_render()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["status"], "PENDING")
        self.assertEqual(body["generation_id"], self.generation.pk)
        starter.assert_not_called()  # TestCase never commits, so the thread must not start

    def test_other_teacher_post_is_forbidden(self):
        other = Client()
        other.force_login(self.other_teacher)
        response = self.post_render(client=other)
        self.assertEqual(response.status_code, 403)

    def test_missing_generation_post_is_not_found(self):
        response = self.post_render(generation_id=999_999)
        self.assertEqual(response.status_code, 404)

    def test_non_approved_generation_post_is_bad_request(self):
        self.generation.status = GenerationRequest.Status.GENERATED
        self.generation.save(update_fields=("status",))
        response = self.post_render()
        self.assertEqual(response.status_code, 400)

    def test_unsupported_environment_post_is_service_unavailable(self):
        with override_settings(VIDEO_RENDER_RAILWAY_ENVIRONMENT=True):
            response = self.post_render()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["state"], "unsupported")

    def test_unexpected_fields_are_rejected(self):
        response = self.client.post(
            f"/api/teacherless/generations/{self.generation.pk}/render/",
            data=json_dumps_extra(),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_status_api_visibility(self):
        render = request_teacherless_render(self.generation.pk, self.teacher)
        self.assertEqual(
            self.client.get(f"/api/teacherless/renders/{render.pk}/status/").status_code, 200
        )
        other = Client()
        other.force_login(self.other_teacher)
        self.assertEqual(
            other.get(f"/api/teacherless/renders/{render.pk}/status/").status_code, 404
        )
        admin_client = Client()
        admin_client.force_login(self.admin)
        self.assertEqual(
            admin_client.get(f"/api/teacherless/renders/{render.pk}/status/").status_code, 200
        )
        self.assertEqual(
            self.client.get("/api/teacherless/renders/424242/status/").status_code, 404
        )

    def test_media_api_streams_succeeded_render(self):
        render = self.make_succeeded()
        response = self.client.get(f"/teacherless/renders/{render.pk}/media/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "video/mp4")
        self.assertIn("inline", response["Content-Disposition"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        disposition = self.client.get(f"/teacherless/renders/{render.pk}/media/?download=1")[
            "Content-Disposition"
        ]
        self.assertIn("attachment", disposition)
        self.assertIn(f"teacherless-lecture-g{self.generation.pk}-v1.mp4", disposition)

    def test_media_api_hides_invisible_or_incomplete_renders(self):
        render = self.make_succeeded()
        other = Client()
        other.force_login(self.other_teacher)
        self.assertEqual(other.get(f"/teacherless/renders/{render.pk}/media/").status_code, 404)
        pending = TeacherlessRender.objects.create(
            generation=self.generation,
            version=2,
            reference=f"teacherless-g{self.generation.pk}-v2",
            status=TeacherlessRender.Status.PENDING,
            requested_by=self.teacher,
        )
        self.assertEqual(
            self.client.get(f"/teacherless/renders/{pending.pk}/media/").status_code, 404
        )

    def test_media_api_404s_when_the_file_is_missing(self):
        render = self.make_succeeded()
        (self.root / "lecture.mp4").unlink()
        self.assertEqual(
            self.client.get(f"/teacherless/renders/{render.pk}/media/").status_code, 404
        )


def json_dumps_extra():
    import json

    return json.dumps({"unexpected": True})
