from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


WORKFLOW_ACTOR_CHOICES = (
    ("TEACHER", "Teacher"),
    ("ADMINISTRATOR", "Administrator"),
    ("SYSTEM_WORKER", "System worker"),
)


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


class GenerationRequest(models.Model):
    class Status(models.TextChoices):
        GENERATED = "GENERATED", "Generated draft"
        PARTIALLY_APPROVED = "PARTIALLY_APPROVED", "Partially approved"
        APPROVED = "APPROVED", "Teacher approved"

    chapter = models.ForeignKey(Chapter, on_delete=models.PROTECT, related_name="generation_requests")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="generation_requests"
    )
    guidelines = models.JSONField()
    generator_key = models.CharField(max_length=64)
    input_sha256 = models.CharField(max_length=64)
    status = models.CharField(max_length=24, choices=Status, default=Status.GENERATED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "pk")
        indexes = [
            models.Index(fields=("requested_by", "status"), name="generation_actor_status_idx"),
            models.Index(fields=("chapter", "created_at"), name="generation_chapter_time_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            previous = GenerationRequest.objects.filter(pk=self.pk).values(
                "chapter_id", "requested_by_id", "guidelines", "generator_key", "input_sha256"
            ).first()
            current = {name: getattr(self, name) for name in previous} if previous else None
            if previous is not None and current != previous:
                raise ValueError("Generation input records are immutable.")
        return super().save(*args, **kwargs)


class ImmutableGenerationRecord(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValueError("Generation history records are immutable.")
        return super().save(*args, **kwargs)


class GenerationSourceSnapshot(ImmutableGenerationRecord):
    generation = models.ForeignKey(GenerationRequest, on_delete=models.PROTECT, related_name="source_snapshots")
    source = models.ForeignKey(ContentSource, on_delete=models.PROTECT, related_name="generation_snapshots")
    extraction = models.ForeignKey(ExtractionVersion, on_delete=models.PROTECT, related_name="generation_snapshots")
    source_file_sha256 = models.CharField(max_length=64)
    extraction_version = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    source_title = models.CharField(max_length=200)

    class Meta:
        ordering = ("generation", "source_id")
        constraints = [
            models.UniqueConstraint(fields=("generation", "source"), name="unique_generation_source_snapshot")
        ]


class GenerationPageSnapshot(ImmutableGenerationRecord):
    source_snapshot = models.ForeignKey(
        GenerationSourceSnapshot, on_delete=models.PROTECT, related_name="pages"
    )
    extracted_page = models.ForeignKey(ExtractedPage, on_delete=models.PROTECT, related_name="generation_snapshots")
    page_number = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    text = models.TextField()
    text_sha256 = models.CharField(max_length=64)

    class Meta:
        ordering = ("source_snapshot", "page_number")
        constraints = [
            models.UniqueConstraint(
                fields=("source_snapshot", "page_number"), name="unique_generation_snapshot_page"
            ),
            models.CheckConstraint(condition=~Q(text=""), name="generation_snapshot_text_not_empty"),
        ]


class SlideDraft(models.Model):
    generation = models.ForeignKey(GenerationRequest, on_delete=models.PROTECT, related_name="slides")
    position = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    current_version = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    approved_revision = models.ForeignKey(
        "SlideRevision", on_delete=models.PROTECT, null=True, blank=True, related_name="approved_for_slides"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("generation", "position")
        constraints = [
            models.UniqueConstraint(fields=("generation", "position"), name="unique_generation_slide_position")
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            previous = SlideDraft.objects.filter(pk=self.pk).values("generation_id", "position").first()
            if previous is not None and (
                previous["generation_id"] != self.generation_id or previous["position"] != self.position
            ):
                raise ValueError("Slide identity and order are immutable.")
        return super().save(*args, **kwargs)


class SlideRevision(ImmutableGenerationRecord):
    slide = models.ForeignKey(SlideDraft, on_delete=models.PROTECT, related_name="revisions")
    version = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    title = models.CharField(max_length=200)
    created_by_actor_id = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("slide", "version")
        constraints = [
            models.UniqueConstraint(fields=("slide", "version"), name="unique_slide_revision_version")
        ]


class SlideClaim(ImmutableGenerationRecord):
    revision = models.ForeignKey(SlideRevision, on_delete=models.PROTECT, related_name="claims")
    position = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    text = models.TextField()

    class Meta:
        ordering = ("revision", "position")
        constraints = [
            models.UniqueConstraint(fields=("revision", "position"), name="unique_revision_claim_position"),
            models.CheckConstraint(condition=~Q(text=""), name="slide_claim_text_not_empty"),
        ]


class NarrationStatement(ImmutableGenerationRecord):
    revision = models.ForeignKey(SlideRevision, on_delete=models.PROTECT, related_name="narration_statements")
    position = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    text = models.TextField()

    class Meta:
        ordering = ("revision", "position")
        constraints = [
            models.UniqueConstraint(fields=("revision", "position"), name="unique_revision_narration_position"),
            models.CheckConstraint(condition=~Q(text=""), name="narration_statement_text_not_empty"),
        ]


class SourceReference(ImmutableGenerationRecord):
    claim = models.ForeignKey(SlideClaim, on_delete=models.PROTECT, null=True, blank=True, related_name="references")
    narration_statement = models.ForeignKey(
        NarrationStatement, on_delete=models.PROTECT, null=True, blank=True, related_name="references"
    )
    page_snapshot = models.ForeignKey(GenerationPageSnapshot, on_delete=models.PROTECT, related_name="references")
    start_offset = models.PositiveIntegerField()
    end_offset = models.PositiveIntegerField()
    supported_text_sha256 = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(Q(claim__isnull=False, narration_statement__isnull=True) | Q(claim__isnull=True, narration_statement__isnull=False)),
                name="source_reference_exactly_one_target",
            ),
            models.CheckConstraint(condition=Q(end_offset__gt=models.F("start_offset")), name="source_reference_valid_offsets"),
        ]
        indexes = [models.Index(fields=("page_snapshot", "start_offset"), name="source_ref_page_offset_idx")]


class CanonicalNarrationSnapshot(ImmutableGenerationRecord):
    revision = models.OneToOneField(SlideRevision, on_delete=models.PROTECT, related_name="canonical_narration")
    text = models.TextField()
    text_sha256 = models.CharField(max_length=64)
    approved_by_actor_id = models.PositiveBigIntegerField()
    approved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("revision", "approved_at", "pk")


class LectureWorkflow(models.Model):
    class State(models.TextChoices):
        SOURCE_CONTENT_READY = "SOURCE_CONTENT_READY", "Source and content ready"
        SLIDE_NARRATION_DRAFT = "SLIDE_NARRATION_DRAFT", "Slide and narration draft"
        TEACHER_SLIDE_NARRATION_APPROVED = (
            "TEACHER_SLIDE_NARRATION_APPROVED",
            "Teacher approved current slides and narration",
        )
        RECORDING_PENDING = "RECORDING_PENDING", "Recording pending"
        RECORDING_READY = "RECORDING_READY", "Recording ready"
        DRAFT_VIDEO_PENDING = "DRAFT_VIDEO_PENDING", "Draft video pending"
        DRAFT_VIDEO_READY = "DRAFT_VIDEO_READY", "Draft video ready"
        TEACHER_VIDEO_REVISION_REQUESTED = (
            "TEACHER_VIDEO_REVISION_REQUESTED",
            "Teacher requested video revision",
        )
        TEACHER_VIDEO_APPROVED = "TEACHER_VIDEO_APPROVED", "Teacher approved video"
        FINAL_ADMIN_APPROVED = "FINAL_ADMIN_APPROVED", "Final administrator approval"
        EXPORT_READY = "EXPORT_READY", "Export-ready handoff"

    generation = models.OneToOneField(
        GenerationRequest,
        on_delete=models.PROTECT,
        related_name="lecture_workflow",
    )
    state = models.CharField(max_length=48, choices=State, default=State.SOURCE_CONTENT_READY)
    version = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    slide_approval_fingerprint = models.CharField(max_length=64, blank=True)
    recording_reference = models.CharField(max_length=128, blank=True)
    draft_video_reference = models.CharField(max_length=128, blank=True)
    export_reference = models.CharField(max_length=128, blank=True)
    teacher_video_approved_by = models.CharField(max_length=128, blank=True)
    teacher_video_approved_at = models.DateTimeField(null=True, blank=True)
    final_admin_approved_by = models.CharField(max_length=128, blank=True)
    final_admin_approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "pk")
        constraints = [
            models.CheckConstraint(condition=Q(version__gte=1), name="workflow_version_positive")
        ]
        indexes = [
            models.Index(fields=("state", "updated_at"), name="workflow_state_time_idx"),
            models.Index(fields=("generation", "version"), name="workflow_generation_ver_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and LectureWorkflow.objects.filter(pk=self.pk).exists() and not getattr(
            self, "_domain_service_write", False
        ):
            raise ValueError("Workflow state may change only through the workflow domain service.")
        return super().save(*args, **kwargs)


class ImmutableWorkflowRecord(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValueError("Workflow audit records are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Workflow audit records cannot be deleted.")


class WorkflowAuditEvent(ImmutableWorkflowRecord):
    workflow = models.ForeignKey(
        LectureWorkflow,
        on_delete=models.PROTECT,
        related_name="audit_events",
    )
    sequence = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    actor_type = models.CharField(max_length=24, choices=WORKFLOW_ACTOR_CHOICES)
    actor_identity_reference = models.CharField(max_length=128)
    previous_state = models.CharField(max_length=48, choices=LectureWorkflow.State, blank=True)
    new_state = models.CharField(max_length=48, choices=LectureWorkflow.State)
    reason_code = models.CharField(max_length=64)
    idempotency_key = models.CharField(max_length=128)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("workflow", "sequence")
        constraints = [
            models.CheckConstraint(
                condition=Q(sequence__gte=1), name="workflow_audit_sequence_positive"
            ),
            models.UniqueConstraint(
                fields=("workflow", "sequence"),
                name="unique_workflow_audit_sequence",
            ),
            models.UniqueConstraint(
                fields=("workflow", "idempotency_key"),
                name="unique_workflow_transition_key",
            ),
        ]
        indexes = [
            models.Index(fields=("workflow", "occurred_at"), name="workflow_audit_time_idx")
        ]


class WorkflowJob(models.Model):
    class JobType(models.TextChoices):
        SLIDE_NARRATION_DRAFT = "SLIDE_NARRATION_DRAFT", "Slide and narration draft coordination"
        RECORDING_READINESS = "RECORDING_READINESS", "Recording readiness coordination"
        DRAFT_VIDEO_READINESS = "DRAFT_VIDEO_READINESS", "Draft-video readiness coordination"
        EXPORT_READINESS = "EXPORT_READINESS", "Export handoff readiness coordination"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RUNNING = "RUNNING", "Running"
        SUCCEEDED = "SUCCEEDED", "Succeeded"
        FAILED = "FAILED", "Terminal failure"
        CANCELLED = "CANCELLED", "Cancelled"

    workflow = models.ForeignKey(
        LectureWorkflow,
        on_delete=models.PROTECT,
        related_name="jobs",
    )
    job_type = models.CharField(max_length=32, choices=JobType)
    payload = models.JSONField(default=dict)
    payload_sha256 = models.CharField(max_length=64)
    idempotency_key = models.CharField(max_length=128)
    workflow_version = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    status = models.CharField(max_length=16, choices=Status, default=Status.PENDING)
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3, validators=[MinValueValidator(1)])
    available_at = models.DateTimeField()
    leased_until = models.DateTimeField(null=True, blank=True)
    lease_owner = models.CharField(max_length=128, blank=True)
    completion_idempotency_key = models.CharField(max_length=128, blank=True)
    result = models.JSONField(default=dict, blank=True)
    failure_reason_code = models.CharField(max_length=64, blank=True)
    failure_message = models.CharField(max_length=300, blank=True)
    created_by_actor_type = models.CharField(max_length=24, choices=WORKFLOW_ACTOR_CHOICES)
    created_by_identity_reference = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("created_at", "pk")
        constraints = [
            models.CheckConstraint(
                condition=Q(workflow_version__gte=1), name="workflow_job_version_positive"
            ),
            models.UniqueConstraint(
                fields=("workflow", "job_type", "idempotency_key"),
                name="unique_workflow_job_key",
            ),
            models.CheckConstraint(
                condition=Q(max_attempts__gte=1) & Q(max_attempts__lte=5),
                name="workflow_job_retry_bounds",
            ),
            models.CheckConstraint(
                condition=Q(attempts__gte=0) & Q(attempts__lte=models.F("max_attempts")),
                name="workflow_job_attempt_bounds",
            ),
        ]
        indexes = [
            models.Index(
                fields=("status", "available_at", "created_at"),
                name="workflow_job_claim_idx",
            ),
            models.Index(fields=("leased_until", "status"), name="workflow_job_lease_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and WorkflowJob.objects.filter(pk=self.pk).exists() and not getattr(
            self, "_domain_service_write", False
        ):
            raise ValueError("Workflow jobs may change only through the queue domain service.")
        return super().save(*args, **kwargs)


class WorkflowJobEvent(ImmutableWorkflowRecord):
    job = models.ForeignKey(
        WorkflowJob,
        on_delete=models.PROTECT,
        related_name="events",
    )
    sequence = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    actor_type = models.CharField(max_length=24, choices=WORKFLOW_ACTOR_CHOICES)
    actor_identity_reference = models.CharField(max_length=128)
    previous_status = models.CharField(max_length=16, choices=WorkflowJob.Status, blank=True)
    new_status = models.CharField(max_length=16, choices=WorkflowJob.Status)
    reason_code = models.CharField(max_length=64)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("job", "sequence")
        constraints = [
            models.CheckConstraint(
                condition=Q(sequence__gte=1), name="workflow_job_event_sequence_positive"
            ),
            models.UniqueConstraint(
                fields=("job", "sequence"),
                name="unique_workflow_job_event_sequence",
            )
        ]
        indexes = [
            models.Index(fields=("job", "occurred_at"), name="workflow_job_event_time_idx")
        ]


class ImmutableRecordingRecord(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValueError("Recording audit records are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Recording audit records cannot be deleted.")


class RecordingTake(ImmutableRecordingRecord):
    workflow = models.ForeignKey(
        LectureWorkflow, on_delete=models.PROTECT, related_name="recording_takes"
    )
    slide_revision = models.ForeignKey(
        SlideRevision, on_delete=models.PROTECT, related_name="recording_takes"
    )
    canonical_narration = models.ForeignKey(
        CanonicalNarrationSnapshot, on_delete=models.PROTECT, related_name="recording_takes"
    )
    take_number = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    storage_key = models.CharField(max_length=255, unique=True)
    original_name = models.CharField(max_length=255)
    extension = models.CharField(max_length=8)
    media_type = models.CharField(max_length=40)
    byte_size = models.PositiveBigIntegerField()
    duration_ms = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="recording_takes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("workflow", "slide_revision__slide", "take_number")
        constraints = [
            models.UniqueConstraint(
                fields=("workflow", "slide_revision", "take_number"),
                name="unique_recording_take_number",
            ),
            models.CheckConstraint(condition=Q(take_number__gte=1), name="recording_take_number_positive"),
            models.CheckConstraint(condition=Q(byte_size__gte=1), name="recording_take_size_positive"),
            models.CheckConstraint(condition=Q(duration_ms__gte=1), name="recording_take_duration_positive"),
        ]
        indexes = [
            models.Index(fields=("workflow", "slide_revision"), name="recording_workflow_slide_idx"),
            models.Index(fields=("recorded_by", "created_at"), name="recording_teacher_time_idx"),
        ]


class RecordingSelection(models.Model):
    workflow = models.ForeignKey(
        LectureWorkflow, on_delete=models.PROTECT, related_name="recording_selections"
    )
    slide = models.ForeignKey(
        SlideDraft, on_delete=models.PROTECT, related_name="recording_selections"
    )
    current_take = models.ForeignKey(
        RecordingTake, on_delete=models.PROTECT, related_name="current_selections"
    )
    version = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    selected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="recording_selections"
    )
    selected_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("workflow", "slide__position")
        constraints = [
            models.UniqueConstraint(fields=("workflow", "slide"), name="unique_recording_selection"),
            models.CheckConstraint(condition=Q(version__gte=1), name="recording_selection_version_positive"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and RecordingSelection.objects.filter(pk=self.pk).exists() and not getattr(
            self, "_domain_service_write", False
        ):
            raise ValueError("Recording selection may change only through the recording service.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Recording selections cannot be deleted.")


class RecordingSelectionEvent(ImmutableRecordingRecord):
    selection = models.ForeignKey(
        RecordingSelection, on_delete=models.PROTECT, related_name="events"
    )
    version = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    take = models.ForeignKey(RecordingTake, on_delete=models.PROTECT, related_name="selection_events")
    selected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="recording_selection_events"
    )
    selected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("selection", "version")
        constraints = [
            models.UniqueConstraint(
                fields=("selection", "version"), name="unique_recording_selection_event_version"
            ),
            models.CheckConstraint(
                condition=Q(version__gte=1), name="recording_selection_event_version_positive"
            ),
        ]


class RecordingCompletion(ImmutableRecordingRecord):
    workflow = models.ForeignKey(
        LectureWorkflow, on_delete=models.PROTECT, related_name="recording_completions"
    )
    reference = models.CharField(max_length=128, unique=True)
    slide_approval_fingerprint = models.CharField(max_length=64)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="recording_completions"
    )
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("workflow", "completed_at", "pk")


class RecordingCompletionItem(ImmutableRecordingRecord):
    completion = models.ForeignKey(
        RecordingCompletion, on_delete=models.PROTECT, related_name="items"
    )
    position = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    slide_revision = models.ForeignKey(
        SlideRevision, on_delete=models.PROTECT, related_name="recording_completion_items"
    )
    take = models.ForeignKey(
        RecordingTake, on_delete=models.PROTECT, related_name="completion_items"
    )

    class Meta:
        ordering = ("completion", "position")
        constraints = [
            models.UniqueConstraint(
                fields=("completion", "position"), name="unique_recording_completion_position"
            ),
            models.CheckConstraint(
                condition=Q(position__gte=1), name="recording_completion_position_positive"
            ),
        ]


class ImmutableVideoRecord(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValueError("Video history records are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Video history records cannot be deleted.")


class VideoRenderInput(ImmutableVideoRecord):
    workflow = models.ForeignKey(
        LectureWorkflow, on_delete=models.PROTECT, related_name="video_render_inputs"
    )
    recording_completion = models.ForeignKey(
        RecordingCompletion, on_delete=models.PROTECT, related_name="video_render_inputs"
    )
    workflow_version = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    slide_approval_fingerprint = models.CharField(max_length=64)
    recording_reference = models.CharField(max_length=128)
    input_sha256 = models.CharField(max_length=64, unique=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="video_render_inputs"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("workflow", "created_at", "pk")
        indexes = [models.Index(fields=("workflow", "created_at"), name="video_input_workflow_idx")]


class VideoRenderInputItem(ImmutableVideoRecord):
    render_input = models.ForeignKey(
        VideoRenderInput, on_delete=models.PROTECT, related_name="items"
    )
    position = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    slide_revision = models.ForeignKey(
        SlideRevision, on_delete=models.PROTECT, related_name="video_render_input_items"
    )
    canonical_narration = models.ForeignKey(
        CanonicalNarrationSnapshot,
        on_delete=models.PROTECT,
        related_name="video_render_input_items",
    )
    take = models.ForeignKey(
        RecordingTake, on_delete=models.PROTECT, related_name="video_render_input_items"
    )
    title_snapshot = models.CharField(max_length=200)
    claims_snapshot = models.JSONField(default=list)
    narration_snapshot = models.TextField()
    narration_sha256 = models.CharField(max_length=64)
    take_sha256 = models.CharField(max_length=64)
    take_duration_ms = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    take_storage_key = models.CharField(max_length=255)

    class Meta:
        ordering = ("render_input", "position")
        constraints = [
            models.UniqueConstraint(
                fields=("render_input", "position"), name="unique_video_input_position"
            ),
            models.CheckConstraint(condition=Q(position__gte=1), name="video_input_position_positive"),
            models.CheckConstraint(
                condition=Q(take_duration_ms__gte=1), name="video_input_duration_positive"
            ),
        ]


class VideoRenderVersion(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending local render"
        RUNNING = "RUNNING", "Local render running"
        SUCCEEDED = "SUCCEEDED", "Draft render available"
        FAILED = "FAILED", "Local render failed"
        STALE = "STALE", "Inputs are stale"

    workflow = models.ForeignKey(
        LectureWorkflow, on_delete=models.PROTECT, related_name="video_render_versions"
    )
    render_input = models.ForeignKey(
        VideoRenderInput, on_delete=models.PROTECT, related_name="render_versions"
    )
    version = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="derived_versions"
    )
    reference = models.CharField(max_length=128, unique=True)
    status = models.CharField(max_length=16, choices=Status, default=Status.PENDING)
    manifest_storage_key = models.CharField(max_length=255)
    video_storage_key = models.CharField(max_length=255)
    video_sha256 = models.CharField(max_length=64, blank=True)
    byte_size = models.PositiveBigIntegerField(null=True, blank=True)
    failure_reason_code = models.CharField(max_length=64, blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="video_render_versions"
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("workflow", "version")
        constraints = [
            models.UniqueConstraint(
                fields=("workflow", "version"), name="unique_video_render_version"
            ),
            models.CheckConstraint(condition=Q(version__gte=1), name="video_render_version_positive"),
        ]
        indexes = [
            models.Index(fields=("status", "requested_at"), name="video_render_status_idx"),
            models.Index(fields=("workflow", "version"), name="video_render_workflow_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and VideoRenderVersion.objects.filter(pk=self.pk).exists() and not getattr(
            self, "_domain_service_write", False
        ):
            raise ValueError("Video render versions may change only through the video service.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Video render versions cannot be deleted.")


class VideoEditDecision(ImmutableVideoRecord):
    class DecisionType(models.TextChoices):
        BRANDING = "BRANDING", "Institutional branding"
        CAPTION_LAYOUT = "CAPTION_LAYOUT", "Caption layout"
        TRANSITION_TIMING = "TRANSITION_TIMING", "Transition timing"
        SPOKEN_CONTENT_REMOVAL = "SPOKEN_CONTENT_REMOVAL", "Approved spoken-content removal"

    workflow = models.ForeignKey(
        LectureWorkflow, on_delete=models.PROTECT, related_name="video_edit_decisions"
    )
    base_render = models.ForeignKey(
        VideoRenderVersion, on_delete=models.PROTECT, related_name="edit_decisions"
    )
    decision_type = models.CharField(max_length=32, choices=DecisionType)
    payload = models.JSONField(default=dict)
    payload_sha256 = models.CharField(max_length=64)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="video_edit_decisions"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("workflow", "created_at", "pk")
        indexes = [models.Index(fields=("workflow", "created_at"), name="video_edit_workflow_idx")]


class SpokenContentEditApproval(ImmutableVideoRecord):
    decision = models.OneToOneField(
        VideoEditDecision, on_delete=models.PROTECT, related_name="spoken_approval"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="spoken_content_edit_approvals",
    )
    approved_at = models.DateTimeField(auto_now_add=True)


class VideoRenderAppliedEdit(ImmutableVideoRecord):
    render = models.ForeignKey(
        VideoRenderVersion, on_delete=models.PROTECT, related_name="applied_edits"
    )
    decision = models.ForeignKey(
        VideoEditDecision, on_delete=models.PROTECT, related_name="applied_to_renders"
    )
    position = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        ordering = ("render", "position")
        constraints = [
            models.UniqueConstraint(fields=("render", "decision"), name="unique_render_edit"),
            models.UniqueConstraint(fields=("render", "position"), name="unique_render_edit_position"),
        ]


class VideoReviewSubmission(ImmutableVideoRecord):
    render = models.OneToOneField(
        VideoRenderVersion, on_delete=models.PROTECT, related_name="review_submission"
    )
    job = models.OneToOneField(
        WorkflowJob, on_delete=models.PROTECT, related_name="video_review_submission"
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="video_review_submissions",
    )
    submitted_at = models.DateTimeField(auto_now_add=True)


class TeacherVideoReview(ImmutableVideoRecord):
    class Decision(models.TextChoices):
        APPROVED = "APPROVED", "Approved"
        REVISION_REQUESTED = "REVISION_REQUESTED", "Revision requested"

    render = models.OneToOneField(
        VideoRenderVersion, on_delete=models.PROTECT, related_name="teacher_review"
    )
    decision = models.CharField(max_length=24, choices=Decision)
    notes = models.CharField(max_length=500, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="teacher_video_reviews"
    )
    reviewed_at = models.DateTimeField(auto_now_add=True)


class AdminFinalVideoApproval(ImmutableVideoRecord):
    render = models.OneToOneField(
        VideoRenderVersion, on_delete=models.PROTECT, related_name="admin_final_approval"
    )
    teacher_review = models.OneToOneField(
        TeacherVideoReview, on_delete=models.PROTECT, related_name="admin_final_approval"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="admin_final_video_approvals",
    )
    approved_at = models.DateTimeField(auto_now_add=True)


class VideoExportPackage(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending local package"
        RUNNING = "RUNNING", "Local package running"
        READY = "READY", "Local package ready"
        FAILED = "FAILED", "Local package failed"
        STALE = "STALE", "Approval or inputs are stale"

    workflow = models.ForeignKey(
        LectureWorkflow, on_delete=models.PROTECT, related_name="video_export_packages"
    )
    render = models.ForeignKey(
        VideoRenderVersion, on_delete=models.PROTECT, related_name="export_packages"
    )
    admin_approval = models.OneToOneField(
        AdminFinalVideoApproval, on_delete=models.PROTECT, related_name="export_package"
    )
    job = models.OneToOneField(
        WorkflowJob, on_delete=models.PROTECT, related_name="video_export_package"
    )
    version = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    reference = models.CharField(max_length=128, unique=True)
    storage_key = models.CharField(max_length=255)
    status = models.CharField(max_length=16, choices=Status, default=Status.PENDING)
    manifest_sha256 = models.CharField(max_length=64, blank=True)
    failure_reason_code = models.CharField(max_length=64, blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="video_export_packages"
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("workflow", "version")
        constraints = [
            models.UniqueConstraint(
                fields=("workflow", "version"), name="unique_video_export_version"
            ),
            models.CheckConstraint(condition=Q(version__gte=1), name="video_export_version_positive"),
        ]
        indexes = [models.Index(fields=("status", "requested_at"), name="video_export_status_idx")]

    def save(self, *args, **kwargs):
        if self.pk and VideoExportPackage.objects.filter(pk=self.pk).exists() and not getattr(
            self, "_domain_service_write", False
        ):
            raise ValueError("Video export packages may change only through the video service.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Video export packages cannot be deleted.")
