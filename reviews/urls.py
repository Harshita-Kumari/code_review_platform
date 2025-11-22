from django.urls import path
from . import views

app_name = "reviews"

urlpatterns = [
    path("", views.index, name="index"),
    path("detail/<int:pk>/", views.detail, name="detail"),
    path("project/<int:submission_id>/", views.project_detail, name="project_detail"),
    path("history/", views.history, name="history"),
]
