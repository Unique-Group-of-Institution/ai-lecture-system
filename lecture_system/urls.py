from django.contrib import admin
from django.urls import path

from lectures import views


urlpatterns = [
    path("admin/", admin.site.urls),
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
