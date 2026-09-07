from django.urls import path
from .views import serve_submission_image

urlpatterns = [
    path("image/<uuid:image_id>/", serve_submission_image, name="serve_image"),
]
