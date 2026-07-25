from django.urls import path
from .views import trigger_bitable_sync

urlpatterns = [
    path("jobs/bitable-sync/", trigger_bitable_sync),
]
