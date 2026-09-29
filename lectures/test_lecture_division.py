import json
import os
import shutil
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from .generation import actor_context_for_user, create_generation
from .models import (
    Chapter,
    ContentFile,
    ContentSource,
    Course,
    ExtractedPage,
    ExtractionVersion,
    GenerationRequest,
    LectureDivision,
    LectureWorkflow,
)
from .roles import assign_teacher, ensure_roles


class LectureDivisionPipelineTests(TestCase):
    def setUp(self):
        ensure_roles()
        root = Path(__file__).resolve().parents[1] / "data" / "content-tools" / "tmp"
        root.mkdir(parents=True, exist_ok=True)
        self.storage = root / f"division-test-{os.getpid()}-{uuid.uuid4().hex}"
        self.storage.mkdir()
        override = override_settings(CONTENT_STORAGE_ROOT=self.storage)
        override.enable()
        self.addCleanup(override.disable)
        self.addCleanup(lambda: shutil.rmtree(self.storage, ignore_errors=True))

        self.teacher = assign_teacher(User.objects.create_user("teacher-division"))
        self.course = Course.objects.create(
            code="SYN-DIV", title="Synthetic Computer Science",
            class_name="Class 9", subject_name="Computer Science", teacher=self.teacher,
        )
        self.chapter = Chapter.objects.create(course=self.course, number=1, title="Unit 1")
        self.source = self.make_source()

    def make_source(self, pages=("Page one text about computers.", "Page two text about types.", "Page three text about networks.")):
        source = ContentSource.objects.create(
            chapter=self.chapter, source_type=ContentSource.SourceType.INSTITUTIONAL,
            access_scope=ContentSource.AccessScope.AUTHORIZED_TEACHERS, owner=None,
            title="Synthetic textbook", rights_confirmed=True, rights_confirmed_by=self.teacher,
            processing_state=ContentSource.ProcessingState.READY, page_count=len(pages),
        )
        source_file = ContentFile.objects.create(
            source=source, original_name="synthetic.pdf", storage_key=f"originals/{source.pk}.pdf",
            extension=".pdf", media_type="application/pdf", byte_size=10,
            sha256=f"hash-{source.pk}",
        )
        extraction = ExtractionVersion.objects.create(
            source=source, version=1, status=ExtractionVersion.Status.COMPLETE, extractor="synthetic-division",
        )
        for number, text in enumerate(pages, start=1):
            raw = text.encode("utf-8")
            key = f"derived/{source.pk}/v1/page-{number:04d}.txt"
            path = self.storage / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            ExtractedPage.objects.create(
                extraction=extraction, source_file=source_file, page_number=number,
                method=ExtractedPage.Method.PDF_TEXT, text_storage_key=key,
                text_sha256=__import__("hashlib").sha256(raw).hexdigest(),
                character_count=len(text), requires_review=False,
                review_status=ExtractedPage.ReviewStatus.NOT_REQUIRED,
            )
        return source

    def make_division(self, number=1, title="Lecture one", start=1, end=2):
        return LectureDivision.objects.create(
            chapter=self.chapter, number=number, title=title, page_start=start, page_end=end,
        )

    def write_division_file(self, payload):
        path = self.storage / "division.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_import_command_creates_and_updates_division(self):
        path = self.write_division_file({
            "lectures": [
                {"number": 1, "title": "Introduction", "pages": "1-2"},
                {"number": 2, "title": "Networks", "pages": "3-3"},
            ]
        })
        call_command("import_lecture_division", course_code=self.course.code, chapter_number=1, file=str(path))
        self.assertEqual(LectureDivision.objects.count(), 2)
        first = LectureDivision.objects.get(number=1)
        self.assertEqual((first.page_start, first.page_end), (1, 2))

        path = self.write_division_file({"lectures": [{"number": 1, "title": "Introduction revised", "pages": "1-1"}]})
        call_command("import_lecture_division", course_code=self.course.code, chapter_number=1, file=str(path))
        self.assertEqual(LectureDivision.objects.count(), 2)
        first.refresh_from_db()
        self.assertEqual(first.title, "Introduction revised")
        self.assertEqual((first.page_start, first.page_end), (1, 1))

    def test_import_command_rejects_inverted_page_range(self):
        path = self.write_division_file({"lectures": [{"number": 1, "title": "Bad", "pages": "5-2"}]})
        with self.assertRaises(CommandError):
            call_command("import_lecture_division", course_code=self.course.code, chapter_number=1, file=str(path))

    def test_generation_is_scoped_to_lecture_pages(self):
        division = self.make_division(start=1, end=2)
        generation = create_generation(
            actor=actor_context_for_user(self.teacher),
            chapter_id=self.chapter.pk,
            source_ids=[self.source.pk],
            guidelines={"learning_objective": "Explain computers", "audience_level": "Class 9", "slide_count": 2},
            lecture_id=division.pk,
        )
        pages = sorted(set(generation.source_snapshots.values_list("pages__page_number", flat=True)))
        self.assertEqual(pages, [1, 2])
        self.assertEqual(generation.lecture_id, division.pk)

    def test_generation_rejects_out_of_scope_and_foreign_lectures(self):
        empty = self.make_division(number=2, start=7, end=9)
        with self.assertRaises(ValidationError):
            create_generation(
                actor=actor_context_for_user(self.teacher),
                chapter_id=self.chapter.pk,
                source_ids=[self.source.pk],
                guidelines={"learning_objective": "Explain computers", "audience_level": "Class 9", "slide_count": 2},
                lecture_id=empty.pk,
            )
        other_chapter = Chapter.objects.create(course=self.course, number=2, title="Unit 2")
        foreign = LectureDivision.objects.create(
            chapter=other_chapter, number=1, title="Foreign", page_start=1, page_end=1,
        )
        with self.assertRaises(ValidationError):
            create_generation(
                actor=actor_context_for_user(self.teacher),
                chapter_id=self.chapter.pk,
                source_ids=[self.source.pk],
                guidelines={"learning_objective": "Explain computers", "audience_level": "Class 9", "slide_count": 2},
                lecture_id=foreign.pk,
            )
        unscoped = LectureDivision.objects.create(
            chapter=self.chapter, number=3, title="Unscoped", page_start=None, page_end=None,
        )
        with self.assertRaises(ValidationError):
            create_generation(
                actor=actor_context_for_user(self.teacher),
                chapter_id=self.chapter.pk,
                source_ids=[self.source.pk],
                guidelines={"learning_objective": "Explain computers", "audience_level": "Class 9", "slide_count": 2},
                lecture_id=unscoped.pk,
            )

    def test_generate_command_skip_engine_creates_workflow(self):
        self.make_division()
        call_command(
            "generate_lecture_ppt", course_code=self.course.code, lecture=1,
            slide_count=2, skip_engine=True,
        )
        generation = GenerationRequest.objects.get(lecture__number=1)
        workflow = LectureWorkflow.objects.get(generation=generation)
        self.assertEqual(workflow.state, LectureWorkflow.State.SOURCE_CONTENT_READY)
        pages = sorted(set(generation.source_snapshots.values_list("pages__page_number", flat=True)))
        self.assertEqual(pages, [1, 2])

    def test_generate_command_runs_queued_engine_and_records_pptx(self):
        self.make_division()
        job = SimpleNamespace(pk=77, status="SUCCEEDED")

        def fake_execute(*args, **kwargs):
            GenerationRequest.objects.filter(lecture__number=1).update(
                pptx_storage_key="slide-engine/generation-1/lecture.pptx"
            )
            return job

        with (
            mock.patch("lectures.management.commands.generate_lecture_ppt.queue_slide_generation") as queued,
            mock.patch(
                "lectures.management.commands.generate_lecture_ppt.execute_one_slide_generation",
                side_effect=fake_execute,
            ),
        ):
            call_command("generate_lecture_ppt", course_code=self.course.code, lecture=1, slide_count=2)
        queued.assert_called_once()
        generation = GenerationRequest.objects.get(lecture__number=1)
        self.assertEqual(generation.pptx_storage_key, "slide-engine/generation-1/lecture.pptx")
        workflow = LectureWorkflow.objects.get(generation=generation)
        self.assertEqual(workflow.state, LectureWorkflow.State.SOURCE_CONTENT_READY)

    def test_generate_command_requires_division_and_ready_source(self):
        with self.assertRaises(CommandError):
            call_command("generate_lecture_ppt", course_code=self.course.code, lecture=9, skip_engine=True)
        self.source.processing_state = ContentSource.ProcessingState.REVIEW_REQUIRED
        self.source.save(update_fields=("processing_state", "updated_at"))
        self.make_division()
        with self.assertRaises(CommandError):
            call_command("generate_lecture_ppt", course_code=self.course.code, lecture=1, skip_engine=True)
