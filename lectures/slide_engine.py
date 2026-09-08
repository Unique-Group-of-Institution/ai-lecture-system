from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .lecture_builder import BuilderSlide, BuilderSource, build_lecture_json
from .models import GenerationRequest, LectureWorkflow, SourceReference, WorkflowJob
from .workflow import (
    WorkflowActorContext,
    claim_job,
    complete_job,
    fail_job,
    submit_job,
    system_worker_context,
    transition_workflow,
    ACTOR_SYSTEM_WORKER,
)

logger = logging.getLogger(__name__)

class SlideEngineError(Exception):
    code = "SLIDE_ENGINE_ERROR"

class SlideEngineTimeout(SlideEngineError):
    code = "TIMEOUT"

class SlideEngineDependencyError(SlideEngineError):
    code = "DEPENDENCY_UNAVAILABLE"

class SlideEngineInvalidOutput(SlideEngineError):
    code = "WORKER_ERROR"


def _contained(path: Path, root: Path) -> Path:
    resolved_root = root.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValidationError("Slide-engine path escaped the approved storage root.") from exc
    return resolved


def _source_for_reference(reference: SourceReference) -> BuilderSource:
    page = reference.page_snapshot
    text = page.text[reference.start_offset:reference.end_offset]
    if text != next((item.text for item in [reference.claim, reference.narration_statement] if item), text):
        raise ValidationError("Generation provenance failed integrity validation.")
    return BuilderSource(page_snapshot_id=page.pk, page_number=page.page_number, start_offset=reference.start_offset, end_offset=reference.end_offset, text=text)


def build_canonical_payload(generation: GenerationRequest) -> dict:
    generation = GenerationRequest.objects.select_related("chapter__course").prefetch_related(
        "slides__revisions__claims__references__page_snapshot",
        "slides__revisions__narration_statements__references__page_snapshot",
    ).get(pk=generation.pk)
    guidelines = generation.guidelines if isinstance(generation.guidelines, dict) else {}
    objective = str(guidelines.get("learning_objective", "Explain the key ideas in this lecture.")).strip()
    slos = [objective, "Explain the main concepts and relationships covered in the lecture.", "Apply the lecture ideas to the reviewed textbook content."]
    slides = []
    recap = []
    questions = []
    for draft in generation.slides.order_by("position"):
        revision = draft.revisions.get(version=draft.current_version)
        claims = tuple(item.text for item in revision.claims.all())
        narration = tuple(item.text for item in revision.narration_statements.all())
        refs = []
        for relation in (revision.claims.all(), revision.narration_statements.all()):
            for item in relation:
                for reference in item.references.all():
                    refs.append(_source_for_reference(reference))
        unique = {(r.page_snapshot_id, r.start_offset, r.end_offset): r for r in refs}
        sources = tuple(unique.values())
        slides.append(BuilderSlide(revision.title, claims, narration, sources))
        recap.append(claims[0] if claims else revision.title)
        questions.append(f"What is the main idea of {revision.title}?")
    payload = build_lecture_json(
        course_class=generation.chapter.course.class_name or "Unknown",
        subject=generation.chapter.course.subject_name or "physics",
        unit=generation.chapter.title,
        lecture=generation.pk,
        title=generation.slides.order_by("position").first().revisions.get(version=1).title if generation.slides.exists() else generation.chapter.title,
        lms_scope=generation.chapter.title,
        textbook_pages=", ".join(str(p.page_number) for p in generation.source_snapshots.values_list("pages__page_number", flat=True).distinct() if p),
        introduction=f"This lecture covers {generation.chapter.title} using the authorized, reviewed textbook snapshot.",
        learning_objectives=slos[:6],
        previous_knowledge=None,
        slides=slides,
        recap=recap[:8],
        review_questions=questions[:8],
    )
    return payload


def _validate_pptx(path: Path) -> None:
    if not path.is_file():
        raise SlideEngineInvalidOutput("The slide engine did not produce the requested PowerPoint file.")
    if path.stat().st_size <= 0 or path.stat().st_size > settings.SLIDE_ENGINE_MAX_PPTX_BYTES:
        raise SlideEngineInvalidOutput("The generated PowerPoint file failed the output-size check.")
    if not zipfile.is_zipfile(path):
        raise SlideEngineInvalidOutput("The generated PowerPoint file is not a valid ZIP package.")
    try:
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None or "[Content_Types].xml" not in archive.namelist():
                raise SlideEngineInvalidOutput("The generated PowerPoint package failed integrity checks.")
    except zipfile.BadZipFile as exc:
        raise SlideEngineInvalidOutput("The generated PowerPoint package is corrupt.") from exc


