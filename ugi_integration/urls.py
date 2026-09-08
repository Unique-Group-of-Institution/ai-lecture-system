from django.urls import path
from . import views

urlpatterns = [
    path('launch/', views.launch, name='lms_launch'),
]