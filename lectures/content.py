from __future__ import annotations

import csv
import hashlib
import io
import multiprocessing
import os
import re
import shutil
import subprocess
import uuid
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, models, transaction
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


def _remove_known_tree(path: Path, expected_parent: Path) -> None:
    """Remove only an exact operation-owned staging/derived directory."""
    resolved = path.resolve()
    parent = expected_parent.resolve()
    if resolved == parent or parent not in resolved.parents:
        raise RuntimeError("Refused unsafe cleanup target.")
    if resolved.exists():
        shutil.rmtree(resolved)


def validate_filename(name: str) -> str:
    if not name or len(name) > 255 or not SAFE_NAME.fullmatch(name):
        raise ValidationError("Unsafe upload filename.")
    if Path(name).name != name or Path(name).stem.upper() in WINDOWS_RESERVED or name.endswith((".", " ")):
        raise ValidationError("Unsafe upload filename.")
    extension = Path(name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValidationError("Unsupported upload type.")
    return extension


def _pdf_dimensions(reader: PdfReader) -> None:
    if not 1 <= len(reader.pages) <= settings.CONTENT_MAX_PDF_PAGES:
        raise ValidationError("PDF page count exceeds the safe limit.")
    for page in reader.pages:
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        if width <= 0 or height <= 0 or width > settings.CONTENT_MAX_PDF_PAGE_WIDTH_POINTS or height > settings.CONTENT_MAX_PDF_PAGE_HEIGHT_POINTS:
            raise ValidationError("PDF page dimensions exceed the safe limit.")
        scale = settings.CONTENT_PDF_RENDER_SCALE
        pixels = int(width * scale / 72) * int(height * scale / 72)
        if pixels > settings.CONTENT_MAX_RENDERED_PAGE_PIXELS:
            raise ValidationError("PDF render dimensions exceed the safe pixel limit.")


def _validate_image(content: bytes, expected: str) -> None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                width, height = image.size
                if width > settings.CONTENT_MAX_IMAGE_WIDTH or height > settings.CONTENT_MAX_IMAGE_HEIGHT or width * height > settings.CONTENT_MAX_IMAGE_PIXELS:
                    raise ValidationError("Image dimensions exceed the safe limit.")
                image.verify()
                actual = image.format
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValidationError("Corrupted or unsafe image.") from exc
    if (expected == "image/png" and actual != "PNG") or (expected == "image/jpeg" and actual != "JPEG"):
        raise ValidationError("Image extension and signature do not match.")


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
            _pdf_dimensions(reader)
            pages = len(reader.pages)
        except ValidationError:
            raise
        except Exception as exc:
            raise ValidationError("Corrupted or unsupported PDF.") from exc
    else:
        _validate_image(content, expected)
    return ValidatedUpload(name, extension, expected, len(content), hashlib.sha256(content).hexdigest(), content, pages)


def sources_visible_to(user):
    queryset = ContentSource.objects.select_related("chapter__course", "owner")
    if not user.is_authenticated:
        return queryset.none()
    if user.groups.filter(name=ADMINISTRATOR_ROLE).exists():
        return queryset
    if user.groups.filter(name=TEACHER_ROLE).exists():
        return queryset.filter(models.Q(source_type=ContentSource.SourceType.INSTITUTIONAL, chapter__course__teacher=user) | models.Q(source_type=ContentSource.SourceType.TEACHER, owner=user))
    return queryset.none()


def _require_source_policy(actor, source_type: str, chapter):
    if not actor.is_authenticated or not actor.has_perm("lectures.add_contentsource"):
        raise PermissionDenied("Missing content-source registration permission.")
    is_admin = actor.groups.filter(name=ADMINISTRATOR_ROLE).exists()
    is_teacher = actor.groups.filter(name=TEACHER_ROLE).exists()
    if source_type == ContentSource.SourceType.INSTITUTIONAL:
        if not is_admin:
            raise PermissionDenied("Only administrators may register institutional sources.")
        return ContentSource.AccessScope.AUTHORIZED_TEACHERS, None
    if source_type == ContentSource.SourceType.TEACHER:
        if not (is_teacher and chapter.course.teacher_id == actor.pk):
            raise PermissionDenied("Teacher upload is outside the actor's course scope.")
        return ContentSource.AccessScope.OWNER_AND_ADMINS, actor
    raise ValidationError("Unsupported source type.")


def register_upload(*, actor, chapter, title: str, source_type: str, rights_confirmed: bool, upload, filename: str) -> ContentSource:
    if not rights_confirmed:
        raise ValidationError("Authorization and rights confirmation is required.")
    clean_title = title.strip()
    if not clean_title:
        raise ValidationError("A source title is required.")
    scope, owner = _require_source_policy(actor, source_type, chapter)
    validated = validate_upload(upload, filename)
    token = uuid.uuid4().hex
    staging = _contained(f"staging/registration-{token}.part")
    target = _contained(f"originals/{token}{validated.extension}")
    staging.parent.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    registered = False
    try:
        with staging.open("xb") as handle:
            handle.write(validated.content)
            handle.flush()
            os.fsync(handle.fileno())
        with transaction.atomic():
            source = ContentSource.objects.create(chapter=chapter, source_type=source_type, access_scope=scope, owner=owner, title=clean_title, rights_confirmed=True, rights_confirmed_by=actor, rights_confirmed_at=timezone.now(), page_count=validated.page_count, processing_state=ContentSource.ProcessingState.REGISTERED)
            ContentFile.objects.create(source=source, original_name=validated.original_name, storage_key=f"originals/{token}{validated.extension}", extension=validated.extension, media_type=validated.media_type, byte_size=validated.byte_size, sha256=validated.sha256)
            if target.exists():
                raise ValidationError("Immutable destination already exists.")
            # Hard-link finalization is same-volume, atomic, and refuses overwrite.
            os.link(staging, target)
            staging.unlink()
        registered = True
        return source
    finally:
        if staging.exists():
            staging.unlink()
        if not registered and target.exists():
            target.unlink()


def _ocr_image(image_path: Path, tesseract: Path, tessdata: Path):
    for required in (tesseract, tessdata / "urd.traineddata", tessdata / "eng.traineddata", tessdata / "osd.traineddata"):
        if not required.is_file():
            raise FileNotFoundError("Required local OCR dependency is unavailable.")
    command = [str(tesseract), str(image_path), "stdout", "--tessdata-dir", str(tessdata), "-l", "urd+eng", "--oem", "1", "--psm", "1", "tsv"]
    try:
        result = subprocess.run(command, capture_output=True, check=False, timeout=settings.CONTENT_OCR_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Local OCR exceeded the safe time limit.") from exc
    if result.returncode != 0:
        raise RuntimeError("Local OCR failed safely.")
    rows = list(csv.DictReader(io.StringIO(result.stdout.decode("utf-8", errors="strict")), delimiter="\t"))
    words, confidences, last_line = [], [], None
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


def _render_worker(pdf_path: str, page_index: int, scale: float, output_path: str) -> None:
    import pypdfium2 as pdfium
    document = pdfium.PdfDocument(pdf_path)
    document[page_index].render(scale=scale).to_pil().save(output_path, format="PNG")


def _pdf_text_worker(pdf_path: str, output_dir: str, max_page_bytes: int) -> None:
    reader = PdfReader(pdf_path, strict=True)
    target = Path(output_dir)
    for index, page in enumerate(reader.pages, start=1):
        encoded = (page.extract_text() or "").strip().encode("utf-8")
        if len(encoded) > max_page_bytes:
            raise RuntimeError("PDF page text exceeds safe output limit.")
        (target / f"native-{index:04d}.txt").write_bytes(encoded)


def _extract_pdf_text_bounded(source_path: Path, output_dir: Path) -> None:
    process = multiprocessing.get_context("spawn").Process(
        target=_pdf_text_worker,
        args=(str(source_path), str(output_dir), settings.CONTENT_MAX_PAGE_TEXT_BYTES),
    )
    process.start()
    process.join(settings.CONTENT_PDF_TEXT_TIMEOUT_SECONDS)
    if process.is_alive():
        process.terminate()
        process.join(5)
        raise RuntimeError("PDF text extraction exceeded the safe time limit.")
    if process.exitcode != 0:
        raise RuntimeError("PDF text extraction failed safely.")


def _render_page_bounded(source_path: Path, page_index: int, output_path: Path) -> None:
    process = multiprocessing.get_context("spawn").Process(target=_render_worker, args=(str(source_path), page_index, settings.CONTENT_PDF_RENDER_SCALE, str(output_path)))
    process.start()
    process.join(settings.CONTENT_RENDER_TIMEOUT_SECONDS)
    if process.is_alive():
        process.terminate()
        process.join(5)
        raise RuntimeError("PDF rendering exceeded the safe time limit.")
    if process.exitcode != 0 or not output_path.is_file():
        raise RuntimeError("PDF rendering failed safely.")


def _allocate_extraction(source_id: int) -> ExtractionVersion:
    for _ in range(3):
        try:
            with transaction.atomic():
                locked = ContentSource.objects.select_for_update().get(pk=source_id)
                version = (locked.extractions.order_by("-version").values_list("version", flat=True).first() or 0) + 1
                extraction = ExtractionVersion.objects.create(source=locked, version=version, status=ExtractionVersion.Status.PROCESSING, extractor="pypdf-6.14.2/tesseract-5.4.0")
                locked.processing_state = ContentSource.ProcessingState.PROCESSING
                locked.save(update_fields=("processing_state", "updated_at"))
                return extraction
        except IntegrityError:
            continue
    raise RuntimeError("Could not allocate a collision-free extraction version.")


def _review_flags(text: str, confidence: float | None) -> list[str]:
    flags = ["OCR_ADVISORY", "VERIFY_READING_ORDER"]
    if confidence is None or confidence < LOW_CONFIDENCE:
        flags.append("LOW_OR_UNKNOWN_CONFIDENCE")
    if any("\u0600" <= char <= "\u06ff" for char in text) and any(char.isascii() and char.isalpha() for char in text):
        flags.append("MIXED_URDU_ENGLISH_DIRECTION")
    if any(mark in text for mark in ("=", "∑", "√", "|", "\t")):
        flags.append("COMPLEX_LAYOUT_EQUATION_OR_TABLE")
    return flags


def extract_source(source: ContentSource, *, tesseract_path: Path | None = None, tessdata_path: Path | None = None) -> ExtractionVersion:
    source = ContentSource.objects.select_related("original_file").get(pk=source.pk)
    original = source.original_file
    source_path = _contained(original.storage_key)
    if source_path.stat().st_size != original.byte_size or hashlib.sha256(source_path.read_bytes()).hexdigest() != original.sha256:
        source.processing_state = ContentSource.ProcessingState.COMPROMISED
        source.save(update_fields=("processing_state", "updated_at"))
        raise RuntimeError("Immutable original failed integrity verification.")
    extraction = _allocate_extraction(source.pk)
    staging = _contained(f"staging/extraction-{extraction.pk}-{uuid.uuid4().hex}")
    final = _contained(f"derived/{source.pk}/v{extraction.version}")
    staging.mkdir(parents=True, exist_ok=False)
    final_created = False
    pages = []
    total_pixels = total_bytes = 0
    try:
        if original.extension == ".pdf":
            reader = PdfReader(str(source_path), strict=True)
            _pdf_dimensions(reader)
            _extract_pdf_text_bounded(source_path, staging)
            for index, page in enumerate(reader.pages, start=1):
                native_path = staging / f"native-{index:04d}.txt"
                text = native_path.read_text(encoding="utf-8")
                native_path.unlink()
                if text:
                    pages.append((index, text, ExtractedPage.Method.PDF_TEXT, None, []))
                    continue
                width, height = float(page.mediabox.width), float(page.mediabox.height)
                pixels = int(width * settings.CONTENT_PDF_RENDER_SCALE / 72) * int(height * settings.CONTENT_PDF_RENDER_SCALE / 72)
                total_pixels += pixels
                if total_pixels > settings.CONTENT_MAX_RENDERED_TOTAL_PIXELS:
                    raise ValidationError("Cumulative rendered pixels exceed the safe limit.")
                image_path = staging / f"page-{index:04d}.png"
                _render_page_bounded(source_path, index - 1, image_path)
                total_bytes += image_path.stat().st_size
                if total_bytes > settings.CONTENT_MAX_DERIVED_BYTES:
                    raise ValidationError("Cumulative derived output exceeds the safe limit.")
                text, confidence = _ocr_image(image_path, tesseract_path or Path(settings.CONTENT_TESSERACT_PATH), tessdata_path or Path(settings.CONTENT_TESSDATA_PATH))
                pages.append((index, text, ExtractedPage.Method.OCR, confidence, _review_flags(text, confidence)))
        else:
            text, confidence = _ocr_image(source_path, tesseract_path or Path(settings.CONTENT_TESSERACT_PATH), tessdata_path or Path(settings.CONTENT_TESSDATA_PATH))
            pages.append((1, text, ExtractedPage.Method.OCR, confidence, _review_flags(text, confidence)))
        # Integrity is the final gate before any extraction can become successful.
        if source_path.stat().st_size != original.byte_size or hashlib.sha256(source_path.read_bytes()).hexdigest() != original.sha256:
            raise RuntimeError("FINAL_INTEGRITY_MISMATCH")
        for page_number, text, _, _, _ in pages:
            encoded = text.encode("utf-8")
            total_bytes += len(encoded)
            if total_bytes > settings.CONTENT_MAX_DERIVED_BYTES:
                raise ValidationError("Cumulative derived output exceeds the safe limit.")
            (staging / f"page-{page_number:04d}.txt").write_bytes(encoded)
        with transaction.atomic():
            locked_source = ContentSource.objects.select_for_update().get(pk=source.pk)
            if final.exists():
                raise RuntimeError("Extraction output version already exists.")
            final.parent.mkdir(parents=True, exist_ok=True)
            staging.rename(final)
            final_created = True
            any_ocr = False
            for page_number, text, method, confidence, flags in pages:
                encoded = text.encode("utf-8")
                any_ocr = any_ocr or method == ExtractedPage.Method.OCR
                ExtractedPage.objects.create(extraction=extraction, source_file=original, page_number=page_number, method=method, text_storage_key=f"derived/{source.pk}/v{extraction.version}/page-{page_number:04d}.txt", text_sha256=hashlib.sha256(encoded).hexdigest(), character_count=len(text), mean_confidence=confidence, requires_review=method == ExtractedPage.Method.OCR, review_status=ExtractedPage.ReviewStatus.PENDING if method == ExtractedPage.Method.OCR else ExtractedPage.ReviewStatus.NOT_REQUIRED, review_flags=flags)
            extraction.status = ExtractionVersion.Status.REVIEW_REQUIRED if any_ocr else ExtractionVersion.Status.COMPLETE
            extraction.completed_at = timezone.now()
            extraction.save(update_fields=("status", "completed_at"))
            locked_source.processing_state = ContentSource.ProcessingState.REVIEW_REQUIRED if any_ocr else ContentSource.ProcessingState.READY
            locked_source.page_count = len(pages)
            locked_source.save(update_fields=("processing_state", "page_count", "updated_at"))
        return extraction
    except Exception as exc:
        mismatch = str(exc) == "FINAL_INTEGRITY_MISMATCH"
        with transaction.atomic():
            extraction.status = ExtractionVersion.Status.FAILED
            extraction.error_code = "ORIGINAL_INTEGRITY_MISMATCH" if mismatch else "LOCAL_EXTRACTION_FAILED"
            extraction.completed_at = timezone.now()
            extraction.save(update_fields=("status", "error_code", "completed_at"))
            source.processing_state = ContentSource.ProcessingState.COMPROMISED if mismatch else ContentSource.ProcessingState.FAILED
            source.save(update_fields=("processing_state", "updated_at"))
        raise
    finally:
        if staging.exists():
            _remove_known_tree(staging, _contained("staging"))
        if final_created and extraction.status == ExtractionVersion.Status.FAILED and final.exists():
            derived_source = _contained(f"derived/{source.pk}")
            _remove_known_tree(final, derived_source)
            if derived_source.exists() and not any(derived_source.iterdir()):
                derived_source.rmdir()


@transaction.atomic
def approve_ocr_extraction(*, actor, extraction: ExtractionVersion) -> ExtractionVersion:
    locked = ExtractionVersion.objects.select_for_update().select_related("source__chapter__course").get(pk=extraction.pk)
    if not actor.is_authenticated or not actor.groups.filter(name=TEACHER_ROLE).exists() or locked.source.chapter.course.teacher_id != actor.pk or not actor.has_perm("lectures.change_extractedpage"):
        raise PermissionDenied("Only the assigned authorized teacher may approve OCR pages.")
    pending = locked.pages.filter(method=ExtractedPage.Method.OCR, review_status=ExtractedPage.ReviewStatus.PENDING)
    if not pending.exists():
        raise ValidationError("No pending OCR pages are available for review.")
    now = timezone.now()
    pending.update(review_status=ExtractedPage.ReviewStatus.APPROVED, reviewed_by=actor, reviewed_at=now, requires_review=False)
    locked.status = ExtractionVersion.Status.COMPLETE
    locked.save(update_fields=("status",))
    locked.source.processing_state = ContentSource.ProcessingState.READY
    locked.source.save(update_fields=("processing_state", "updated_at"))
    return locked