def _paths(generation_id: int) -> tuple[Path, Path]:
    root = _contained(settings.SLIDE_ENGINE_STORAGE_ROOT, settings.DATA_ROOT)
    job_root = _contained(root / f"generation-{generation_id}", root)
    job_root.mkdir(parents=True, exist_ok=True)
    return job_root / "lecture.json", job_root / "lecture.pptx"


def run_slide_engine(generation_id: int) -> str:
    generation = GenerationRequest.objects.get(pk=generation_id)
    payload = build_canonical_payload(generation)
    input_path, output_path = _paths(generation_id)
    input_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    command = [settings.SLIDE_ENGINE_EXECUTABLE, str(settings.SLIDE_ENGINE_ROOT / "scripts" / "generate-deck.mjs"), "--input", str(input_path), "--output", str(output_path)]
    try:
        completed = subprocess.run(
            command,
            cwd=str(settings.SLIDE_ENGINE_ROOT),
            shell=False,
            capture_output=True,
            text=True,
            timeout=settings.SLIDE_ENGINE_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SlideEngineTimeout("Slide generation timed out.") from exc
    except OSError as exc:
        logger.exception("Slide engine dependency unavailable")
        raise SlideEngineDependencyError("The slide generation worker is unavailable.") from exc
    stdout = (completed.stdout or "")[: settings.SLIDE_ENGINE_MAX_STDOUT_BYTES]
    stderr = (completed.stderr or "")[: settings.SLIDE_ENGINE_MAX_STDERR_BYTES]
    if completed.returncode != 0:
        logger.error("Slide engine failed: returncode=%s stdout=%r stderr=%r", completed.returncode, stdout, stderr)
        raise SlideEngineError("The slide generator failed safely.")
    _validate_pptx(output_path)
    logger.info("Slide engine completed generation=%s output=%s", generation_id, output_path)
    return output_path.relative_to(settings.DATA_ROOT).as_posix()


def queue_slide_generation(*, actor: WorkflowActorContext, workflow_id: int, idempotency_key: str) -> WorkflowJob:
    return submit_job(
        actor=actor,
        workflow_id=workflow_id,
        job_type=WorkflowJob.JobType.SLIDE_NARRATION_DRAFT,
        payload={"generation_id": LectureWorkflow.objects.get(pk=workflow_id).generation_id},
        idempotency_key=idempotency_key,
        max_attempts=3,
    )


def execute_one_slide_generation(*, worker: WorkflowActorContext, lease_seconds: int = 300) -> WorkflowJob | None:
    job = claim_job(actor=worker, lease_seconds=lease_seconds, job_types=[WorkflowJob.JobType.SLIDE_NARRATION_DRAFT])
    if job is None:
        return None
    try:
        artifact = run_slide_engine(job.workflow.generation_id)
        completed = complete_job(
            actor=worker,
            job_id=job.pk,
            completion_idempotency_key=f"slide-engine:{job.pk}:attempt:{job.attempts}",
            result={"job_id": job.pk, "job_type": job.job_type, "workflow_id": job.workflow_id, "workflow_version": job.workflow_version, "generation_id": job.workflow.generation_id},
        )
        transition_workflow(
            actor=worker,
            workflow_id=job.workflow_id,
            target_state=LectureWorkflow.State.SLIDE_NARRATION_DRAFT,
            reason_code="DRAFT_AVAILABLE",
            expected_version=job.workflow_version,
            idempotency_key=f"slide-engine-transition:{job.pk}:attempt:{job.attempts}",
            job_id=completed.pk,
        )
        return completed
    except SlideEngineTimeout as exc:
        fail_job(actor=worker, job_id=job.pk, reason_code=exc.code, message=str(exc), retryable=True, retry_delay_seconds=30)
    except SlideEngineDependencyError as exc:
        fail_job(actor=worker, job_id=job.pk, reason_code=exc.code, message=str(exc), retryable=True, retry_delay_seconds=60)
    except (SlideEngineInvalidOutput, SlideEngineError, ValidationError) as exc:
        code = getattr(exc, "code", "WORKER_ERROR")
        if code not in {"INVALID_INPUT", "RESOURCE_LIMIT", "WORKER_ERROR"}: code = "WORKER_ERROR"
        fail_job(actor=worker, job_id=job.pk, reason_code=code, message="Slide generation failed safely.", retryable=False)
    return WorkflowJob.objects.get(pk=job.pk)
