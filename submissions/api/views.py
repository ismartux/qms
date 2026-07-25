from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.core.management import call_command


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