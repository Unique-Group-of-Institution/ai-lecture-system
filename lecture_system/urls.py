from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from lectures import views
from ugi_sso.views import consume_ugi_launch


urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("auth/ugi/consume", consume_ugi_launch, name="ugi-sso-consume"),
    path("teacher/recordings/", views.teacher_recording_portal, name="teacher-recording-portal"),
    path("teacher/recordings/<int:workflow_id>/", views.teacher_recording_detail, name="teacher-recording-detail"),
    path("teacher/recording-takes/<int:take_id>/media/", views.recording_take_media, name="recording-take-media"),
    path("api/recordings/<int:workflow_id>/open/", views.recording_open_api, name="recording-open"),
    path("api/recordings/<int:workflow_id>/slides/<int:slide_id>/takes/", views.recording_take_upload_api, name="recording-take-upload"),
    path("api/recordings/<int:workflow_id>/slides/<int:slide_id>/select/", views.recording_take_select_api, name="recording-take-select"),
    path("api/recordings/<int:workflow_id>/complete/", views.recording_complete_api, name="recording-complete"),
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
