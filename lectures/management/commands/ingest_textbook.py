from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from lectures.content import extract_source, register_upload
from lectures.models import Chapter, ContentSource, Course
from lectures.roles import ADMINISTRATOR_ROLE


class Command(BaseCommand):
    help = (
        "Register an official textbook/board PDF as an institutional content source and run "
        "local text extraction so its pages become available for lecture mapping."
    )

    def add_arguments(self, parser):
        parser.add_argument("--course-code", required=True)
        parser.add_argument("--pdf", required=True)
        parser.add_argument("--source-title")
        parser.add_argument("--chapter-number", type=int, default=1)
        parser.add_argument("--chapter-title")
        parser.add_argument("--class-name")
        parser.add_argument("--subject-name")
        parser.add_argument("--course-title")
        parser.add_argument("--teacher", help="Username of the assigned teacher when creating a new course.")
        parser.add_argument("--admin", help="Username of an Administrator user (default: first Administrator).")
        parser.add_argument("--create-course", action="store_true")

    def handle(self, *args, **options):
        from django.contrib.auth import get_user_model

        user_model = get_user_model()
        if options["admin"]:
            admin = user_model.objects.filter(username=options["admin"]).first()
        else:
            admin = user_model.objects.filter(groups__name=ADMINISTRATOR_ROLE).order_by("pk").first()
        if admin is None:
            raise CommandError("No Administrator user available; create one or pass --admin.")

        course = Course.objects.filter(code=options["course_code"]).first()
        if course is None:
            if not options["create_course"]:
                raise CommandError(f"Course {options['course_code']} does not exist; pass --create-course to create it.")
            teacher = user_model.objects.filter(username=options["teacher"]).first()
            if teacher is None:
                raise CommandError("A new course needs an existing teacher username via --teacher.")
            course = Course.objects.create(
                code=options["course_code"],
                title=options["course_title"] or f"{options['class_name'] or ''} {options['subject_name'] or ''}".strip() or options["course_code"],
                class_name=options["class_name"] or "",
                subject_name=options["subject_name"] or "",
                teacher=teacher,
            )
            self.stdout.write(f"Created course {course.code} (id={course.pk}).")

        chapter, created = Chapter.objects.get_or_create(
            course=course,
            number=options["chapter_number"],
            defaults={"title": options["chapter_title"] or f"Unit {options['chapter_number']}"},
        )
        if created:
            self.stdout.write(f"Created chapter {chapter} (id={chapter.pk}).")

        pdf_path = Path(options["pdf"])
        if not pdf_path.is_file():
            raise CommandError(f"PDF not found: {pdf_path}")
        title = options["source_title"] or pdf_path.stem

        with pdf_path.open("rb") as handle:
            source = register_upload(
                actor=admin,
                chapter=chapter,
                title=title,
                source_type=ContentSource.SourceType.INSTITUTIONAL,
                rights_confirmed=True,
                upload=handle,
                filename=pdf_path.name,
            )
        self.stdout.write(f"Registered content source id={source.pk} '{source.title}' ({source.page_count} pages).")

        try:
            extraction = extract_source(source)
        except (ValidationError, RuntimeError) as exc:
            raise CommandError(f"Extraction failed safely: {exc}") from exc

        source.refresh_from_db()
        self.stdout.write(
            f"Extraction v{extraction.version} status={extraction.status}; source state={source.processing_state}."
        )
        if source.processing_state == ContentSource.ProcessingState.REVIEW_REQUIRED:
            self.stdout.write(
                self.style.WARNING(
                    "Scanned pages require teacher OCR review. Run: python manage.py approve_ocr_pages "
                    f"--source {source.pk} --teacher <username>"
                )
            )
        elif source.processing_state == ContentSource.ProcessingState.READY:
            self.stdout.write(self.style.SUCCESS("Source is READY for lecture mapping and generation."))
