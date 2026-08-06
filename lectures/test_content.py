import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from PIL import Image
from pypdf import PdfWriter

from .content import _contained, _ocr_image, extract_source, register_upload, sources_visible_to, validate_upload
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
        class Reader:
            pages = [Page("Page one"), Page("Page two")]
        with patch("lectures.content.PdfReader", return_value=Reader()):
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
        with patch("socket.create_connection", side_effect=AssertionError("network forbidden")), patch("lectures.content.subprocess.run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = tsv
            text, confidence = _ocr_image(image, tool, tessdata)
        self.assertEqual((text, confidence), ("English", 90.0))
        command = run.call_args.args[0]
        self.assertIn("urd+eng", command)
        self.assertIn("tsv", command)

    def test_selection_api_combines_only_visible_rights_confirmed_sources(self):
        institutional = self.upload(self.admin, ContentSource.SourceType.INSTITUTIONAL)
        private = self.upload()
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
