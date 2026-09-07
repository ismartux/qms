from django.http import JsonResponse, HttpResponse, Http404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET

from submissions.models import SubmissionImage


@require_GET
def serve_submission_image(request, image_id):
    """
    Stream a binary image stored in SubmissionImage by UUID.
    """
    try:
        img = SubmissionImage.objects.get(id=image_id)
    except SubmissionImage.DoesNotExist:
        raise Http404("Image not found")

    return HttpResponse(
        bytes(img.image),
        content_type=img.content_type,
    )