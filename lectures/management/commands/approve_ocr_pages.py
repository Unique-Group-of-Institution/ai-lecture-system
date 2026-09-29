from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from lectures.content import approve_ocr_extraction
from lectures.models import ContentSource, ExtractionVersion


class Command(BaseCommand):
    help = (
        "Record the assigned teacher's review approval for pending OCR pages of a scanned source, "
        "promoting the source to READY so generation can use it."
    )

    def add_arguments(self, parser):
        parser.add_argument("--source", type=int, required=True)
        parser.add_argument("--teacher", required=True)

    def handle(self, *args, **options):
        teacher = get_user_model().objects.filter(username=options["teacher"]).first()
        if teacher is None:
            raise CommandError(f"Teacher user '{options['teacher']}' does not exist.")
        source = ContentSource.objects.filter(pk=options["source"]).first()
        if source is None:
            raise CommandError(f"Content source {options['source']} does not exist.")
        extraction = source.extractions.order_by("-version").first()
        if extraction is None or extraction.status != ExtractionVersion.Status.REVIEW_REQUIRED:
            raise CommandError("The latest extraction of this source is not awaiting OCR review.")
        approve_ocr_extraction(actor=teacher, extraction=extraction)
        source.refresh_from_db()
        self.stdout.write(self.style.SUCCESS(f"OCR pages approved; source state={source.processing_state}."))
