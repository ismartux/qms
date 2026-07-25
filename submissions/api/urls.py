from django.urls import path
from .views import trigger_bitable_sync, serve_submission_image

urlpatterns = [
    path("jobs/bitable-sync/", trigger_bitable_sync),
    path("image/<uuid:image_id>/", serve_submission_image, name="serve_image"),
]
