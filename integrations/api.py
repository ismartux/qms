from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
import json

from integrations.services.sync import ingest_offline_submission
from core.audit.models import DomainEvent


@require_POST
@login_required
def offline_sync_api(request):
    """
    Secure offline ingestion endpoint.

    Enforces:
    - POST only
    - Authenticated user
    - JSON validation
    - Idempotency (duplicate event protection)
    - Safe error handling
    """

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"error": "Invalid JSON payload"},
            status=400
        )

    event_id = payload.get("event_id")

    if not event_id:
        return JsonResponse(
            {"error": "Missing event_id"},
            status=400
        )

    # 🔒 Idempotency check
    if DomainEvent.objects.filter(event_id=event_id).exists():
        return JsonResponse({"status": "duplicate"})

    try:
        with transaction.atomic():

            # Record event first (prevents race)
            DomainEvent.objects.create(
                event_id=event_id,
                event_type="OFFLINE_SUBMISSION",
                payload=payload,
                object_type="Submission",
            )

            ingest_offline_submission(payload, request.user)

    except ValidationError as e:
        return JsonResponse(
            {"error": e.message_dict if hasattr(e, "message_dict") else str(e)},
            status=400
        )

    except Exception as e:
        return JsonResponse(
            {"error": "Internal server error"},
            status=500
        )

    return JsonResponse({"status": "ok"})