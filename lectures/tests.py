import os
import subprocess
import sys
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError, connection, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse

from .models import Chapter, Course, LectureRequest
from .roles import (
    ADMINISTRATOR_ROLE,
    TEACHER_ROLE,
    assign_administrator,
    assign_teacher,
    can_request_lecture,
    courses_visible_to,
    lecture_requests_visible_to,
)


class CleanMigrationTests(TestCase):
    def test_migrations_apply_to_a_clean_sqlite_database(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "clean.sqlite3"
            environment = os.environ.copy()
            environment["AI_LECTURE_SQLITE_PATH"] = str(database)
            result = subprocess.run(
                [sys.executable, "manage.py", "migrate", "--noinput"],
                cwd=project_root,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(database.is_file())


class RolePermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        user_model = get_user_model()
        cls.teacher = assign_teacher(user_model.objects.create_user("teacher", password="safe-test-pass"))
        cls.other_teacher = assign_teacher(
            user_model.objects.create_user("other-teacher", password="safe-test-pass")
        )
        cls.administrator = assign_administrator(
            user_model.objects.create_user("administrator", password="safe-test-pass")
        )
        cls.course = Course.objects.create(code="PHY-101", title="Physics", teacher=cls.teacher)
        cls.other_course = Course.objects.create(
            code="MTH-101", title="Mathematics", teacher=cls.other_teacher
        )
        cls.chapter = Chapter.objects.create(course=cls.course, number=1, title="Motion")
        cls.request = LectureRequest.objects.create(
            chapter=cls.chapter,
            requested_by=cls.teacher,
            title="Introduction to Motion",
            learning_objectives="Explain displacement and velocity.",
        )

    def test_teacher_permissions_are_limited(self) -> None:
        self.assertTrue(self.teacher.groups.filter(name=TEACHER_ROLE).exists())
        self.assertTrue(self.teacher.has_perm("lectures.add_lecturerequest"))
        self.assertTrue(self.teacher.has_perm("lectures.view_course"))
        self.assertFalse(self.teacher.has_perm("lectures.add_course"))
        self.assertFalse(self.teacher.has_perm("lectures.delete_lecturerequest"))
        self.assertTrue(can_request_lecture(self.teacher, self.course))
        self.assertFalse(can_request_lecture(self.teacher, self.other_course))

    def test_administrator_has_domain_permissions_and_staff_access(self) -> None:
        self.assertTrue(self.administrator.groups.filter(name=ADMINISTRATOR_ROLE).exists())
        self.assertTrue(self.administrator.is_staff)
        for action in ("add", "change", "delete", "view"):
            self.assertTrue(self.administrator.has_perm(f"lectures.{action}_course"))
            self.assertTrue(self.administrator.has_perm(f"lectures.{action}_chapter"))
            self.assertTrue(self.administrator.has_perm(f"lectures.{action}_lecturerequest"))
        for action in ("add", "change", "view"):
            self.assertTrue(self.administrator.has_perm(f"auth.{action}_user"))
        self.assertFalse(self.administrator.has_perm("auth.delete_user"))
        self.assertFalse(self.administrator.has_perm("auth.change_group"))

    def test_unauthorized_users_cannot_see_domain_records(self) -> None:
        user = get_user_model().objects.create_user("unassigned", password="safe-test-pass")
        self.assertFalse(courses_visible_to(user).exists())
        self.assertFalse(lecture_requests_visible_to(user).exists())
        self.assertFalse(courses_visible_to(AnonymousUser()).exists())

    def test_teacher_sees_only_owned_records_and_admin_sees_all(self) -> None:
        self.assertQuerySetEqual(courses_visible_to(self.teacher), [self.course])
        self.assertQuerySetEqual(lecture_requests_visible_to(self.teacher), [self.request])
        self.assertEqual(courses_visible_to(self.administrator).count(), 2)
        self.assertEqual(lecture_requests_visible_to(self.administrator).count(), 1)

    def test_teacher_is_rejected_by_admin_login_while_administrator_is_allowed(self) -> None:
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 302)
        self.client.force_login(self.administrator)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)


class DomainModelTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.teacher = get_user_model().objects.create_user("teacher")
        cls.course = Course.objects.create(code="PHY-101", title="Physics", teacher=cls.teacher)
        cls.chapter = Chapter.objects.create(course=cls.course, number=1, title="Motion")

    def test_relationships_and_default_ordering(self) -> None:
        second = Chapter.objects.create(course=self.course, number=2, title="Forces")
        request = LectureRequest.objects.create(
            chapter=second,
            requested_by=self.teacher,
            title="Forces",
            learning_objectives="Describe balanced forces.",
        )
        self.assertEqual(list(self.course.chapters.values_list("number", flat=True)), [1, 2])
        self.assertEqual(request.chapter.course.teacher, self.teacher)

    def test_chapter_number_is_unique_per_course(self) -> None:
        with self.assertRaises(IntegrityError), transaction.atomic():
            Chapter.objects.create(course=self.course, number=1, title="Duplicate")

    def test_empty_learning_objectives_are_rejected_by_database(self) -> None:
        with self.assertRaises(IntegrityError), transaction.atomic():
            LectureRequest.objects.create(
                chapter=self.chapter,
                requested_by=self.teacher,
                title="Invalid",
                learning_objectives="",
            )

    def test_protected_relationships_prevent_accidental_content_deletion(self) -> None:
        with self.assertRaises(ProtectedError):
            self.teacher.delete()
        with self.assertRaises(ProtectedError):
            self.course.delete()

    def test_models_use_portable_fields_constraints_and_indexes(self) -> None:
        self.assertEqual(connection.vendor, "sqlite")
        for model in (Course, Chapter, LectureRequest):
            self.assertFalse(model._meta.required_db_vendor)
            self.assertTrue(all(index.condition is None for index in model._meta.indexes))
        self.assertEqual(Course._meta.get_field("teacher").remote_field.on_delete.__name__, "PROTECT")
