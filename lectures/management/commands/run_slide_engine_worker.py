from django.core.management.base import BaseCommand
from django.db import transaction

from lectures.models import Course
from lectures.slide_engine import execute_one_slide_generation
from lectures.workflow import system_worker_context


class Command(BaseCommand):
    help = "Claim and execute one queued UGI slide-engine generation job."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="Keep processing jobs until the queue is empty.")
        parser.add_argument("--lease-seconds", type=int, default=300)

    def handle(self, *args, **options):
        actor = system_worker_context(
            identity_reference="slide-engine-worker",
            permitted_course_ids=Course.objects.values_list("pk", flat=True),
        )
        processed = 0
        while True:
            job = execute_one_slide_generation(worker=actor, lease_seconds=options["lease_seconds"])
            if job is None:
                break
            processed += 1
            self.stdout.write(self.style.SUCCESS(f"slide-engine job {job.pk}: {job.status}"))
            if not options["loop"]:
                break
        self.stdout.write(f"Processed {processed} slide-engine job(s).")
