from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class Course(models.Model):
    code = models.CharField(max_length=32, unique=True)
    title = models.CharField(max_length=200)
    class_name = models.CharField(max_length=100, blank=True)
    subject_name = models.CharField(max_length=100, blank=True)
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="courses_taught",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("code",)
        indexes = [models.Index(fields=("teacher", "is_active"), name="course_teacher_active_idx")]

    def __str__(self) -> str:
        return f"{self.code} — {self.title}"


class Chapter(models.Model):
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="chapters")
    number = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("course", "number")
        constraints = [
            models.UniqueConstraint(fields=("course", "number"), name="unique_chapter_number"),
            models.CheckConstraint(condition=Q(number__gte=1), name="chapter_number_positive"),
        ]
        indexes = [models.Index(fields=("course", "number"), name="chapter_course_number_idx")]

    def __str__(self) -> str:
        return f"{self.course.code} / {self.number}: {self.title}"


class LectureRequest(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    chapter = models.ForeignKey(Chapter, on_delete=models.PROTECT, related_name="lecture_requests")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="lecture_requests",
    )
    title = models.CharField(max_length=200)
    learning_objectives = models.TextField()
    status = models.CharField(max_length=16, choices=Status, default=Status.DRAFT)
    requested_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-requested_at", "pk")
        constraints = [
            models.CheckConstraint(
                condition=~Q(learning_objectives=""),
                name="lecture_objectives_not_empty",
            )
        ]
        indexes = [
            models.Index(fields=("requested_by", "status"), name="lecture_requester_status_idx"),
            models.Index(fields=("chapter", "status"), name="lecture_chapter_status_idx"),
        ]

    def __str__(self) -> str:
        return self.title


class ContentSource(models.Model):
    class SourceType(models.TextChoices):
        INSTITUTIONAL = "INSTITUTIONAL", "Institutional textbook or notes"
        TEACHER = "TEACHER", "Teacher-owned upload"

    class AccessScope(models.TextChoices):
        AUTHORIZED_TEACHERS = "AUTHORIZED_TEACHERS", "Authorized teachers"
        OWNER_AND_ADMINS = "OWNER_AND_ADMINS", "Owner and administrators"

    class ProcessingState(models.TextChoices):
        REGISTERED = "REGISTERED", "Registered"
        READY = "READY", "Ready"
        PROCESSING = "PROCESSING", "Processing"
        REVIEW_REQUIRED = "REVIEW_REQUIRED", "Teacher review required"
        FAILED = "FAILED", "Failed safely"
        COMPROMISED = "COMPROMISED", "Original integrity mismatch"

    chapter = models.ForeignKey(Chapter, on_delete=models.PROTECT, related_name="content_sources")
    source_type = models.CharField(max_length=20, choices=SourceType)
    access_scope = models.CharField(max_length=24, choices=AccessScope)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_content_sources",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=200)
    rights_confirmed = models.BooleanField(default=False)
    rights_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="rights_confirmed_sources",
        null=True,
        blank=True,
    )
    rights_confirmed_at = models.DateTimeField(null=True, blank=True)
    page_count = models.PositiveIntegerField(default=0)
    processing_state = models.CharField(
        max_length=24,
        choices=ProcessingState,
        default=ProcessingState.REGISTERED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("chapter", "title", "pk")
        constraints = [
            models.CheckConstraint(
                condition=(Q(source_type="INSTITUTIONAL", owner__isnull=True) | Q(source_type="TEACHER", owner__isnull=False)),
                name="content_source_owner_matches_type",
            ),
            models.CheckConstraint(
                condition=(
                    Q(source_type="INSTITUTIONAL", access_scope="AUTHORIZED_TEACHERS")
                    | Q(source_type="TEACHER", access_scope="OWNER_AND_ADMINS")
                ),
                name="content_source_scope_matches_type",
            ),
        ]
        indexes = [
            models.Index(fields=("chapter", "source_type"), name="content_chapter_type_idx"),
            models.Index(fields=("owner", "processing_state"), name="content_owner_state_idx"),
        ]

    def __str__(self) -> str:
        return self.title


class ContentFile(models.Model):
    source = models.OneToOneField(ContentSource, on_delete=models.PROTECT, related_name="original_file")
    original_name = models.CharField(max_length=255)
    storage_key = models.CharField(max_length=255, unique=True)
    extension = models.CharField(max_length=8)
    media_type = models.CharField(max_length=40)
    byte_size = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=("sha256",), name="content_file_sha_idx")]

    def save(self, *args, **kwargs):
        if self.pk and ContentFile.objects.filter(pk=self.pk).exists():
            raise ValueError("Original content-file records are immutable.")
        return super().save(*args, **kwargs)


class ExtractionVersion(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETE = "COMPLETE", "Complete"
        REVIEW_REQUIRED = "REVIEW_REQUIRED", "Teacher review required"
        FAILED = "FAILED", "Failed safely"

    source = models.ForeignKey(ContentSource, on_delete=models.PROTECT, related_name="extractions")
    version = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    status = models.CharField(max_length=24, choices=Status, default=Status.PENDING)
    extractor = models.CharField(max_length=100)
    error_code = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("source", "version")
        constraints = [
            models.UniqueConstraint(fields=("source", "version"), name="unique_source_extraction_version")
        ]


class ExtractedPage(models.Model):
    class ReviewStatus(models.TextChoices):
        NOT_REQUIRED = "NOT_REQUIRED", "Not required"
        PENDING = "PENDING", "Teacher review pending"
        APPROVED = "APPROVED", "Teacher approved"

    class Method(models.TextChoices):
        PDF_TEXT = "PDF_TEXT", "PDF text layer"
        OCR = "OCR", "Local OCR"

    extraction = models.ForeignKey(ExtractionVersion, on_delete=models.PROTECT, related_name="pages")
    source_file = models.ForeignKey(ContentFile, on_delete=models.PROTECT, related_name="extracted_pages")
    page_number = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    method = models.CharField(max_length=16, choices=Method)
    text_storage_key = models.CharField(max_length=255)
    text_sha256 = models.CharField(max_length=64)
    character_count = models.PositiveIntegerField(default=0)
    mean_confidence = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    requires_review = models.BooleanField(default=False)
    review_status = models.CharField(max_length=16, choices=ReviewStatus, default=ReviewStatus.NOT_REQUIRED)
    review_flags = models.JSONField(default=list, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="reviewed_extracted_pages",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("extraction", "page_number")
        constraints = [
            models.UniqueConstraint(fields=("extraction", "page_number"), name="unique_extraction_page"),
            models.CheckConstraint(
                condition=(
                    Q(method="PDF_TEXT", requires_review=False, review_status="NOT_REQUIRED", reviewed_by__isnull=True, reviewed_at__isnull=True)
                    | Q(method="OCR", requires_review=True, review_status="PENDING", reviewed_by__isnull=True, reviewed_at__isnull=True)
                    | Q(method="OCR", requires_review=False, review_status="APPROVED", reviewed_by__isnull=False, reviewed_at__isnull=False)
                ),
                name="extracted_page_review_invariants",
            ),
        ]
        indexes = [
            models.Index(fields=("source_file", "page_number"), name="content_file_page_idx")
        ]
