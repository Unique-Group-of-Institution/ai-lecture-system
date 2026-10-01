from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError

from .models import GenerationRequest, SlideDraft


WORD_MS = 60_000 / 150
MAX_SCENES = 120
MAX_SCENE_TEXT = 4000


def _estimate_duration_ms(text: str) -> int:
    words = max(1, len(re.findall(r"\S+", text)))
    return max(2000, int(math.ceil(words * WORD_MS / 100.0) * 100))


def _scene_kind(title: str, text: str) -> str:
    value = f"{title} {text}".lower()
    if any(token in value for token in ("formula", "equation", "i =", "v =", "q =", "ohm")):
        return "formula"
    if any(token in value for token in ("diagram", "circuit", "graph", "figure", "shown", "schematic")):
        return "diagram"
    if any(token in value for token in ("example", "calculate", "solution", "numerical", "find")):
        return "workedExample"
    if any(token in value for token in ("summary", "recap", "review", "key points")):
        return "recap"
    return "concept"


def _safe_id(position: int) -> str:
    return f"source-scene-{position:03d}"


def compile_teacherless_manifest(generation_id: int) -> dict:
    generation = GenerationRequest.objects.select_related("chapter__course", "lecture").filter(pk=generation_id).first()
    if generation is None:
        raise ValidationError("Generation is unavailable.")
    if generation.status != GenerationRequest.Status.APPROVED:
        raise ValidationError("Teacherless compilation requires an approved source-grounded generation.")
    slides = list(
        SlideDraft.objects.filter(generation=generation, approved_revision__isnull=False)
        .select_related("approved_revision", "approved_revision__canonical_narration")
        .prefetch_related("approved_revision__narration_statements__references__page_snapshot")
        .order_by("position")
    )
    if not slides:
        raise ValidationError("No approved slides are available for teacherless compilation.")

    scenes = []
    total_ms = 0
    for position, slide in enumerate(slides, start=1):
        revision = slide.approved_revision
        narration = revision.canonical_narration
        statements = list(revision.narration_statements.all().order_by("position"))
        if not narration or not statements:
            raise ValidationError(f"Slide {slide.position} has no canonical narration.")

        text = narration.text.strip()
        if not text or len(text) > MAX_SCENE_TEXT:
            raise ValidationError(f"Slide {slide.position} narration is empty or exceeds the scene limit.")

        refs = []
        for statement in statements:
            for ref in statement.references.all():
                refs.append({
                    "pageSnapshotId": ref.page_snapshot_id,
                    "pageNumber": ref.page_snapshot.page_number,
                    "startOffset": ref.start_offset,
                    "endOffset": ref.end_offset,
                })

        duration_ms = _estimate_duration_ms(text)
        kind = _scene_kind(revision.title, text)
        elements = [{
            "kind": "text",
            "id": "narration",
            "text": text,
            "x": 100,
            "y": 210,
            "width": 1660,
            "fontSize": 42,
        }]
        if kind == "formula":
            elements.append({
                "kind": "formula",
                "id": "formula-focus",
                "expression": revision.title,
                "x": 260,
                "y": 500,
                "width": 1400,
                "fontSize": 64,
            })
        elif kind == "diagram":
            elements.append({
                "kind": "diagram",
                "id": "diagram-placeholder",
                "label": "Source diagram / visual asset required",
                "x": 420,
                "y": 500,
                "width": 1080,
                "height": 260,
            })
        elif kind == "workedExample":
            elements.append({
                "kind": "callout",
                "id": "worked-example",
                "text": "Step-by-step worked example",
                "x": 420,
                "y": 500,
                "width": 1080,
            })

        animations = [{"type": "fadeIn"}]
        if kind == "diagram":
            animations.append({"type": "draw", "axis": "x"})
        elif kind == "formula":
            animations.append({"type": "highlight", "target": "formula-focus"})

        scenes.append({
            "id": _safe_id(position),
            "kind": kind,
            "durationMs": duration_ms,
            "title": revision.title,
            "narration": {
                "text": text,
                "language": "SOURCE",
                "estimatedDurationMs": duration_ms,
            },
            "elements": elements,
            "animations": animations,
            "provenance": refs,
        })
        total_ms += duration_ms
        if len(scenes) > MAX_SCENES:
            raise ValidationError("Teacherless lecture exceeds the maximum scene count.")

    manifest = {
        "schemaVersion": 1,
        "compositionId": "TeacherlessLecture",
        "fps": 30,
        "width": 1920,
        "height": 1080,
        "renderReference": f"generation:{generation.pk}:teacherless:v1",
        "lecture": {
            "generationId": generation.pk,
            "course": generation.chapter.course.title,
            "className": generation.chapter.course.class_name,
            "subject": generation.chapter.course.subject_name,
            "chapter": generation.chapter.title,
            "lecture": generation.lecture.title if generation.lecture else "",
            "inputSha256": generation.input_sha256,
        },
        "branding": {
            "institutionName": "Unique Group of Institutions",
            "accentColor": "#17365D",
            "backgroundColor": "#F8FAFC",
        },
        "narration": {
            "languageMode": "SOURCE",
            "ttsProvider": None,
            "status": "READY_FOR_TTS",
        },
        "scenes": scenes,
        "qa": {
            "sceneCount": len(scenes),
            "estimatedDurationMs": total_ms,
            "estimatedDurationMinutes": round(total_ms / 60_000, 2),
            "hasProvenance": all(bool(scene["provenance"]) for scene in scenes),
            "requiresVisualAssetPass": any(scene["kind"] == "diagram" for scene in scenes),
        },
    }
    return manifest


def write_teacherless_manifest(generation_id: int) -> Path:
    manifest = compile_teacherless_manifest(generation_id)
    root = Path(settings.DATA_ROOT).resolve() / "lectures" / "teacherless" / f"generation-{generation_id}"
    root.mkdir(parents=True, exist_ok=True)
    path = root / "manifest-v1.json"
    encoded = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    path.write_bytes(encoded)
    return path


def manifest_sha256(manifest: dict) -> str:
    return hashlib.sha256(json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _srt_time(ms: int) -> str:
    hours, remainder = divmod(max(0, ms), 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def manifest_to_srt(manifest: dict) -> str:
    rows = []
    cursor = 0
    for number, scene in enumerate(manifest["scenes"], start=1):
        duration = int(scene["durationMs"])
        text = scene.get("narration", {}).get("text", "").strip()
        if not text:
            cursor += duration
            continue
        rows.append(
            f"{number}\n{_srt_time(cursor)} --> {_srt_time(cursor + duration)}\n{text}\n"
        )
        cursor += duration
    return "\n".join(rows)


def write_teacherless_srt(generation_id: int) -> Path:
    manifest = compile_teacherless_manifest(generation_id)
    root = Path(settings.DATA_ROOT).resolve() / "lectures" / "teacherless" / f"generation-{generation_id}"
    root.mkdir(parents=True, exist_ok=True)
    path = root / "captions-v1.srt"
    path.write_text(manifest_to_srt(manifest), encoding="utf-8")
    return path
