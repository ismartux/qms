import threading
from django.db import models

from submissions.models import (
    DynamicFormSubmission,
    DynamicFormSubmissionValue,
    DynamicSubmissionSyncLog,
)

from integrations.models import IntegrationTemplateMapping
from integrations.bitable.upsert_client import (
    upsert_bitable_record_via_relay,
)

from integrations.bitable.dynamic_service import (
    _dynamic_work_context_fields,
)


# =========================================================
# AGGREGATED MODE
# One submission = one row
# =========================================================
def send_dynamic_submission_aggregated(
    submission: DynamicFormSubmission,
    log: DynamicSubmissionSyncLog,
):
    template = submission.template_version.template
    work_context = submission.work_context

    # -------------------------------------------------
    # SAFE MAPPING RESOLUTION
    # -------------------------------------------------
    qs = IntegrationTemplateMapping.objects.filter(
        template__code=template.code,
        enabled=True,
    )

    if work_context and getattr(work_context, "plant", None):
        qs = qs.filter(
            models.Q(plant=work_context.plant) |
            models.Q(plant__isnull=True)
        )
    else:
        qs = qs.filter(plant__isnull=True)

    mapping = qs.select_related("target").first()

    if not mapping:
        log.status = "FAILED"
        log.error = "No IntegrationTemplateMapping found"
        log.save(update_fields=["status", "error"])
        return

    # -------------------------------------------------
    # CONTEXT FIELDS (ONCE)
    # -------------------------------------------------
    context_fields = _dynamic_work_context_fields(submission)

    # -------------------------------------------------
    # BUILD RECORD
    # -------------------------------------------------
    fields = {
        "Submission_ID": str(submission.submission_id),
        "Template_Code": template.code,
        "Template_Name": template.name,
        "Submitted_At": int(submission.submitted_at.timestamp() * 1000),
        **context_fields,
    }

    values = (
        DynamicFormSubmissionValue.objects
        .filter(submission=submission)
        .select_related("field")
    )

    for val in values:
        fields[val.field.label] = val.value

    payload = {
        "app_token": mapping.target.code,
        "table_id": mapping.external_table_id,
        "records": [fields],
        "match_field": "Submission_ID",
    }

    log.request_payload = payload
    log.save(update_fields=["request_payload"])

    _fire_and_forget(payload=payload, log=log)


# =========================================================
# FULL MODE
# One field = one row
# =========================================================
def send_dynamic_submission_per_field(
    submission: DynamicFormSubmission,
    log: DynamicSubmissionSyncLog,
):
    template = submission.template_version.template
    work_context = submission.work_context

    # -------------------------------------------------
    # SAFE MAPPING RESOLUTION
    # -------------------------------------------------
    qs = IntegrationTemplateMapping.objects.filter(
        template__code=template.code,
        enabled=True,
    )

    if work_context and getattr(work_context, "plant", None):
        qs = qs.filter(
            models.Q(plant=work_context.plant) |
            models.Q(plant__isnull=True)
        )
    else:
        qs = qs.filter(plant__isnull=True)

    mapping = qs.select_related("target").first()

    if not mapping:
        log.status = "FAILED"
        log.error = "No IntegrationTemplateMapping found"
        log.save(update_fields=["status", "error"])
        return

    # -------------------------------------------------
    # CONTEXT FIELDS (ONCE)
    # -------------------------------------------------
    context_fields = _dynamic_work_context_fields(submission)

    # -------------------------------------------------
    # BUILD RECORDS
    # -------------------------------------------------
    records = []

    values = (
        DynamicFormSubmissionValue.objects
        .filter(submission=submission)
        .select_related("field")
        .order_by("field__order")
    )

    for val in values:
        records.append({
            "Submission_ID": str(submission.submission_id),
            "Field_ID": str(val.field.id),
            "Field_Label": val.field.label,
            "Value": val.value,
            **context_fields,
        })

    payload = {
        "app_token": mapping.target.code,
        "table_id": mapping.external_table_id,
        "records": records,
        "match_field": "Submission_ID",
    }

    log.request_payload = payload
    log.save(update_fields=["request_payload"])

    _fire_and_forget(payload=payload, log=log)


# =========================================================
# FIRE & FORGET TRANSPORT
# =========================================================
def _fire_and_forget(*, payload: dict, log: DynamicSubmissionSyncLog):

    def _send():
        try:
            result = upsert_bitable_record_via_relay(**payload)

            log.status = "SUCCESS"
            log.http_status = result.get("http_status")
            log.response_payload = result.get("response")
            log.save(update_fields=[
                "status",
                "http_status",
                "response_payload",
            ])

        except Exception as e:
            log.status = "FAILED"
            log.error = str(e)
            log.save(update_fields=["status", "error"])

    threading.Thread(target=_send, daemon=True).start()


# =========================================================
# TRANSFORMS
# =========================================================
def apply_transform(transform_key, value):
    if transform_key == "UPPER":
        return str(value).upper()

    if transform_key == "LOWER":
        return str(value).lower()

    if transform_key == "BOOL":
        return "Yes" if str(value).lower() in ("1", "true", "yes") else "No"

    return value