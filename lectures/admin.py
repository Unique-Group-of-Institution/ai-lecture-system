from django.contrib import admin

from .models import Chapter, Course, LectureRequest


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
