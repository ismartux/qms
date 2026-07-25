from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from .models import SubmissionImage


def serve_submission_image(request, image_id):
    """Return binary image data for a SubmissionImage.
    """
    img = get_object_or_404(SubmissionImage, pk=image_id)
    if not img.image:
        raise Http404("Image not found")
    # Assuming stored images are in common formats; use generic binary response.
    response = HttpResponse(img.image, content_type='application/octet-stream')
    response['Content-Disposition'] = f'inline; filename="{image_id}.png"'
    return response


# Create your views here.
