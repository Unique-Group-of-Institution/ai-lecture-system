from collections import OrderedDict

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render

from .models import (
    Course,
    GenerationRequest,
    LectureWorkflow,
)


def _workflow_visible_to_user(request, workflow):
    course = workflow.generation.chapter.course

    if request.user.is_superuser or request.user.is_staff:
        return True

    return course.teacher_id == request.user.id


STAGE_GUIDANCE = {
    "SOURCE_CONTENT_READY": ("Admin", "Run slide & narration generation for this lecture."),
    "SLIDE_NARRATION_DRAFT": ("Teacher", "Review every slide, then approve slides & narration."),
    "TEACHER_SLIDE_NARRATION_APPROVED": ("Teacher", "Confirm approval to unlock the recording portal."),
    "RECORDING_PENDING": ("Teacher", "Open the recording portal and record slide narration."),
    "RECORDING_READY": ("Admin", "All narration recorded — request the draft video render."),
    "DRAFT_VIDEO_PENDING": ("Admin", "Draft video render running; recover it if the render fails."),
    "DRAFT_VIDEO_READY": ("Teacher", "Watch the draft video and approve or request revision."),
    "TEACHER_VIDEO_REVISION_REQUESTED": ("Admin", "Revision requested — render a new draft video."),
    "TEACHER_VIDEO_APPROVED": ("Admin", "Give the final approval for this lecture."),
    "FINAL_ADMIN_APPROVED": ("Admin", "Generate the export package (MP4/SRT/PPTX)."),
    "EXPORT_READY": ("Admin", "Upload the export package to Google Drive."),
}


def _stage_info(workflow):
    if workflow is None:
        return {
            "state": "",
            "state_label": "Not generated",
            "actor": "Admin",
            "tone": "admin",
            "hint": "Create the content generation for this lecture.",
        }
    actor, hint = STAGE_GUIDANCE.get(workflow.state, ("", ""))
    tone = "done" if workflow.state == "EXPORT_READY" else (
        "teacher" if actor == "Teacher" else "admin"
    )
    return {
        "state": workflow.state,
        "state_label": workflow.get_state_display(),
        "actor": actor,
        "tone": tone,
        "hint": hint,
    }


def _format_duration(milliseconds):
    total_seconds = int(milliseconds / 1000)

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    return f"{minutes:02d}:{seconds:02d}"


@login_required
def studio_home(request):
    courses = (
        Course.objects
        .filter(is_active=True)
        .select_related("teacher")
        .prefetch_related("chapters")
    )

    if not request.user.is_staff and not request.user.is_superuser:
        courses = courses.filter(teacher=request.user)

    hierarchy = OrderedDict()

    for course in courses:

        class_name = (
            getattr(course, "class_name", None)
            or "Unassigned Class"
        )

        subject_name = (
            getattr(course, "subject_name", None)
            or "Unassigned Subject"
        )

        teacher = getattr(course, "teacher", None)

        if teacher:
            teacher_name = (
                teacher.get_full_name()
                or getattr(teacher, "username", None)
                or "Unassigned Teacher"
            )
        else:
            teacher_name = "Unassigned Teacher"

        class_bucket = hierarchy.setdefault(
            class_name,
            {
                "name": class_name,
                "subjects": OrderedDict(),
            },
        )

        subject_bucket = class_bucket["subjects"].setdefault(
            subject_name,
            {
                "name": subject_name,
                "teachers": OrderedDict(),
            },
        )

        teacher_bucket = subject_bucket["teachers"].setdefault(
            teacher_name,
            {
                "name": teacher_name,
                "course": course,
                "lectures": [],
            },
        )

        for chapter in course.chapters.all():

            generation = (
                GenerationRequest.objects
                .filter(chapter=chapter)
                .order_by("-created_at")
                .first()
            )

            workflow = None

            if generation:
                workflow = (
                    LectureWorkflow.objects
                    .filter(generation=generation)
                    .order_by("-created_at")
                    .first()
                )

            teacher_bucket["lectures"].append(
                {
                    "chapter": chapter,
                    "generation": generation,
                    "workflow": workflow,
                    "stage": _stage_info(workflow),
                }
            )

    context = {
        "hierarchy": hierarchy,

        "class_count": len(hierarchy),

        "subject_count": sum(
            len(item["subjects"])
            for item in hierarchy.values()
        ),

        "teacher_count": sum(
            len(subject["teachers"])
            for item in hierarchy.values()
            for subject in item["subjects"].values()
        ),

        "lecture_count": sum(
            len(teacher["lectures"])
            for item in hierarchy.values()
            for subject in item["subjects"].values()
            for teacher in subject["teachers"].values()
        ),
    }

    return render(
        request,
        "lectures/studio.html",
        context,
    )


