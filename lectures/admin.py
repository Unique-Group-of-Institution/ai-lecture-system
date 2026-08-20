from django.contrib import admin

from .models import (
    CanonicalNarrationSnapshot, Chapter, ContentFile, ContentSource, Course, ExtractedPage,
    ExtractionVersion, GenerationPageSnapshot, GenerationRequest, GenerationSourceSnapshot,
    LectureRequest, NarrationStatement, SlideClaim, SlideDraft, SlideRevision, SourceReference,
    LectureWorkflow, WorkflowAuditEvent, WorkflowJob, WorkflowJobEvent,
    RecordingCompletion, RecordingCompletionItem, RecordingSelection,
    RecordingSelectionEvent, RecordingTake,
)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "teacher", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "title", "teacher__username")


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ("course", "number", "title")
    list_filter = ("course",)
    search_fields = ("title", "course__code")


@admin.register(LectureRequest)
class LectureRequestAdmin(admin.ModelAdmin):
    list_display = ("title", "chapter", "requested_by", "status", "requested_at")
    list_filter = ("status",)
    search_fields = ("title", "requested_by__username", "chapter__course__code")


@admin.register(ContentSource)
class ContentSourceAdmin(admin.ModelAdmin):
    list_display = ("title", "source_type", "access_scope", "owner", "chapter", "processing_state", "page_count")
    list_filter = ("source_type", "access_scope", "processing_state", "rights_confirmed")
    search_fields = ("title", "owner__username", "chapter__course__code")
    readonly_fields = tuple(field.name for field in ContentSource._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ContentFile)
class ContentFileAdmin(admin.ModelAdmin):
    list_display = ("source", "media_type", "byte_size", "sha256", "created_at")
    readonly_fields = tuple(field.name for field in ContentFile._meta.fields)

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ExtractionVersion)
class ExtractionVersionAdmin(admin.ModelAdmin):
    list_display = ("source", "version", "status", "extractor", "completed_at")
    readonly_fields = tuple(field.name for field in ExtractionVersion._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ExtractedPage)
class ExtractedPageAdmin(admin.ModelAdmin):
    list_display = ("source_file", "page_number", "method", "mean_confidence", "requires_review")
    list_filter = ("method", "requires_review")
    readonly_fields = tuple(field.name for field in ExtractedPage._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ReadOnlyGenerationAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(GenerationRequest)
class GenerationRequestAdmin(ReadOnlyGenerationAdmin):
    list_display = ("id", "chapter", "requested_by", "status", "generator_key", "created_at")
    list_filter = ("status", "generator_key")


@admin.register(SlideDraft)
class SlideDraftAdmin(ReadOnlyGenerationAdmin):
    list_display = ("id", "generation", "position", "current_version", "approved_revision")


for generation_model in (
    GenerationSourceSnapshot, GenerationPageSnapshot, SlideRevision, SlideClaim,
    NarrationStatement, SourceReference, CanonicalNarrationSnapshot,
):
    admin.site.register(generation_model, ReadOnlyGenerationAdmin)


@admin.register(LectureWorkflow)
class LectureWorkflowAdmin(ReadOnlyGenerationAdmin):
    list_display = ("id", "generation", "state", "version", "updated_at")
    list_filter = ("state",)


@admin.register(WorkflowJob)
class WorkflowJobAdmin(ReadOnlyGenerationAdmin):
    list_display = (
        "id", "workflow", "workflow_version", "job_type", "status", "attempts", "max_attempts"
    )
    list_filter = ("job_type", "status")


admin.site.register(WorkflowAuditEvent, ReadOnlyGenerationAdmin)
admin.site.register(WorkflowJobEvent, ReadOnlyGenerationAdmin)

for recording_model in (
    RecordingTake,
    RecordingSelection,
    RecordingSelectionEvent,
    RecordingCompletion,
    RecordingCompletionItem,
):
    admin.site.register(recording_model, ReadOnlyGenerationAdmin)
