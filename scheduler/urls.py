from django.urls import path
from . import views

app_name = "scheduler_admin"

urlpatterns = [
    path("", views.schedule_list, name="schedule_list"),
    path("create/", views.schedule_create, name="schedule_create"),
    path("<int:pk>/edit/", views.schedule_edit, name="schedule_edit"),
    path("instances/", views.instance_list, name="instance_list"),
    path("control/", views.scheduler_control, name="scheduler_control"),
    path("<int:pk>/delete/", views.schedule_delete, name="schedule_delete"),
]