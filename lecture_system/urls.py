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
]
