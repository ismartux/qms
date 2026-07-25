from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError

import json
import hmac
import hashlib

from django.conf import settings

from core.audit.models import DomainEvent
from submissions.services import submit_submission_from_payload


@csrf_exempt  # Keep for external/offline clients
@require_POST
def offline_ingest(request):
    """
    Offline submission ingestion endpoint.

    Expected payload format:
    {
        "id": "<event_id>",
        "type": "SUBMISSION_SUBMIT",
        "payload": {...}
    }
    """

    # -------------------------------------------------
    # 🔐 0️⃣ Optional HMAC Signature Verification
    # -------------------------------------------------
    # Recommended for production. Will not break existing logic
    # if header not enforced yet.

    secret = getattr(settings, "OFFLINE_INGEST_SECRET", None)

    if secret:
        signature = request.headers.get("X-Signature")

        if not signature:
            return JsonResponse(
                {"status": "error", "message": "Missing signature"},
                status=403,
            )

        computed = hmac.new(
            secret.encode(),
            request.body,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(computed, signature):
            return JsonResponse(
                {"status": "error", "message": "Invalid signature"},
                status=403,
            )

    # -------------------------------------------------
    # 1️⃣ Parse JSON safely
    # -------------------------------------------------
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse(
            {"status": "error", "message": "Invalid JSON payload"},
            status=400,
        )

    event_id = payload.get("id")
    event_type = payload.get("type")
    data = payload.get("payload")

    if not event_id or not event_type or data is None:
        return JsonResponse(
            {"status": "error", "message": "Invalid event structure"},
            status=400,
        )

    # -------------------------------------------------
    # 2️⃣ Idempotent Event Creation (Race-Safe)
    # -------------------------------------------------
    try:
        with transaction.atomic():
            DomainEvent.objects.create(
                event_id=event_id,
                event_type=event_type,
                payload=data,
                object_type="Submission",
            )
    except IntegrityError:
        # Event already exists → safe retry
        return JsonResponse({"status": "duplicate"}, status=200)

    # -------------------------------------------------
    # 3️⃣ Process Event (Outside Event Creation Block)
    # -------------------------------------------------
    try:
        if event_type == "SUBMISSION_SUBMIT":
            submit_submission_from_payload(data, request.user)

    except ValidationError as ve:
        return JsonResponse(
            {
                "status": "error",
                "message": (
                    ve.message_dict
                    if hasattr(ve, "message_dict")
                    else str(ve)
                ),
            },
            status=400,
        )

    except Exception as e:
        return JsonResponse(
            {"status": "error", "message": str(e)},
            status=500,
        )

    return JsonResponse({"status": "ok"}, status=200)