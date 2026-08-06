from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class Course(models.Model):
    code = models.CharField(max_length=32, unique=True)
    title = models.CharField(max_length=200)
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
