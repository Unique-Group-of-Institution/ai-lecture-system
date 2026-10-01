from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import threading
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connections
from django.utils import timezone

from .models import GenerationRequest, TeacherlessRender
from .teacherless import (
    apply_narration_audio,
    compile_teacherless_manifest,
    manifest_sha256,
    manifest_to_srt,
)
from .tts import WindowsSystemSpeechProvider
from .video import (
    UnsupportedRenderEnvironment,
    _file_sha,
    _render_failure_detail,
    _run_bounded,
    render_environment_supported,
)

logger = logging.getLogger(__name__)

MAX_PRODUCTION_MS = 60_000


def teacherless_root() -> Path:
    data_root = Path(settings.DATA_ROOT).resolve()
    base = Path(settings.BASE_DIR).resolve()
    if data_root != base / "data":
        raise UnsupportedRenderEnvironment("Teacherless storage must remain project-local.")
    root = data_root / "lectures" / "teacherless"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _relative_under(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root).as_posix()


def _resolve_relative(root: Path, relative: str, *, must_exist: bool) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ValidationError("Teacherless artifact reference is invalid.")
    parts = Path(relative.replace("\\", "/")).parts
    if not parts or Path(relative).is_absolute() or ".." in parts:
        raise ValidationError("Teacherless artifact reference is invalid.")
    path = root.joinpath(*parts)
    if must_exist and not path.is_file():
        raise ValidationError("Teacherless artifact is unavailable.")
    return path


def render_video_path(render: TeacherlessRender) -> Path:
    return _resolve_relative(teacherless_root(), render.video_relative_path, must_exist=True)


def render_manifest_path(render: TeacherlessRender) -> Path:
    return _resolve_relative(teacherless_root(), render.manifest_relative_path, must_exist=True)


def _save(render: TeacherlessRender, **fields) -> None:
    for name, value in fields.items():
        setattr(render, name, value)
    render._domain_service_write = True
    try:
        render.save(update_fields=tuple(fields))
    finally:
        del render._domain_service_write


def _mp4_duration_ms(path: Path) -> int:
    data = path.read_bytes()
    index = data.find(b"mvhd")
    if index == -1:
        raise ValidationError("Branding video has no measurable duration.")
    body = data[index + 4:]
    if body[0] == 1:
        timescale = int.from_bytes(body[20:24], "big")
        duration = int.from_bytes(body[24:32], "big")
    else:
        timescale = int.from_bytes(body[12:16], "big")
        duration = int.from_bytes(body[16:20], "big")
    if timescale <= 0:
        raise ValidationError("Branding video has an invalid timescale.")
    milliseconds = int(duration * 1000 / timescale)
    if milliseconds < 250 or milliseconds > MAX_PRODUCTION_MS:
        raise ValidationError("Branding video duration is outside the supported range.")
    return milliseconds


def _attach_production(manifest: dict, public_dir: Path) -> None:
    """Copy PO branding media into the render and reference it from the manifest."""
    assets = Path(settings.DATA_ROOT).resolve() / "assets"
    branding_dir = public_dir / "branding"
    production: dict[str, object] = {}

    intro = assets / "intro-outro" / "intro.mp4"
    if intro.is_file():
        branding_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(intro, branding_dir / "intro.mp4")
        production["introSrc"] = "branding/intro.mp4"
        production["introDurationMs"] = _mp4_duration_ms(intro)

    outro = assets / "intro-outro" / "outro.mp4"
    if outro.is_file():
        branding_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(outro, branding_dir / "outro.mp4")
        production["outroSrc"] = "branding/outro.mp4"
        production["outroDurationMs"] = _mp4_duration_ms(outro)

    logo = assets / "branding" / "logo.png"
    if logo.is_file():
        branding_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(logo, branding_dir / "logo.png")
        production["logoSrc"] = "branding/logo.png"

    music_dir = assets / "music"
    if music_dir.is_dir():
        for candidate in sorted(music_dir.glob("*")):
            if candidate.suffix.lower() in {".mp3", ".wav"} and candidate.is_file():
                branding_dir.mkdir(parents=True, exist_ok=True)
                target = f"music{candidate.suffix.lower()}"
                shutil.copyfile(candidate, branding_dir / target)
                production["musicSrc"] = f"branding/{target}"
                break

    if production:
        manifest["production"] = production


def request_teacherless_render(generation_id: int, user) -> TeacherlessRender:
    """Create (or reuse) a queued teacherless render for an approved generation."""
    if not render_environment_supported():
        raise UnsupportedRenderEnvironment(
            "The trusted local evaluation render adapter is not enabled."
        )
    generation = GenerationRequest.objects.filter(pk=generation_id).select_related(
        "chapter__course"
    ).first()
    if generation is None:
        raise GenerationRequest.DoesNotExist("Generation is unavailable.")
    if generation.chapter.course.teacher_id != user.pk and not (
        user.is_staff or user.is_superuser
    ):
        raise PermissionDenied("Teacherless rendering is not authorized for this generation.")
    if generation.status != GenerationRequest.Status.APPROVED:
        raise ValidationError("Teacherless rendering requires an approved generation.")

    latest = TeacherlessRender.objects.filter(generation=generation).order_by("-version").first()
    if latest is not None and latest.status == TeacherlessRender.Status.RUNNING:
        stale_before = timezone.now() - timedelta(seconds=settings.VIDEO_RENDER_TIMEOUT_SECONDS)
        if latest.started_at is None or latest.started_at > stale_before:
            return latest
        _save(
            latest,
            status=TeacherlessRender.Status.FAILED,
            failure_reason_code="RENDER_STALE",
            failure_detail="The render worker stopped before finishing (server restart?).",
            completed_at=timezone.now(),
        )
    if (
        latest is not None
        and latest.status == TeacherlessRender.Status.PENDING
    ):
        return latest
    if latest is not None and latest.status == TeacherlessRender.Status.SUCCEEDED:
        return latest

    version = (latest.version + 1) if latest is not None else 1
    render = TeacherlessRender.objects.create(
        generation=generation,
        version=version,
        reference=f"teacherless-g{generation.pk}-v{version}",
        status=TeacherlessRender.Status.PENDING,
        requested_by=user,
    )
    return render


