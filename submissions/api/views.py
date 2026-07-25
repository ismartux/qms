from django.http import JsonResponse, HttpResponse, Http404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST, require_GET
from django.core.management import call_command

from submissions.models import SubmissionImage


@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_POST
def trigger_bitable_sync(request):
    """
    Trigger Bitable sync job manually.
    Superuser only.
    """

    call_command("sync_bitable")

    return JsonResponse({
        "status": "ok",
        "message": "Bitable sync started"
    })


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