from django.contrib import admin

from .models import Chapter, ContentFile, ContentSource, ExtractedPage, ExtractionVersion, Course, LectureRequest


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
