from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from lectures.generation import actor_context_for_user, create_generation
from lectures.models import ContentSource, Course, LectureDivision
from lectures.slide_engine import SlideEngineError, execute_one_slide_generation, queue_slide_generation
from lectures.workflow import (
    create_workflow,
    system_worker_context,
    workflow_actor_for_user,
)


class Command(BaseCommand):
    help = (
        "Run the source-grounded pipeline for one lecture division: scope the reviewed textbook "
        "pages to the lecture, generate grounded slides, create the workflow, run the slide engine "
        "and produce the branded PPTX."
    )

    def add_arguments(self, parser):
        parser.add_argument("--course-code", required=True)
        parser.add_argument("--lecture", type=int, required=True, help="Lecture division number.")
        parser.add_argument("--slide-count", type=int, default=8)
        parser.add_argument("--objective", help="Learning objective text for the generation guidelines.")
        parser.add_argument(
            "--skip-engine",
            action="store_true",
            help="Create slides and workflow but do not run the Node slide engine.",
        )

    def handle(self, *args, **options):
        course = Course.objects.filter(code=options["course_code"]).select_related("teacher").first()
        if course is None:
            raise CommandError(f"Course {options['course_code']} does not exist.")
        division = (
            LectureDivision.objects.select_related("chapter")
            .filter(chapter__course=course, number=options["lecture"])
            .first()
        )
        if division is None:
            raise CommandError(
                f"Lecture {options['lecture']} is not in the division of {course.code}; "
                "import it with import_lecture_division first."
            )
        if division.page_range() is None:
            raise CommandError("This lecture division entry has no textbook page range.")

        chapter = division.chapter
        sources = list(
            ContentSource.objects.filter(
                chapter=chapter,
                rights_confirmed=True,
                processing_state=ContentSource.ProcessingState.READY,
            ).order_by("pk")
        )
        if not sources:
            raise CommandError("No READY reviewed content source exists for this chapter yet.")

        teacher = course.teacher
        actor = actor_context_for_user(teacher)
        if not actor.can_generate:
            raise CommandError(
                f"Course teacher '{teacher.username}' lacks generation rights (Teacher group + permission)."
            )

        guidelines = {
            "learning_objective": options["objective"]
            or f"Explain {division.title} using the authorized textbook pages {division.page_start}-{division.page_end}.",
            "audience_level": course.class_name or "secondary",
            "slide_count": options["slide_count"],
        }
        try:
            generation = create_generation(
                actor=actor,
                chapter_id=chapter.pk,
                source_ids=[source.pk for source in sources],
                guidelines=guidelines,
                lecture_id=division.pk,
            )
        except (ValidationError, PermissionError) as exc:
            raise CommandError(f"Generation failed closed: {getattr(exc, 'message', exc)}") from exc

        pages = sorted(
            generation.source_snapshots.values_list("pages__page_number", flat=True).distinct()
        )
        self.stdout.write(
            f"Generation {generation.pk}: {generation.slides.count()} grounded slides from pages "
            f"{pages[0]}-{pages[-1]} (scope {division.page_start}-{division.page_end})."
        )

        workflow_actor = workflow_actor_for_user(teacher)
        workflow = create_workflow(
            actor=workflow_actor,
            generation_id=generation.pk,
            idempotency_key=f"lecture-division-create:{generation.pk}",
        )
        self.stdout.write(f"Workflow {workflow.pk} created in state {workflow.state}.")

        if options["skip_engine"]:
            self.stdout.write(self.style.WARNING("Slide engine skipped; queue it later with run_slide_engine_worker."))
            return

        queue_slide_generation(
            actor=workflow_actor,
            workflow_id=workflow.pk,
            idempotency_key=f"lecture-division-slide-engine:{generation.pk}",
        )
        worker = system_worker_context(
            identity_reference="local-lecture-division-worker",
            permitted_course_ids=[course.pk],
        )
        try:
            with transaction.atomic():
                job = execute_one_slide_generation(worker=worker)
        except SlideEngineError as exc:
            raise CommandError(f"Slide engine failed safely: {exc}") from exc
        if job is None:
            raise CommandError("The slide generation job could not be claimed.")

        workflow.refresh_from_db()
        generation.refresh_from_db()
        self.stdout.write(f"Slide engine job {job.pk}: {job.status}.")
        self.stdout.write(f"Workflow state: {workflow.state}.")
        if generation.pptx_storage_key:
            self.stdout.write(self.style.SUCCESS(f"PPTX ready: data/{generation.pptx_storage_key}"))
        else:
            raise CommandError("The slide engine did not record a PPTX output.")
