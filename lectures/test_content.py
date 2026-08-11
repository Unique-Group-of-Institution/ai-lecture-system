import io
import json
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import DEFAULT, patch

from django.contrib.auth.models import Group, User
from django.contrib import admin as django_admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.test import Client, RequestFactory, TestCase, override_settings
from PIL import Image
from pypdf import PdfWriter

from .admin import ContentFileAdmin, ContentSourceAdmin, ExtractedPageAdmin, ExtractionVersionAdmin
from .content import _allocate_extraction, _contained, _extract_pdf_text_bounded, _inspect_pdf_bounded, _ocr_image, _remove_known_tree, _render_page_bounded, approve_ocr_extraction, extract_source, register_upload, sources_visible_to, validate_upload
from .models import Chapter, ContentFile, ContentSource, Course, ExtractedPage, ExtractionVersion
from .roles import ADMINISTRATOR_ROLE, TEACHER_ROLE, ensure_roles


def synthetic_image(fmt="PNG"):
    output = io.BytesIO()
    Image.new("RGB", (64, 32), "white").save(output, format=fmt)
    output.seek(0)
    return output


def synthetic_pdf(pages=1):
    output = io.BytesIO()
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=72, height=72)
    writer.write(output)
    output.seek(0)
    return output


@override_settings(CONTENT_MAX_UPLOAD_BYTES=1024 * 1024)
class ContentFoundationTests(TestCase):
    def setUp(self):
        ensure_roles()
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = override_settings(CONTENT_STORAGE_ROOT=self.tmp.name)
        self.settings.enable()
        self.addCleanup(self.settings.disable)
        self.addCleanup(self.tmp.cleanup)
        self.admin = User.objects.create_user("admin")
        self.teacher = User.objects.create_user("teacher")
        self.other = User.objects.create_user("other")
        self.admin.groups.add(Group.objects.get(name=ADMINISTRATOR_ROLE))
        self.teacher.groups.add(Group.objects.get(name=TEACHER_ROLE))
        self.other.groups.add(Group.objects.get(name=TEACHER_ROLE))
        self.course = Course.objects.create(code="SYN", title="Synthetic", class_name="10", subject_name="Science", teacher=self.teacher)
        self.chapter = Chapter.objects.create(course=self.course, number=1, title="Synthetic chapter")

    def upload(self, actor=None, source_type=ContentSource.SourceType.TEACHER, data=None, name="lesson.png", rights=True):
        return register_upload(actor=actor or self.teacher, chapter=self.chapter, title="Synthetic only", source_type=source_type, rights_confirmed=rights, upload=data or synthetic_image(), filename=name)

    def ocr_paths(self):
        image = Path(self.tmp.name, "fixture.png")
        image.write_bytes(synthetic_image().read())
        tool = Path(self.tmp.name, "tesseract.exe")
        tool.write_bytes(b"synthetic")
        tessdata = Path(self.tmp.name, "tessdata")
        tessdata.mkdir(exist_ok=True)
        for language in ("urd", "eng", "osd"):
            (tessdata / f"{language}.traineddata").write_bytes(b"synthetic")
        return image, tool, tessdata

    @staticmethod
    def ocr_process(stdout=b"", stderr=b"", returncode=0, hangs=False):
        class Process:
            def __init__(self):
                self.stdout = BytesIO(stdout)
                self.stderr = BytesIO(stderr)
                self.returncode = None if hangs else returncode
                self.terminated = False
                self.killed = False
                self.wait_calls = 0
            def poll(self): return self.returncode
            def terminate(self):
                self.terminated = True
                self.returncode = -15
            def kill(self):
                self.killed = True
                self.returncode = -9
            def wait(self, timeout=None):
                self.wait_calls += 1
                return self.returncode
        return Process()

    def test_access_policy_separates_institutional_and_private_teacher_sources(self):
        institutional = self.upload(self.admin, ContentSource.SourceType.INSTITUTIONAL)
        private = self.upload()
        self.assertEqual(set(sources_visible_to(self.teacher)), {institutional, private})
        self.assertNotIn(private, sources_visible_to(self.other))
        self.assertEqual(set(sources_visible_to(self.admin)), {institutional, private})

    def test_rights_confirmation_is_mandatory(self):
        with self.assertRaises(ValidationError):
            self.upload(rights=False)

    def test_pdf_and_image_validation_use_real_decoders(self):
        self.assertEqual(validate_upload(synthetic_pdf(2), "pages.pdf").page_count, 2)
        self.assertEqual(validate_upload(synthetic_image("JPEG"), "page.jpeg").media_type, "image/jpeg")
        self.assertEqual(validate_upload(synthetic_image(), "page.png").media_type, "image/png")

    def test_mismatch_corruption_and_executable_are_rejected(self):
        cases = [(synthetic_image(), "wrong.pdf"), (synthetic_image("JPEG"), "wrong.png"), (io.BytesIO(b"MZpayload"), "bad.pdf"), (io.BytesIO(b"%PDF-broken"), "bad.pdf")]
        for data, name in cases:
            with self.subTest(name=name), self.assertRaises(ValidationError):
                validate_upload(data, name)

    def test_unsafe_names_paths_and_unsupported_types_are_rejected(self):
        for name in ("../page.png", "CON.png", "bad?.png", "page.exe", "page.png."):
            with self.subTest(name=name), self.assertRaises(ValidationError):
                validate_upload(synthetic_image(), name)
        with self.assertRaises(ValidationError):
            _contained("../outside.txt")

    def test_size_limit_is_enforced(self):
        with self.assertRaises(ValidationError):
            validate_upload(synthetic_image(), "page.png", max_bytes=10)

    def test_near_boundary_upload_is_accepted(self):
        data = synthetic_image()
        size = len(data.getvalue())
        self.assertEqual(validate_upload(data, "page.png", max_bytes=size).byte_size, size)

    def test_original_record_and_bytes_are_immutable(self):
        source = self.upload()
        original = source.original_file
        path = Path(self.tmp.name, original.storage_key)
        before = path.read_bytes()
        original.original_name = "changed.png"
        with self.assertRaises(ValueError):
            original.save()
        with self.assertRaises(FileExistsError):
            path.open("xb")
        self.assertEqual(path.read_bytes(), before)

    def test_page_provenance_for_text_pdf(self):
        source = self.upload(data=synthetic_pdf(2), name="synthetic.pdf")
        class Page:
            def __init__(self, text): self.text = text
            def extract_text(self): return self.text
            mediabox = type("Box", (), {"width": 72, "height": 72})()
        class Reader:
            pages = [Page("Page one"), Page("Page two")]
        def native(source_path, output):
            (output / "native-0001.txt").write_text("Page one", encoding="utf-8")
            (output / "native-0002.txt").write_text("Page two", encoding="utf-8")
        with patch("lectures.content.PdfReader", return_value=Reader()), patch("lectures.content._extract_pdf_text_bounded", side_effect=native):
            extraction = extract_source(source)
        self.assertEqual(extraction.status, ExtractionVersion.Status.COMPLETE)
        self.assertEqual(list(extraction.pages.values_list("page_number", "method")), [(1, ExtractedPage.Method.PDF_TEXT), (2, ExtractedPage.Method.PDF_TEXT)])
        self.assertTrue(all(page.source_file_id == source.original_file.pk for page in extraction.pages.all()))

    def test_low_confidence_urdu_ocr_requires_review_and_preserves_unicode(self):
        source = self.upload()
        with patch("lectures.content._ocr_image", return_value=("اردو English", 42.5)):
            extraction = extract_source(source)
        page = extraction.pages.get()
        self.assertEqual(extraction.status, ExtractionVersion.Status.REVIEW_REQUIRED)
        self.assertTrue(page.requires_review)
        text = Path(self.tmp.name, page.text_storage_key).read_text(encoding="utf-8")
        self.assertEqual(text, "اردو English")

    def test_missing_ocr_tool_or_models_fails_safely(self):
        source = self.upload()
        with self.assertRaises(FileNotFoundError):
            extract_source(source, tesseract_path=Path(self.tmp.name, "missing.exe"), tessdata_path=Path(self.tmp.name))
        source.refresh_from_db()
        self.assertEqual(source.processing_state, ContentSource.ProcessingState.FAILED)
        self.assertEqual(source.extractions.get().error_code, "LOCAL_EXTRACTION_FAILED")

    def test_ocr_service_never_calls_network(self):
        image = Path(self.tmp.name, "fixture.png")
        image.write_bytes(synthetic_image().read())
        tool = Path(self.tmp.name, "tesseract.exe")
        tool.write_bytes(b"synthetic")
        tessdata = Path(self.tmp.name, "tessdata")
        tessdata.mkdir()
        for language in ("urd", "eng", "osd"):
            (tessdata / f"{language}.traineddata").write_bytes(b"synthetic")
        tsv = b"level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n5\t1\t1\t1\t1\t1\t0\t0\t1\t1\t90\tEnglish\n"
        process = self.ocr_process(stdout=tsv)
        with patch("socket.create_connection", side_effect=AssertionError("network forbidden")), patch("lectures.content.subprocess.Popen", return_value=process) as popen:
            text, confidence = _ocr_image(image, tool, tessdata)
        self.assertEqual((text, confidence), ("English", 90.0))
        command = popen.call_args.args[0]
        self.assertIn("urd+eng", command)
        self.assertIn("tsv", command)

    def test_selection_api_combines_only_visible_rights_confirmed_sources(self):
        institutional = self.upload(self.admin, ContentSource.SourceType.INSTITUTIONAL)
        private = self.upload()
        ContentSource.objects.filter(pk__in=(institutional.pk, private.pk)).update(processing_state=ContentSource.ProcessingState.READY)
        hidden = register_upload(actor=self.other, chapter=Chapter.objects.create(
            course=Course.objects.create(code="OTHER", title="Other", teacher=self.other),
            number=1, title="Other"), title="Hidden", source_type=ContentSource.SourceType.TEACHER,
            rights_confirmed=True, upload=synthetic_image(), filename="hidden.png")
        self.client.force_login(self.teacher)
        response = self.client.post(
            "/api/content-selection/",
            data=json.dumps({"source_ids": [institutional.pk, private.pk]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual({item["id"] for item in response.json()["sources"]}, {institutional.pk, private.pk})
        denied = self.client.post(
            "/api/content-selection/",
            data=json.dumps({"source_ids": [hidden.pk]}),
            content_type="application/json",
        )
        self.assertEqual(denied.status_code, 403)

    @override_settings(CONTENT_MAX_IMAGE_PIXELS=100, CONTENT_MAX_IMAGE_WIDTH=1000, CONTENT_MAX_IMAGE_HEIGHT=1000)
    def test_decompression_bomb_warning_is_validation_failure(self):
        with self.assertRaises(ValidationError):
            validate_upload(synthetic_image(), "bomb.png")

    @override_settings(CONTENT_MAX_IMAGE_WIDTH=32)
    def test_extreme_image_dimensions_are_rejected(self):
        with self.assertRaises(ValidationError):
            validate_upload(synthetic_image(), "wide.png")

    @override_settings(CONTENT_MAX_PDF_PAGES=2)
    def test_excessive_pdf_pages_are_rejected(self):
        with self.assertRaises(ValidationError):
            validate_upload(synthetic_pdf(3), "many.pdf")

    @override_settings(CONTENT_MAX_PDF_PAGE_WIDTH_POINTS=100)
    def test_oversized_pdf_page_dimensions_are_rejected(self):
        output = io.BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=101, height=72)
        writer.write(output)
        output.seek(0)
        with self.assertRaises(ValidationError):
            validate_upload(output, "wide.pdf")

    def test_high_confidence_ocr_still_requires_teacher_review_and_gate(self):
        source = self.upload()
        with patch("lectures.content._ocr_image", return_value=("اردو English = x", 99.9)):
            extraction = extract_source(source)
        page = extraction.pages.get()
        source.refresh_from_db()
        self.assertEqual(extraction.status, ExtractionVersion.Status.REVIEW_REQUIRED)
        self.assertEqual(source.processing_state, ContentSource.ProcessingState.REVIEW_REQUIRED)
        self.assertEqual(page.review_status, ExtractedPage.ReviewStatus.PENDING)
        self.assertIn("MIXED_URDU_ENGLISH_DIRECTION", page.review_flags)
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.post("/api/content-selection/", data=json.dumps({"source_ids": [source.pk]}), content_type="application/json").status_code, 403)
        approve_ocr_extraction(actor=self.teacher, extraction=extraction)
        source.refresh_from_db()
        self.assertEqual(source.processing_state, ContentSource.ProcessingState.READY)

    def test_unassigned_teacher_cannot_approve_ocr(self):
        source = self.upload()
        with patch("lectures.content._ocr_image", return_value=("text", 90)):
            extraction = extract_source(source)
        with self.assertRaises(PermissionDenied):
            approve_ocr_extraction(actor=self.other, extraction=extraction)

    def test_registration_failure_leaves_no_database_or_private_artifact(self):
        with patch("lectures.content.ContentFile.objects.create", side_effect=RuntimeError("injected")), self.assertRaises(RuntimeError):
            self.upload()
        self.assertFalse(ContentSource.objects.exists())
        files = [path for path in Path(self.tmp.name).rglob("*") if path.is_file()]
        self.assertEqual(files, [])

    def test_extraction_failure_cleans_staging_and_keeps_original(self):
        source = self.upload()
        original_path = Path(self.tmp.name, source.original_file.storage_key)
        before = original_path.read_bytes()
        with patch("lectures.content._ocr_image", side_effect=RuntimeError("injected")), self.assertRaises(RuntimeError):
            extract_source(source)
        self.assertEqual(original_path.read_bytes(), before)
        self.assertFalse(any(Path(self.tmp.name, "staging").glob("extraction-*")))
        self.assertFalse(Path(self.tmp.name, "derived", str(source.pk)).exists())

    def test_database_failure_after_promotion_removes_derived_tree(self):
        source = self.upload()
        original_path = Path(self.tmp.name, source.original_file.storage_key)
        before = original_path.read_bytes()
        with patch("lectures.content._ocr_image", return_value=("synthetic", 95)), patch(
            "lectures.content.ExtractedPage.objects.create", side_effect=IntegrityError("injected")
        ), self.assertRaises(IntegrityError):
            extract_source(source)
        source.refresh_from_db()
        extraction = source.extractions.get()
        self.assertEqual(original_path.read_bytes(), before)
        self.assertEqual(source.processing_state, ContentSource.ProcessingState.FAILED)
        self.assertEqual(extraction.status, ExtractionVersion.Status.FAILED)
        self.assertFalse(Path(self.tmp.name, "derived", str(source.pk)).exists())

    def test_final_integrity_mismatch_never_becomes_ready(self):
        source = self.upload()
        original_path = Path(self.tmp.name, source.original_file.storage_key)
        def mutate(*args, **kwargs):
            original_path.write_bytes(b"changed evidence")
            return "text", 95
        with patch("lectures.content._ocr_image", side_effect=mutate), self.assertRaisesRegex(RuntimeError, "FINAL_INTEGRITY_MISMATCH"):
            extract_source(source)
        source.refresh_from_db()
        extraction = source.extractions.get()
        self.assertEqual(source.processing_state, ContentSource.ProcessingState.COMPROMISED)
        self.assertEqual(extraction.error_code, "ORIGINAL_INTEGRITY_MISMATCH")
        self.assertTrue(original_path.exists())
        self.assertFalse(extraction.pages.exists())

    def test_version_allocation_retries_a_unique_collision(self):
        source = self.upload()
        manager_create = ExtractionVersion.objects.create
        with patch("lectures.content.ExtractionVersion.objects.create", side_effect=[IntegrityError("collision"), DEFAULT], wraps=manager_create) as create:
            extraction = _allocate_extraction(source.pk)
        self.assertEqual(extraction.version, 1)
        self.assertEqual(create.call_count, 2)

    @override_settings(CONTENT_MAX_RENDERED_TOTAL_PIXELS=3)
    def test_cumulative_rendering_limit_fails_before_render(self):
        source = self.upload(data=synthetic_pdf(2), name="scans.pdf")
        class Page:
            mediabox = type("Box", (), {"width": 72, "height": 72})()
            def extract_text(self): return ""
        class Reader: pages = [Page(), Page()]
        def blank(source_path, output):
            (output / "native-0001.txt").write_text("", encoding="utf-8")
            (output / "native-0002.txt").write_text("", encoding="utf-8")
        with patch("lectures.content.PdfReader", return_value=Reader()), patch("lectures.content._extract_pdf_text_bounded", side_effect=blank), patch("lectures.content._render_page_bounded") as render, self.assertRaises(ValidationError):
            extract_source(source)
        render.assert_not_called()

    def test_ocr_timeout_is_safe_failure(self):
        image, tool, tessdata = self.ocr_paths()
        process = self.ocr_process(hangs=True)
        with override_settings(CONTENT_OCR_TIMEOUT_SECONDS=0), patch("lectures.content.subprocess.Popen", return_value=process), self.assertRaisesRegex(RuntimeError, "time limit"):
            _ocr_image(image, tool, tessdata)
        self.assertTrue(process.terminated)
        self.assertGreaterEqual(process.wait_calls, 1)

    def test_ocr_stdout_and_stderr_limits_terminate_and_reap(self):
        image, tool, tessdata = self.ocr_paths()
        for stream in ("stdout", "stderr"):
            process = self.ocr_process(hangs=True, **{stream: b"x" * 9})
            with self.subTest(stream=stream), override_settings(CONTENT_MAX_OCR_STDOUT_BYTES=8, CONTENT_MAX_OCR_STDERR_BYTES=8), patch("lectures.content.subprocess.Popen", return_value=process), self.assertRaisesRegex(RuntimeError, "output exceeded"):
                _ocr_image(image, tool, tessdata)
            self.assertTrue(process.terminated)
            self.assertGreaterEqual(process.wait_calls, 1)

    def test_ocr_nonzero_exit_is_privacy_safe(self):
        image, tool, tessdata = self.ocr_paths()
        process = self.ocr_process(stderr=b"private source text", returncode=2)
        with patch("lectures.content.subprocess.Popen", return_value=process), self.assertRaisesRegex(RuntimeError, "failed safely") as raised:
            _ocr_image(image, tool, tessdata)
        self.assertNotIn("private", str(raised.exception))
        self.assertGreaterEqual(process.wait_calls, 1)

    def test_malformed_tsv_is_privacy_safe(self):
        image, tool, tessdata = self.ocr_paths()
        tsv = b"block_num\tpar_num\tline_num\tconf\ttext\n1\t1\t1\tprivate-value\tprivate source text\n"
        process = self.ocr_process(stdout=tsv)
        with patch("lectures.content.subprocess.Popen", return_value=process), self.assertRaisesRegex(RuntimeError, "invalid output") as raised:
            _ocr_image(image, tool, tessdata)
        self.assertNotIn("private", str(raised.exception))

    def test_valid_tsv_at_stdout_boundary(self):
        image, tool, tessdata = self.ocr_paths()
        tsv = b"block_num\tpar_num\tline_num\tconf\ttext\n1\t1\t1\t99\tbounded\n"
        process = self.ocr_process(stdout=tsv)
        with override_settings(CONTENT_MAX_OCR_STDOUT_BYTES=len(tsv)), patch("lectures.content.subprocess.Popen", return_value=process):
            self.assertEqual(_ocr_image(image, tool, tessdata), ("bounded", 99.0))

    def test_pdf_inspection_timeout_malformed_excessive_and_parser_failure(self):
        source = Path(self.tmp.name, "input.pdf")
        response = Path(self.tmp.name, "response.json")
        source.write_bytes(b"%PDF-synthetic")
        class Process:
            def __init__(self, payload=None, alive=False, stubborn=False):
                self.payload, self.alive, self.stubborn = payload, alive, stubborn
                self.exitcode = None if alive else 0
                self.terminated = False
                self.killed = False
                self.joins = 0
            def start(self):
                if self.payload is not None: response.write_bytes(self.payload)
            def join(self, timeout=None): self.joins += 1
            def is_alive(self): return self.alive
            def terminate(self):
                self.terminated = True
                if not self.stubborn: self.alive = False
            def kill(self): self.killed = True; self.alive = False
        cases = [
            (Process(alive=True, stubborn=True), 32, "time limit"),
            (Process(b"not-json"), 32, "unsafe response"),
            (Process(b"x" * 33), 32, "unsafe response"),
            (Process(b'{"ok":false}'), 32, "unsupported PDF"),
            (Process(b'{"ok":true,"page_count":1,"dimensions":[[NaN,72]]}'), 64, "unsafe response"),
        ]
        for process, limit, message in cases:
            response.unlink(missing_ok=True)
            context = type("Context", (), {"Process": lambda *args, **kwargs: process})()
            with self.subTest(message=message), override_settings(CONTENT_PDF_INSPECTION_TIMEOUT_SECONDS=0, CONTENT_MAX_PDF_INSPECTION_RESPONSE_BYTES=limit), patch("lectures.content.multiprocessing.get_context", return_value=context), self.assertRaisesRegex(ValidationError, message):
                _inspect_pdf_bounded(source, response)
            if message == "time limit":
                self.assertTrue(process.terminated)
                self.assertTrue(process.killed)
                self.assertGreaterEqual(process.joins, 3)

    def test_cleanup_rejects_parent_and_out_of_scope_paths(self):
        parent = Path(self.tmp.name, "staging")
        parent.mkdir()
        outside = Path(self.tmp.name, "outside")
        outside.mkdir()
        for target in (parent, outside):
            with self.subTest(target=target), self.assertRaisesRegex(RuntimeError, "unsafe cleanup"):
                _remove_known_tree(target, parent)

    def test_selection_rejects_malformed_json_and_source_ids(self):
        self.client.force_login(self.teacher)
        url = "/api/content-selection/"
        for body in (
            b"{",
            json.dumps([]),
            json.dumps({"source_ids": "1"}),
            json.dumps({"source_ids": [True]}),
            json.dumps({"source_ids": [{}]}),
            json.dumps({"source_ids": [0]}),
            json.dumps({"source_ids": [-1]}),
            json.dumps({"source_ids": [1.0]}),
            json.dumps({"source_ids": [" 1"]}),
            json.dumps({"source_ids": ["1.0"]}),
        ):
            with self.subTest(body=body):
                self.assertEqual(self.client.post(url, data=body, content_type="application/json").status_code, 400)

    def test_render_timeout_terminates_isolated_worker(self):
        class Process:
            exitcode = None
            def start(self): pass
            def join(self, timeout): pass
            def is_alive(self): return True
            def terminate(self): self.terminated = True
        process = Process()
        context = type("Context", (), {"Process": lambda *args, **kwargs: process})()
        with patch("lectures.content.multiprocessing.get_context", return_value=context), self.assertRaisesRegex(RuntimeError, "time limit"):
            _render_page_bounded(Path("input.pdf"), 0, Path("output.png"))
        self.assertTrue(process.terminated)

    @override_settings(CONTENT_PDF_TEXT_TIMEOUT_SECONDS=0)
    def test_pdf_text_timeout_terminates_isolated_worker(self):
        class Process:
            exitcode = None
            def start(self): pass
            def join(self, timeout): pass
            def is_alive(self): return True
            def terminate(self): self.terminated = True
        process = Process()
        context = type("Context", (), {"Process": lambda *args, **kwargs: process})()
        with patch("lectures.content.multiprocessing.get_context", return_value=context), self.assertRaisesRegex(RuntimeError, "time limit"):
            _extract_pdf_text_bounded(Path("input.pdf"), Path("output"))
        self.assertTrue(process.terminated)

    def test_mixed_text_and_scanned_pdf_preserves_methods_and_requires_review(self):
        source = self.upload(data=synthetic_pdf(2), name="mixed.pdf")
        class Page:
            mediabox = type("Box", (), {"width": 72, "height": 72})()
            def __init__(self, text): self.text = text
            def extract_text(self): return self.text
        class Reader: pages = [Page("native"), Page("")]
        def render(source_path, index, output):
            output.write_bytes(synthetic_image().read())
        def native(source_path, output):
            (output / "native-0001.txt").write_text("native", encoding="utf-8")
            (output / "native-0002.txt").write_text("", encoding="utf-8")
        with patch("lectures.content.PdfReader", return_value=Reader()), patch("lectures.content._extract_pdf_text_bounded", side_effect=native), patch("lectures.content._render_page_bounded", side_effect=render), patch("lectures.content._ocr_image", return_value=("اردو English", 98)):
            extraction = extract_source(source)
        self.assertEqual(list(extraction.pages.values_list("method", flat=True)), [ExtractedPage.Method.PDF_TEXT, ExtractedPage.Method.OCR])
        self.assertEqual(extraction.status, ExtractionVersion.Status.REVIEW_REQUIRED)

    @override_settings(CONTENT_MAX_DERIVED_BYTES=2)
    def test_cumulative_output_bytes_fail_safely(self):
        source = self.upload()
        with patch("lectures.content._ocr_image", return_value=("long text", 90)), self.assertRaises(ValidationError):
            extract_source(source)
        self.assertFalse(Path(self.tmp.name, "derived", str(source.pk)).exists())

    def test_http_upload_permissions_chapter_validation_and_csrf(self):
        url = "/api/content-sources/"
        payload = {"chapter_id": self.chapter.pk, "title": "Synthetic", "source_type": ContentSource.SourceType.TEACHER, "rights_confirmed": "true", "file": synthetic_image()}
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        self.client.force_login(User.objects.create_user("unassigned"))
        self.assertEqual(self.client.post(url, payload).status_code, 403)
        self.client.force_login(self.teacher)
        malformed = dict(payload, chapter_id="not-a-number", file=synthetic_image())
        self.assertEqual(self.client.post(url, malformed).status_code, 400)
        other_chapter = Chapter.objects.create(course=Course.objects.create(code="X", title="X", teacher=self.other), number=1, title="X")
        crossed = dict(payload, chapter_id=other_chapter.pk, file=synthetic_image())
        self.assertEqual(self.client.post(url, crossed).status_code, 403)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.teacher)
        self.assertEqual(csrf_client.post(url, payload).status_code, 403)

    def test_teacher_cannot_create_institutional_but_admin_can(self):
        with self.assertRaises(PermissionDenied):
            self.upload(self.teacher, ContentSource.SourceType.INSTITUTIONAL)
        source = self.upload(self.admin, ContentSource.SourceType.INSTITUTIONAL)
        self.assertIsNone(source.owner)

    def test_admin_provenance_models_are_read_only_and_role_scoped(self):
        request = RequestFactory().get("/admin/")
        staff = User.objects.create_user("staff", is_staff=True)
        source = self.upload()
        for model_admin in (
            ContentSourceAdmin(ContentSource, django_admin.site),
            ContentFileAdmin(ContentFile, django_admin.site),
            ExtractionVersionAdmin(ExtractionVersion, django_admin.site),
            ExtractedPageAdmin(ExtractedPage, django_admin.site),
        ):
            request.user = staff
            self.assertFalse(model_admin.has_add_permission(request))
            self.assertFalse(model_admin.has_change_permission(request, source if isinstance(model_admin, ContentSourceAdmin) else None))
            self.assertFalse(model_admin.has_delete_permission(request))
        request.user = self.admin
        source_admin = ContentSourceAdmin(ContentSource, django_admin.site)
        self.assertFalse(source_admin.has_add_permission(request))
        self.assertFalse(source_admin.has_change_permission(request, source))
        self.assertFalse(source_admin.has_delete_permission(request, source))

    def test_database_rejects_invalid_ocr_review_provenance(self):
        source = self.upload()
        extraction = ExtractionVersion.objects.create(
            source=source, version=1, status=ExtractionVersion.Status.PROCESSING, extractor="synthetic"
        )
        with self.assertRaises(IntegrityError):
            ExtractedPage.objects.create(
                extraction=extraction,
                source_file=source.original_file,
                page_number=1,
                method=ExtractedPage.Method.OCR,
                text_storage_key="synthetic/page.txt",
                text_sha256="0" * 64,
                requires_review=False,
                review_status=ExtractedPage.ReviewStatus.NOT_REQUIRED,
            )
