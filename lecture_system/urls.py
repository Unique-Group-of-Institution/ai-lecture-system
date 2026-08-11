from django.contrib import admin
from django.urls import path

from lectures import views


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/content-sources/", views.content_sources, name="content-sources"),
    path("api/content-selection/", views.content_selection, name="content-selection"),
]