@login_required
def studio_lecture(request, workflow_id):

    workflow = (
        LectureWorkflow.objects
        .select_related(
            "generation__chapter__course",
            "generation__requested_by",
        )
        .get(pk=workflow_id)
    )

    if not _workflow_visible_to_user(request, workflow):
        raise Http404

    generation = workflow.generation
    chapter = generation.chapter
    course = chapter.course

    slides = list(
        generation.slides
        .select_related("approved_revision")
        .prefetch_related("revisions")
        .order_by("position")
    )

    slide_count = len(slides)

    approved_slides = sum(
        1
        for slide in slides
        if slide.approved_revision_id
    )

    pending_slides = (
        slide_count - approved_slides
    )

    all_slides_approved = (
        slide_count > 0
        and approved_slides == slide_count
    )

    # ---------------------------------------------------------
    # RECORDING DATA
    # ---------------------------------------------------------

    recording_takes = list(
        workflow.recording_takes.all()
    )

    recording_selections = list(
        workflow.recording_selections
        .select_related("current_take")
        .all()
    )

    recording_take_count = len(
        recording_takes
    )

    recording_selection_count = len(
        recording_selections
    )

    total_recording_ms = sum(
        take.duration_ms
        for take in recording_takes
    )

    selected_recording_ms = sum(
        selection.current_take.duration_ms
        for selection in recording_selections
        if selection.current_take_id
    )

    recording_duration = _format_duration(
        total_recording_ms
    )

    selected_duration = _format_duration(
        selected_recording_ms
    )

    # ---------------------------------------------------------
    # RECORDING COMPLETION
    # ---------------------------------------------------------

    latest_completion = (
        workflow.recording_completions
        .order_by("-completed_at")
        .first()
    )

    recording_complete = (
        latest_completion is not None
    )

    # A final video should require:
    # 1. every slide approved
    # 2. recording completion
    # 3. a selected take for every slide

    every_slide_has_take = (
        slide_count > 0
        and recording_selection_count >= slide_count
    )

    final_video_ready = (
        all_slides_approved
        and recording_complete
        and every_slide_has_take
    )

    # ---------------------------------------------------------
    # WORKFLOW STATE
    # ---------------------------------------------------------

    state = (
        getattr(workflow, "state", "")
        or ""
    )

    state_label = (
        str(state)
        .replace("_", " ")
        .title()
    )

    context = {
        "workflow": workflow,

        "generation": generation,

        "chapter": chapter,

        "course": course,

        "slides": slides,

        "slide_count": slide_count,

        "approved_slides": approved_slides,

        "pending_slides": pending_slides,

        "all_slides_approved": all_slides_approved,

        "recording_takes": recording_take_count,

        "recording_selections": recording_selection_count,

        "recording_duration": recording_duration,

        "selected_duration": selected_duration,

        "recording_complete": recording_complete,

        "latest_completion": latest_completion,

        "every_slide_has_take": every_slide_has_take,

        "final_video_ready": final_video_ready,

        "state": state,

        "state_label": state_label,
    }

    return render(
        request,
        "lectures/studio_lecture.html",
        context,
    )