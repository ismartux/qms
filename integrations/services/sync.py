from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from integrations.services.payload import build_payload
from integrations.bitable.client import BitableClient
from integrations.models import IntegrationTemplateMapping

from submissions.models import (
    Submission,
    SubmissionResponse,
    SubmissionSyncLog,
)

from core.workflow.states import WorkflowState
from core.tenant.context import set_current_plant


# =====================================================
# SYNC SUBMISSION (SAFE + ON_COMMIT)
# =====================================================

def sync_submission_to_target(submission, target_code):
    """
    Push submission to external integration target.
    External call runs AFTER DB commit.
    """

    def _push():

        # Ensure plant context (important for background jobs)
        set_current_plant(submission.plant)

        mapping = IntegrationTemplateMapping.objects.get(
            template=submission.template_version.template,
            target__code=target_code,
            enabled=True,
        )

        payload = build_payload(submission, mapping)

        client = BitableClient()
        client.push(mapping.external_table_id, payload)

        SubmissionSyncLog.objects.update_or_create(
            submission=submission,
            target=target_code,
            defaults={"status": "SYNCED"},
        )

    transaction.on_commit(_push)


# =====================================================
# OFFLINE INGEST (SAFE + BULK OPTIMIZED)
# =====================================================

@transaction.atomic
def ingest_offline_submission(payload, user):

    submission_id = payload.get("submission_id")
    submitted_at = payload.get("submitted_at")

    if not submission_id:
        raise ValidationError("submission_id is required")

    submission, created = Submission.objects.get_or_create(
        submission_id=submission_id,
        defaults={
            "workflow_state": WorkflowState.SUBMITTED,
            "submitted_by": user,
            "submitted_at": submitted_at or timezone.now(),
        },
    )

    # -------------------------------------------------
    # VALIDATE TEMPLATE VERSION EXISTS
    # -------------------------------------------------
    if not submission.template_version:
        raise ValidationError("Submission missing template version")

    # -------------------------------------------------
    # BULK RESPONSE UPSERT
    # -------------------------------------------------

    responses_payload = payload.get("responses", [])

    if not isinstance(responses_payload, list):
        raise ValidationError("Invalid responses format")

    existing_responses = {
        r.item_id: r
        for r in SubmissionResponse.objects.filter(submission=submission)
    }

    to_create = []
    to_update = []

    for r in responses_payload:

        item_id = r.get("item_id")
        value = r.get("value", "")
        is_nc = r.get("is_nc", False)

        if not item_id:
            continue

        existing = existing_responses.get(item_id)

        if existing:
            existing.value = value
            existing.is_non_conformance = is_nc
            to_update.append(existing)
        else:
            to_create.append(
                SubmissionResponse(
                    submission=submission,
                    item_id=item_id,
                    value=value,
                    is_non_conformance=is_nc,
                )
            )

    if to_create:
        SubmissionResponse.objects.bulk_create(to_create)

    if to_update:
        SubmissionResponse.objects.bulk_update(
            to_update,
            ["value", "is_non_conformance"],
        )

    return submission