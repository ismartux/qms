# analytics/urls.py

from django.urls import path
from .views import role_dashboard

app_name = "dashboard"

urlpatterns = [
    path("", role_dashboard, name="dashboard"),
]
