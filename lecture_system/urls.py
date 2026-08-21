from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from lectures import views


urlpatterns = [
    path("accounts/login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("teacher/recordings/", views.teacher_recording_portal, name="teacher-recording-portal"),
    path("teacher/recordings/<int:workflow_id>/", views.teacher_recording_detail, name="teacher-recording-detail"),
    path("teacher/recording-takes/<int:take_id>/media/", views.recording_take_media, name="recording-take-media"),
    path("admin/video-assembly/", views.admin_video_dashboard, name="admin-video-dashboard"),
    path("admin/", admin.site.urls),
    path("teacher/video-review/", views.teacher_video_dashboard, name="teacher-video-dashboard"),
    path("video/workflows/<int:workflow_id>/", views.video_workflow_detail, name="video-workflow-detail"),
    path("video/renders/<int:render_id>/media/", views.video_render_media, name="video-render-media"),
    path("api/recordings/<int:workflow_id>/open/", views.recording_open_api, name="recording-open"),
    path("api/recordings/<int:workflow_id>/slides/<int:slide_id>/takes/", views.recording_take_upload_api, name="recording-take-upload"),
    path("api/recordings/<int:workflow_id>/slides/<int:slide_id>/select/", views.recording_take_select_api, name="recording-take-select"),
    path("api/recordings/<int:workflow_id>/complete/", views.recording_complete_api, name="recording-complete"),
    path("api/video/workflows/<int:workflow_id>/renders/", views.video_render_request_api, name="video-render-request"),
    path("api/video/workflows/<int:workflow_id>/edits/", views.video_edit_decision_api, name="video-edit-decision"),
    path("api/video/edits/<int:decision_id>/teacher-approve/", views.spoken_edit_approval_api, name="spoken-edit-approval"),
    path("api/video/workflows/<int:workflow_id>/renders/<int:render_id>/submit-review/", views.video_submit_review_api, name="video-submit-review"),
    path("api/video/workflows/<int:workflow_id>/renders/<int:render_id>/teacher-review/", views.teacher_video_review_api, name="teacher-video-review"),
    path("api/video/workflows/<int:workflow_id>/renders/<int:render_id>/admin-final/", views.admin_final_video_approval_api, name="admin-final-video-approval"),
    path("api/video/workflows/<int:workflow_id>/renders/<int:render_id>/export/", views.video_export_request_api, name="video-export-request"),
    path("api/content-sources/", views.content_sources, name="content-sources"),
    path("api/content-selection/", views.content_selection, name="content-selection"),
    path("api/generations/", views.generations, name="generations"),
    path("api/generations/<int:generation_id>/", views.generation_detail, name="generation-detail"),
    path("api/slides/<int:slide_id>/revisions/", views.slide_revisions, name="slide-revisions"),
    path("api/slides/<int:slide_id>/approve/", views.slide_approval, name="slide-approval"),
    path("api/slides/<int:slide_id>/caption/", views.slide_caption, name="slide-caption"),
    path("api/workflows/", views.workflows, name="workflows"),
    path("api/workflows/<int:workflow_id>/", views.workflow_detail, name="workflow-detail"),
    path("api/workflows/<int:workflow_id>/transition/", views.workflow_transition, name="workflow-transition"),
    path("api/workflows/<int:workflow_id>/audit/", views.workflow_audit, name="workflow-audit"),
    path("api/workflow-jobs/", views.workflow_jobs, name="workflow-jobs"),
    path("api/workflow-jobs/claim/", views.workflow_job_claim, name="workflow-job-claim"),
    path("api/workflow-jobs/<int:job_id>/complete/", views.workflow_job_complete, name="workflow-job-complete"),
    path("api/workflow-jobs/<int:job_id>/fail/", views.workflow_job_fail, name="workflow-job-fail"),
    path("api/workflow-jobs/<int:job_id>/cancel/", views.workflow_job_cancel, name="workflow-job-cancel"),
]
