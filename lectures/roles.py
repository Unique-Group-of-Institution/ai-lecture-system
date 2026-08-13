from django.contrib.auth.models import Group, Permission
from django.db.models import QuerySet

from .models import Course, LectureRequest


TEACHER_ROLE = "Teacher"
ADMINISTRATOR_ROLE = "Administrator"
def ensure_roles() -> tuple[Group, Group]:
    teacher, _ = Group.objects.get_or_create(name=TEACHER_ROLE)
    administrator, _ = Group.objects.get_or_create(name=ADMINISTRATOR_ROLE)

    teacher_permissions = Permission.objects.filter(
        content_type__app_label="lectures",
        codename__in=(
            "add_lecturerequest", "view_lecturerequest", "view_course", "view_chapter",
            "add_contentsource", "view_contentsource", "view_contentfile",
            "view_extractionversion", "view_extractedpage", "change_extractedpage",
            "add_generationrequest", "view_generationrequest",
            "view_generationsourcesnapshot", "view_generationpagesnapshot",
            "view_slidedraft", "change_slidedraft", "view_sliderevision",
            "view_slideclaim", "view_narrationstatement", "view_sourcereference",
            "view_canonicalnarrationsnapshot",
            "view_lectureworkflow", "view_workflowauditevent",
            "view_workflowjob", "view_workflowjobevent",
        ),
    )
    administrator_permissions = Permission.objects.filter(content_type__app_label="lectures") | (
        Permission.objects.filter(
            content_type__app_label="auth",
            content_type__model="user",
            codename__in=("add_user", "change_user", "view_user"),
        )
    )
    teacher.permissions.set(teacher_permissions)
    administrator.permissions.set(administrator_permissions)
    return teacher, administrator


def assign_teacher(user):
    teacher, administrator = ensure_roles()
    user.groups.remove(administrator)
    user.groups.add(teacher)
    if user.is_staff:
        user.is_staff = False
        user.save(update_fields=("is_staff",))
    return user


def assign_administrator(user):
    teacher, administrator = ensure_roles()
    user.groups.remove(teacher)
    user.groups.add(administrator)
    if not user.is_staff:
        user.is_staff = True
        user.save(update_fields=("is_staff",))
    return user


def courses_visible_to(user) -> QuerySet[Course]:
    if not user.is_authenticated:
        return Course.objects.none()
    if user.groups.filter(name=ADMINISTRATOR_ROLE).exists():
        return Course.objects.all()
    if user.groups.filter(name=TEACHER_ROLE).exists():
        return Course.objects.filter(teacher=user)
    return Course.objects.none()


def lecture_requests_visible_to(user) -> QuerySet[LectureRequest]:
    if not user.is_authenticated:
        return LectureRequest.objects.none()
    if user.groups.filter(name=ADMINISTRATOR_ROLE).exists():
        return LectureRequest.objects.all()
    if user.groups.filter(name=TEACHER_ROLE).exists():
        return LectureRequest.objects.filter(requested_by=user, chapter__course__teacher=user)
    return LectureRequest.objects.none()


def can_request_lecture(user, course: Course) -> bool:
    return bool(
        user.is_authenticated
        and user.has_perm("lectures.add_lecturerequest")
        and (
            user.groups.filter(name=ADMINISTRATOR_ROLE).exists()
            or course.teacher_id == user.pk
        )
    )