def process_teacherless_render(render_id: int) -> TeacherlessRender:
    """Run the full teacherless pipeline for one queued render (blocking)."""
    render = TeacherlessRender.objects.get(pk=render_id)
    if render.status != TeacherlessRender.Status.PENDING:
        return render
    if not render_environment_supported():
        _save(
            render,
            status=TeacherlessRender.Status.FAILED,
            failure_reason_code="RENDER_ENVIRONMENT",
            failure_detail="The trusted local render adapter is not enabled.",
            completed_at=timezone.now(),
        )
        return render

    _save(render, status=TeacherlessRender.Status.RUNNING, started_at=timezone.now())
    manifest_path: Path | None = None
    output_path: Path | None = None
    try:
        generation_id = render.generation_id
        manifest = compile_teacherless_manifest(generation_id)
        digest = manifest_sha256(manifest)
        root = teacherless_root()
        render_dir = root / f"generation-{generation_id}" / f"render-v{render.version}-{digest[:40]}"
        if render_dir.exists():
            raise ValidationError("The immutable render directory already exists.")
        render_dir.mkdir(parents=True, exist_ok=False)
        public_dir = render_dir / "public"
        audio_dir = public_dir / "audio"

        manifest = apply_narration_audio(manifest, WindowsSystemSpeechProvider(), audio_dir)
        _attach_production(manifest, public_dir)
        manifest["publicDir"] = str(public_dir)
        try:
            requested_scale = float(os.environ.get("AI_LECTURE_TEACHERLESS_RENDER_SCALE", "1"))
        except ValueError:
            requested_scale = 1.0
        if 0.5 <= requested_scale < 1:
            manifest["renderScale"] = requested_scale

        encoded = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
        manifest_path = render_dir / "manifest.json"
        manifest_path.write_bytes(encoded)
        (render_dir / "captions.srt").write_text(manifest_to_srt(manifest), encoding="utf-8")

        project = Path(settings.REMOTION_PROJECT_ROOT).resolve()
        node = shutil.which("node")
        script = project / "scripts" / "render_teacherless.mjs"
        if not node or not script.is_file():
            raise UnsupportedRenderEnvironment("The trusted local teacherless renderer is unavailable.")
        output_path = render_dir / "lecture.mp4"
        _run_bounded(
            [node, str(script), str(manifest_path), str(output_path)],
            cwd=project,
            timeout=settings.VIDEO_RENDER_TIMEOUT_SECONDS,
        )
        video_sha, size = _file_sha(output_path)
        if size < 1:
            raise RuntimeError("The teacherless renderer produced no video.")

        duration_ms = sum(int(scene["durationMs"]) for scene in manifest["scenes"])
        production = manifest.get("production", {})
        duration_ms += int(production.get("introDurationMs", 0)) + int(production.get("outroDurationMs", 0))
        _save(
            render,
            status=TeacherlessRender.Status.SUCCEEDED,
            manifest_relative_path=_relative_under(root, manifest_path),
            video_relative_path=_relative_under(root, output_path),
            manifest_sha256=hashlib.sha256(encoded).hexdigest(),
            video_sha256=video_sha,
            byte_size=size,
            scene_count=len(manifest["scenes"]),
            duration_ms=duration_ms,
            completed_at=timezone.now(),
        )
        logger.info("Teacherless render %s succeeded (%s bytes).", render.pk, size)
    except Exception as exc:
        reason = getattr(exc, "reason_code", "") or exc.__class__.__name__
        _save(
            render,
            status=TeacherlessRender.Status.FAILED,
            failure_reason_code=str(reason)[:64],
            failure_detail=_render_failure_detail(exc, manifest_path, output_path),
            completed_at=timezone.now(),
        )
        logger.warning("Teacherless render %s failed: %s", render.pk, exc)
    finally:
        connections.close_all()
    return render


def start_teacherless_render(render_id: int) -> None:
    """Run one render in a daemon worker thread (called after the row is committed)."""

    def worker() -> None:
        try:
            process_teacherless_render(render_id)
        except Exception:  # never let a background render crash the thread silently
            logger.exception("Teacherless render worker %s crashed.", render_id)
        finally:
            connections.close_all()

    threading.Thread(target=worker, name=f"teacherless-render-{render_id}", daemon=True).start()


def teacherless_render_payload(render: TeacherlessRender) -> dict:
    return {
        "id": render.pk,
        "generation_id": render.generation_id,
        "version": render.version,
        "status": render.status,
        "scene_count": render.scene_count,
        "duration_ms": render.duration_ms,
        "byte_size": render.byte_size,
        "failure_reason_code": render.failure_reason_code,
        "media_url": f"/teacherless/renders/{render.pk}/media/" if render.status == TeacherlessRender.Status.SUCCEEDED else None,
    }
