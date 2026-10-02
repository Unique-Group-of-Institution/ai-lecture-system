from django.core.management.base import BaseCommand, CommandError

from lectures.teacherless import compile_teacherless_manifest, manifest_sha256, write_teacherless_manifest, write_teacherless_srt


class Command(BaseCommand):
    help = "Compile an approved source-grounded generation into a teacherless lecture manifest."

    def add_arguments(self, parser):
        parser.add_argument("generation_id", type=int)
        parser.add_argument("--write", action="store_true", help="Persist the manifest and SRT under DATA_ROOT.")

    def handle(self, *args, **options):
        generation_id = options["generation_id"]
        try:
            manifest = compile_teacherless_manifest(generation_id)
            path = write_teacherless_manifest(generation_id) if options["write"] else None
            srt_path = write_teacherless_srt(generation_id) if options["write"] else None
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        qa = manifest["qa"]
        self.stdout.write(self.style.SUCCESS("TEACHERLESS MANIFEST READY"))
        self.stdout.write(f"generation_id={generation_id}")
        self.stdout.write(f"scene_count={qa['sceneCount']}")
        self.stdout.write(f"estimated_duration_minutes={qa['estimatedDurationMinutes']}")
        self.stdout.write(f"provenance_complete={qa['hasProvenance']}")
        self.stdout.write(f"visual_asset_pass_required={qa['requiresVisualAssetPass']}")
        self.stdout.write(f"manifest_sha256={manifest_sha256(manifest)}")
        if path:
            self.stdout.write(f"manifest_path={path}")
