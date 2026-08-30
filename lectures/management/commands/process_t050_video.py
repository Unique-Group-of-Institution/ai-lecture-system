from django.core.management.base import BaseCommand, CommandError

from lectures.models import VideoRenderVersion
from lectures.video import process_next_readiness_job, process_render


class Command(BaseCommand):
    help = "Process trusted local T050 render and readiness work without an HTTP worker endpoint."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10)

    def handle(self, *args, **options):
        limit = options["limit"]
        if not 1 <= limit <= 100:
            raise CommandError("Limit must be between 1 and 100.")
        processed = 0
        for render_id in VideoRenderVersion.objects.filter(
            status=VideoRenderVersion.Status.PENDING
        ).order_by("requested_at", "pk").values_list("pk", flat=True)[:limit]:
            try:
                process_render(render_id)
                self.stdout.write(self.style.SUCCESS(f"Rendered video version {render_id}."))
            except Exception as exc:
                raise CommandError(f"Video render {render_id} failed safely: {type(exc).__name__}.") from exc
            processed += 1
        while processed < limit:
            try:
                job = process_next_readiness_job()
            except Exception as exc:
                raise CommandError(f"Video readiness processing failed safely: {type(exc).__name__}.") from exc
            if job is None:
                break
            self.stdout.write(self.style.SUCCESS(f"Processed workflow job {job.pk}."))
            processed += 1
        self.stdout.write(f"Processed {processed} trusted local T050 item(s).")
