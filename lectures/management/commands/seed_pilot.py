from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils.crypto import get_random_string

from lectures.models import Chapter, Course
from lectures.roles import assign_administrator, assign_teacher


class Command(BaseCommand):
    help = (
        "Seed the Class 9 Computer Science pilot: roles, an administrator, a teacher and the "
        "pilot course with its first chapter. Idempotent; existing records are left untouched."
    )

    def add_arguments(self, parser):
        parser.add_argument("--admin-username", default="admin")
        parser.add_argument("--teacher-username", default="teacher.cs9")
        parser.add_argument("--admin-password", help="Defaults to AI_LECTURE_SEED_ADMIN_PASSWORD or a generated value.")
        parser.add_argument("--teacher-password", help="Defaults to AI_LECTURE_SEED_TEACHER_PASSWORD or a generated value.")
        parser.add_argument("--course-code", default="CS9")
        parser.add_argument("--course-title", default="Class 9 Computer Science")
        parser.add_argument("--class-name", default="Class 9")
        parser.add_argument("--subject-name", default="Computer Science")

    def _user(self, username, password, assign):
        user = get_user_model().objects.filter(username=username).first()
        created = user is None
        if created:
            user = get_user_model().objects.create_user(username=username, password=password)
            self.stdout.write(f"Created user '{username}'.")
        assign(user)
        return user, created

    def handle(self, *args, **options):
        import os

        admin_password = options["admin_password"] or os.environ.get("AI_LECTURE_SEED_ADMIN_PASSWORD")
        teacher_password = options["teacher_password"] or os.environ.get("AI_LECTURE_SEED_TEACHER_PASSWORD")
        if admin_password is None:
            admin_password = get_random_string(12)
            self.stdout.write(self.style.WARNING(f"Generated admin password: {admin_password}"))
        if teacher_password is None:
            teacher_password = get_random_string(12)
            self.stdout.write(self.style.WARNING(f"Generated teacher password: {teacher_password}"))

        admin, admin_created = self._user(options["admin_username"], admin_password, assign_administrator)
        teacher, teacher_created = self._user(options["teacher_username"], teacher_password, assign_teacher)

        course, course_created = Course.objects.get_or_create(
            code=options["course_code"],
            defaults={
                "title": options["course_title"],
                "class_name": options["class_name"],
                "subject_name": options["subject_name"],
                "teacher": teacher,
            },
        )
        if not course_created and course.teacher_id != teacher.pk:
            course.teacher = teacher
            course.save(update_fields=("teacher", "updated_at"))
        chapter, chapter_created = Chapter.objects.get_or_create(
            course=course, number=1, defaults={"title": "Unit 1"}
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Pilot ready: admin={admin.username} (created={admin_created}), "
                f"teacher={teacher.username} (created={teacher_created}), "
                f"course={course.code} id={course.pk} (created={course_created}), chapter id={chapter.pk}."
            )
        )
