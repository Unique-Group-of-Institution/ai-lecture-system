from __future__ import annotations

import csv
import hashlib
import io
import os
import re
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.utils import timezone
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader

from .models import ContentFile, ContentSource, ExtractedPage, ExtractionVersion
from .roles import ADMINISTRATOR_ROLE, TEACHER_ROLE

ALLOWED_EXTENSIONS = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
SAFE_NAME = re.compile(r"^[^\x00-\x1f<>:\"/\\|?*]+$")
WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
LOW_CONFIDENCE = 70.0


@dataclass(frozen=True)
class ValidatedUpload:
    original_name: str
    extension: str
    media_type: str
    byte_size: int
    sha256: str
    content: bytes
    page_count: int


def storage_root() -> Path:
    root = Path(settings.CONTENT_STORAGE_ROOT).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _contained(relative: str) -> Path:
    if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValidationError("Unsafe local storage path.")
    root = storage_root()
    result = (root / relative).resolve()
    if result != root and root not in result.parents:
        raise ValidationError("Unsafe local storage path.")
    return result


def validate_filename(name: str) -> str:
    if not name or len(name) > 255 or not SAFE_NAME.fullmatch(name):
        raise ValidationError("Unsafe upload filename.")
    if Path(name).name != name or Path(name).stem.upper() in WINDOWS_RESERVED or name.endswith((".", " ")):
        raise ValidationError("Unsafe upload filename.")
    extension = Path(name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValidationError("Unsupported upload type.")
    return extension


def validate_upload(upload: BinaryIO, name: str, max_bytes: int | None = None) -> ValidatedUpload:
    extension = validate_filename(name)
    limit = max_bytes or settings.CONTENT_MAX_UPLOAD_BYTES
    content = upload.read(limit + 1)
    if not content or len(content) > limit:
        raise ValidationError("Upload is empty or exceeds the size limit.")
    if content.startswith(b"MZ"):
        raise ValidationError("Executable uploads are forbidden.")
    expected = ALLOWED_EXTENSIONS[extension]
    pages = 1
    if extension == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise ValidationError("PDF extension and signature do not match.")
        try:
            reader = PdfReader(io.BytesIO(content), strict=True)
            pages = len(reader.pages)
        except Exception as exc:
            raise ValidationError("Corrupted or unsupported PDF.") from exc
        if pages < 1:
            raise ValidationError("PDF contains no pages.")
    else:
        try:
            with Image.open(io.BytesIO(content)) as image:
                image.verify()
                actual = image.format
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise ValidationError("Corrupted or unsafe image.") from exc
        if (expected == "image/png" and actual != "PNG") or (expected == "image/jpeg" and actual != "JPEG"):
            raise ValidationError("Image extension and signature do not match.")
    return ValidatedUpload(name, extension, expected, len(content), hashlib.sha256(content).hexdigest(), content, pages)


def sources_visible_to(user):
    queryset = ContentSource.objects.select_related("chapter__course", "owner")
    if not user.is_authenticated:
        return queryset.none()
    if user.groups.filter(name=ADMINISTRATOR_ROLE).exists():
        return queryset
    if user.groups.filter(name=TEACHER_ROLE).exists():
        return queryset.filter(
            models.Q(source_type=ContentSource.SourceType.INSTITUTIONAL, chapter__course__teacher=user)
            | models.Q(source_type=ContentSource.SourceType.TEACHER, owner=user)
        )
    return queryset.none()


def _require_source_policy(actor, source_type: str, chapter) -> tuple[str, object | None]:
    is_admin = actor.groups.filter(name=ADMINISTRATOR_ROLE).exists()
    is_teacher = actor.groups.filter(name=TEACHER_ROLE).exists()
    if source_type == ContentSource.SourceType.INSTITUTIONAL:
        if not is_admin:
            raise PermissionDenied("Only administrators may register institutional sources.")
        return ContentSource.AccessScope.AUTHORIZED_TEACHERS, None
    if source_type == ContentSource.SourceType.TEACHER:
        if not (is_admin or (is_teacher and chapter.course.teacher_id == actor.pk)):
            raise PermissionDenied("Teacher upload is outside the actor's course scope.")
        return ContentSource.AccessScope.OWNER_AND_ADMINS, actor
    raise ValidationError("Unsupported source type.")


@transaction.atomic
def register_upload(*, actor, chapter, title: str, source_type: str, rights_confirmed: bool, upload, filename: str) -> ContentSource:
    if not rights_confirmed:
        raise ValidationError("Authorization and rights confirmation is required.")
    clean_title = title.strip()
    if not clean_title:
        raise ValidationError("A source title is required.")
    scope, owner = _require_source_policy(actor, source_type, chapter)
    validated = validate_upload(upload, filename)
    key = f"originals/{uuid.uuid4().hex}{validated.extension}"
    target = _contained(key)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("xb") as handle:
            handle.write(validated.content)
    except FileExistsError as exc:
        raise ValidationError("Immutable destination already exists.") from exc
    source = ContentSource.objects.create(
        chapter=chapter,
        source_type=source_type,
        access_scope=scope,
        owner=owner,
        title=clean_title,
        rights_confirmed=True,
        rights_confirmed_by=actor,
        rights_confirmed_at=timezone.now(),
        page_count=validated.page_count,
        processing_state=ContentSource.ProcessingState.READY,
    )
    ContentFile.objects.create(
        source=source,
        original_name=validated.original_name,
        storage_key=key,
        extension=validated.extension,
        media_type=validated.media_type,
        byte_size=validated.byte_size,
        sha256=validated.sha256,
    )
    return source


def _ocr_image(image_path: Path, tesseract: Path, tessdata: Path) -> tuple[str, float | None]:
    for required in (tesseract, tessdata / "urd.traineddata", tessdata / "eng.traineddata", tessdata / "osd.traineddata"):
        if not required.is_file():
            raise FileNotFoundError("Required local OCR dependency is unavailable.")
    command = [
        str(tesseract), str(image_path), "stdout", "--tessdata-dir", str(tessdata),
        "-l", "urd+eng", "--oem", "1", "--psm", "1", "tsv",
    ]
    result = subprocess.run(command, capture_output=True, check=False, timeout=settings.CONTENT_OCR_TIMEOUT_SECONDS)
    if result.returncode != 0:
        raise RuntimeError("Local OCR failed safely.")
    decoded = result.stdout.decode("utf-8", errors="strict")
    rows = list(csv.DictReader(io.StringIO(decoded), delimiter="\t"))
    words: list[str] = []
    confidences: list[float] = []
    last_line = None
    for row in rows:
        word = (row.get("text") or "").strip()
        if not word:
            continue
        line = (row.get("block_num"), row.get("par_num"), row.get("line_num"))
        if words and line != last_line:
            words.append("\n")
        words.append(word)
        last_line = line
        try:
            confidence = float(row.get("conf", "-1"))
            if confidence >= 0:
                confidences.append(confidence)
        except ValueError:
            pass
    text = " ".join(words).replace(" \n ", "\n").strip()
    return text, (sum(confidences) / len(confidences) if confidences else None)


def extract_source(source: ContentSource, *, tesseract_path: Path | None = None, tessdata_path: Path | None = None) -> ExtractionVersion:
    original = source.original_file
    source_path = _contained(original.storage_key)
    before = (source_path.stat().st_size, hashlib.sha256(source_path.read_bytes()).hexdigest())
    version_number = (source.extractions.order_by("-version").values_list("version", flat=True).first() or 0) + 1
    extraction = ExtractionVersion.objects.create(source=source, version=version_number, status=ExtractionVersion.Status.PROCESSING, extractor="pypdf-6.14.2/tesseract-5.4.0")
    source.processing_state = ContentSource.ProcessingState.PROCESSING
    source.save(update_fields=("processing_state", "updated_at"))
    derived_dir = _contained(f"derived/{source.pk}/v{version_number}")
    derived_dir.mkdir(parents=True, exist_ok=False)
    pages: list[tuple[int, str, str, float | None]] = []
    try:
        if original.extension == ".pdf":
            reader = PdfReader(str(source_path), strict=True)
            import pypdfium2 as pdfium
            render_doc = None
            for index, page in enumerate(reader.pages, start=1):
                text = (page.extract_text() or "").strip()
                if text:
                    pages.append((index, text, ExtractedPage.Method.PDF_TEXT, None))
                    continue
                render_doc = render_doc or pdfium.PdfDocument(str(source_path))
                image_path = derived_dir / f"page-{index:04d}.png"
                render_doc[index - 1].render(scale=2).to_pil().save(image_path, format="PNG")
                text, confidence = _ocr_image(image_path, tesseract_path or Path(settings.CONTENT_TESSERACT_PATH), tessdata_path or Path(settings.CONTENT_TESSDATA_PATH))
                pages.append((index, text, ExtractedPage.Method.OCR, confidence))
        else:
            text, confidence = _ocr_image(source_path, tesseract_path or Path(settings.CONTENT_TESSERACT_PATH), tessdata_path or Path(settings.CONTENT_TESSDATA_PATH))
            pages.append((1, text, ExtractedPage.Method.OCR, confidence))
        review = False
        with transaction.atomic():
            for page_number, text, method, confidence in pages:
                text_key = f"derived/{source.pk}/v{version_number}/page-{page_number:04d}.txt"
                text_path = _contained(text_key)
                encoded = text.encode("utf-8")
                with text_path.open("xb") as handle:
                    handle.write(encoded)
                requires_review = method == ExtractedPage.Method.OCR and (confidence is None or confidence < LOW_CONFIDENCE)
                review = review or requires_review
                ExtractedPage.objects.create(
                    extraction=extraction,
                    source_file=original,
                    page_number=page_number,
                    method=method,
                    text_storage_key=text_key,
                    text_sha256=hashlib.sha256(encoded).hexdigest(),
                    character_count=len(text),
                    mean_confidence=confidence,
                    requires_review=requires_review,
                )
        extraction.status = ExtractionVersion.Status.REVIEW_REQUIRED if review else ExtractionVersion.Status.COMPLETE
        extraction.completed_at = timezone.now()
        extraction.save(update_fields=("status", "completed_at"))
        source.processing_state = ContentSource.ProcessingState.REVIEW_REQUIRED if review else ContentSource.ProcessingState.READY
        source.page_count = len(pages)
        source.save(update_fields=("processing_state", "page_count", "updated_at"))
    except Exception:
        extraction.status = ExtractionVersion.Status.FAILED
        extraction.error_code = "LOCAL_EXTRACTION_FAILED"
        extraction.completed_at = timezone.now()
        extraction.save(update_fields=("status", "error_code", "completed_at"))
        source.processing_state = ContentSource.ProcessingState.FAILED
        source.save(update_fields=("processing_state", "updated_at"))
        raise
    after = (source_path.stat().st_size, hashlib.sha256(source_path.read_bytes()).hexdigest())
    if before != after:
        raise RuntimeError("Immutable original changed during extraction.")
    return extraction
