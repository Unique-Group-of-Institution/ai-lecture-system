import csv
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from lectures.models import Chapter, Course, LectureDivision


def _page_value(entry, *keys):
    for key in keys:
        if key in entry and entry[key] not in (None, ""):
            return entry[key]
    return None


def _parse_range(entry):
    raw = _page_value(entry, "pages", "page_range", "range")
    start = _page_value(entry, "page_start", "start", "from")
    end = _page_value(entry, "page_end", "end", "to")
    if raw is not None:
        if isinstance(raw, (list, tuple)) and len(raw) == 2:
            start, end = raw
        elif isinstance(raw, str) and "-" in raw:
            start, end = raw.split("-", 1)
        elif isinstance(raw, (int, str)):
            start = end = raw
    if start in (None, "") and end in (None, ""):
        return None, None
    try:
        start = int(str(start).strip())
        end = int(str(end).strip())
    except (TypeError, ValueError) as exc:
        raise CommandError(f"Invalid page range in entry: {entry!r}") from exc
    if start < 1 or end < start:
        raise CommandError(f"Invalid page range in entry: {entry!r}")
    return start, end


def _parse_entries(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("lectures", data.get("division", []))
        if not isinstance(data, list):
            raise CommandError("Lecture division JSON must be a list or an object with a 'lectures' list.")
        entries = data
    elif suffix == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as handle:
            entries = list(csv.DictReader(handle))
    else:
        raise CommandError("Lecture division file must be .json or .csv")
    return entries


class Command(BaseCommand):
    help = (
        "Import the LMS lecture division (unit -> lecture -> textbook page range) for a chapter. "
        "Existing lecture numbers are updated in place; nothing is deleted."
    )

    def add_arguments(self, parser):
        parser.add_argument("--course-code", required=True)
        parser.add_argument("--chapter-number", type=int, required=True)
        parser.add_argument("--file", required=True)

    def handle(self, *args, **options):
        course = Course.objects.filter(code=options["course_code"]).first()
        if course is None:
            raise CommandError(f"Course {options['course_code']} does not exist.")
        chapter = Chapter.objects.filter(course=course, number=options["chapter_number"]).first()
        if chapter is None:
            raise CommandError(f"Chapter {options['chapter_number']} does not exist for course {course.code}.")

        path = Path(options["file"])
        if not path.is_file():
            raise CommandError(f"Lecture division file not found: {path}")
        entries = _parse_entries(path)

        created = updated = 0
        for position, entry in enumerate(entries, start=1):
            number = entry.get("number", entry.get("lecture", entry.get("lecture_number", position)))
            try:
                number = int(str(number).strip())
            except (TypeError, ValueError) as exc:
                raise CommandError(f"Entry {position} has no usable lecture number: {entry!r}") from exc
            title = str(entry.get("title", entry.get("name", f"Lecture {number}"))).strip()[:200]
            if not title:
                raise CommandError(f"Entry {position} has an empty title.")
            start, end = _parse_range(entry)
            division, was_created = LectureDivision.objects.update_or_create(
                chapter=chapter,
                number=number,
                defaults={"title": title, "page_start": start, "page_end": end},
            )
            if was_created:
                created += 1
            else:
                updated += 1
            pages = f"pages {start}-{end}" if start else "no page scope"
            self.stdout.write(f"  Lecture {number:02d}: {title} ({pages})")

        self.stdout.write(
            self.style.SUCCESS(
                f"Lecture division imported for {chapter}: {created} created, {updated} updated."
            )
        )
