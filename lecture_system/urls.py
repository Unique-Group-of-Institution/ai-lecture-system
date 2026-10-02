from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from lectures import studio
from lectures import views
from ugi_sso.views import consume_ugi_launch


urlpatterns = [

    # ============================================================
    # LMS STUDIO
    # ============================================================

    path(
        "",
        studio.studio_home,
        name="studio-home",
    ),

    path(
        "studio/",
        studio.studio_home,
        name="studio-home-dashboard",
    ),

    path(
        "studio/lecture/<int:workflow_id>/",
        studio.studio_lecture,
        name="studio-lecture",
    ),

    # ============================================================
    # AUTHENTICATION
    # ============================================================

    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html"
        ),
        name="login",
    ),

    path(
        "accounts/logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),

    path(
        "auth/ugi/consume",
        consume_ugi_launch,
        name="ugi-sso-consume",
    ),

    # ============================================================
    # TEACHER RECORDING
    # ============================================================

    path(
        "teacher/recordings/",
        views.teacher_recording_portal,
        name="teacher-recording-portal",
    ),

    path(
        "teacher/recordings/<int:workflow_id>/",
        views.teacher_recording_detail,
        name="teacher-recording-detail",
    ),

    path(
        "teacher/recording-takes/<int:take_id>/media/",
        views.recording_take_media,
        name="recording-take-media",
    ),

    # ============================================================
    # VIDEO ASSEMBLY / REVIEW
    # ============================================================

    path(
        "admin/video-assembly/",
        views.admin_video_dashboard,
        name="admin-video-dashboard",
    ),

    path(
        "teacher/video-review/",
        views.teacher_video_dashboard,
        name="teacher-video-dashboard",
    ),

    path(
        "video/workflows/<int:workflow_id>/",
        views.video_workflow_detail,
        name="video-workflow-detail",
    ),

    path(
        "video/renders/<int:render_id>/media/",
        views.video_render_media,
        name="video-render-media",
    ),

    # ============================================================
    # TEACHERLESS (AUTOMATED) LECTURE RENDER PATH
    # ============================================================

    path(
        "api/teacherless/generations/<int:generation_id>/render/",
        views.teacherless_render_api,
        name="teacherless-render",
    ),

    path(
        "api/teacherless/renders/<int:render_id>/status/",
        views.teacherless_render_status_api,
        name="teacherless-render-status",
    ),

    path(
        "teacherless/renders/<int:render_id>/media/",
        views.teacherless_render_media,
        name="teacherless-render-media",
    ),

    # ============================================================
    # DJANGO ADMIN
    # ============================================================

    path(
        "admin/",
        admin.site.urls,
    ),

    # ============================================================
    # RECORDING APIs
    # ============================================================

    path(
        "api/recordings/<int:workflow_id>/open/",
        views.recording_open_api,
        name="recording-open",
    ),

    path(
        "api/recordings/<int:workflow_id>/slides/<int:slide_id>/takes/",
        views.recording_take_upload_api,
        name="recording-take-upload",
    ),

    path(
        "api/recordings/<int:workflow_id>/slides/<int:slide_id>/select/",
        views.recording_take_select_api,
        name="recording-take-select",
    ),

    path(
        "api/recordings/<int:workflow_id>/complete/",
        views.recording_complete_api,
        name="recording-complete",
    ),

    # ============================================================
    # VIDEO APIs
    # ============================================================

    path(
        "api/video/workflows/<int:workflow_id>/renders/",
        views.video_render_request_api,
        name="video-render-request",
    ),

    path(
        "api/video/workflows/<int:workflow_id>/renders/<int:render_id>/recover/",
        views.video_render_recovery_api,
        name="video-render-recovery",
    ),

    path(
        "api/video/workflows/<int:workflow_id>/edits/",
        views.video_edit_decision_api,
        name="video-edit-decision",
    ),

    path(
        "api/video/edits/<int:decision_id>/teacher-approve/",
        views.spoken_edit_approval_api,
        name="spoken-edit-approval",
    ),

    path(
        "api/video/workflows/<int:workflow_id>/renders/<int:render_id>/submit-review/",
        views.video_submit_review_api,
        name="video-submit-review",
    ),

    path(
        "api/video/workflows/<int:workflow_id>/renders/<int:render_id>/teacher-review/",
        views.teacher_video_review_api,
        name="teacher-video-review",
    ),

    path(
        "api/video/workflows/<int:workflow_id>/renders/<int:render_id>/admin-final/",
        views.admin_final_video_approval_api,
        name="admin-final-video-approval",
    ),

    path(
        "api/video/workflows/<int:workflow_id>/renders/<int:render_id>/export/",
        views.video_export_request_api,
        name="video-export-request",
    ),

    # ============================================================
    # CONTENT APIs
    # ============================================================

    path(
        "api/content-sources/",
        views.content_sources,
        name="content-sources",
    ),

    path(
        "api/content-selection/",
        views.content_selection,
        name="content-selection",
    ),

    # ============================================================
    # GENERATION APIs
    # ============================================================

    path(
        "api/generations/",
        views.generations,
        name="generations",
    ),

    path(
        "api/generations/<int:generation_id>/",
        views.generation_detail,
        name="generation-detail",
    ),

    # ============================================================
    # FINAL-04: PPTX EXPORT
    # ============================================================

    path(
        "api/generations/<int:generation_id>/export-pptx/",
        views.export_generation_pptx,
        name="export-generation-pptx",
    ),

    # ============================================================
    # SLIDE APIs
    # ============================================================

    path(
        "api/slides/<int:slide_id>/revisions/",
        views.slide_revisions,
        name="slide-revisions",
    ),

    path(
        "api/slides/<int:slide_id>/approve/",
        views.slide_approval,
        name="slide-approval",
    ),

    path(
        "api/slides/<int:slide_id>/caption/",
        views.slide_caption,
        name="slide-caption",
    ),

    # ============================================================
    # WORKFLOW APIs
    # ============================================================

    path(
        "api/workflows/",
        views.workflows,
        name="workflows",
    ),

    path(
        "api/workflows/<int:workflow_id>/",
        views.workflow_detail,
        name="workflow-detail",
    ),

    path(
        "api/workflows/<int:workflow_id>/transition/",
        views.workflow_transition,
        name="workflow-transition",
    ),

    path(
        "api/workflows/<int:workflow_id>/audit/",
        views.workflow_audit,
        name="workflow-audit",
    ),

    # ============================================================
    # WORKFLOW JOB APIs
    # ============================================================

    path(
        "api/workflow-jobs/",
        views.workflow_jobs,
        name="workflow-jobs",
    ),

    path(
        "api/workflow-jobs/claim/",
        views.workflow_job_claim,
        name="workflow-job-claim",
    ),

    path(
        "api/workflow-jobs/<int:job_id>/complete/",
        views.workflow_job_complete,
        name="workflow-job-complete",
    ),

    path(
        "api/workflow-jobs/<int:job_id>/fail/",
        views.workflow_job_fail,
        name="workflow-job-fail",
    ),

    path(
        "api/workflow-jobs/<int:job_id>/cancel/",
        views.workflow_job_cancel,
        name="workflow-job-cancel",
    ),
]