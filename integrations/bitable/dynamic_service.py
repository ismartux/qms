import requests
import traceback
from pprint import pprint

from django.conf import settings
from django.utils import timezone
import json
from submissions.models import (
    DynamicFormSubmission,
    DynamicFormSubmissionValue,
    DynamicSubmissionSyncLog,
)


# =========================================================
# WORK CONTEXT SERIALIZER (SINGLE SOURCE OF TRUTH)
# =========================================================
def _dynamic_work_context_fields(submission):
    wc = submission.work_context
    if not wc:
        return {}

    data = {}

    # -----------------------------
    # Work Date
    # -----------------------------
    if getattr(wc, "work_date", None):
        from django.utils import timezone
        data["Date"] = int(
            timezone.make_aware(
                timezone.datetime.combine(
                    wc.work_date,
                    timezone.datetime.min.time()
                )
            ).timestamp() * 1000
        )

    # -----------------------------
    # Safe value resolver
    # -----------------------------
    def _val(obj, attr="code"):
        if obj is None:
            return ""
        if isinstance(obj, str):
            return obj
        return getattr(obj, attr, "") or ""

    # -----------------------------
    # Context fields
    # -----------------------------
    data.update({
        "Plant": _val(getattr(wc, "plant", None), "name"),
        "Line": _val(getattr(wc, "line", None)),
        "Shift": _val(getattr(wc, "shift", None)),
        "Product": _val(getattr(wc, "product", None), "name"),
        "Color": _val(getattr(wc, "model_color", None)),
    })

    return data

def normalize_bitable_number(value):
    if value in (None, "", "None"):
        return None

    if isinstance(value, (int, float)):
        return value

    try:
        return float(str(value).replace("%", "").strip())
    except Exception:
        return None

# =========================================================
# MAIN SYNC FUNCTION (THIS IS THE ONE ACTUALLY USED)
# =========================================================
def sync_dynamic_submission(submission: DynamicFormSubmission):

    if not isinstance(submission, DynamicFormSubmission):
        return


    # -------------------------------------------------
    # SYNC LOG
    # -------------------------------------------------
    log, _ = DynamicSubmissionSyncLog.objects.get_or_create(
        submission=submission,
        target="BITABLE_DYNAMIC",
        defaults={
            "status": "PENDING",
            "attempts": 0,
        },
    )

    if log.status == "IN_PROGRESS":
        return

    log.status = "IN_PROGRESS"
    log.attempts += 1
    log.save(update_fields=["status", "attempts"])

    template = submission.template_version.template

    # Retrieve Bitable credentials from admin config, fallback to template fields
    from notifications.models import BitableConfig
    config = BitableConfig.objects.filter(name=template.code).first()
    if config:
        app_token = config.app_token
        table_id = config.table_id
    else:
        app_token = template.submission_bitable_app_token
        table_id = template.submission_bitable_table_id

    if not app_token or not table_id:
        log.status = "FAILED"
        log.error = "Submission Bitable App/Table not configured on template"
        log.save(update_fields=["status", "error"])
        return


    # -------------------------------------------------
    # META
    # -------------------------------------------------
    submitted_by = submission.submitted_by
    submitted_by_display = (
        f"{submitted_by.get_full_name()} ({submitted_by.username})"
        if submitted_by.get_full_name()
        else submitted_by.username
    )

    values = (
        DynamicFormSubmissionValue.objects
        .filter(submission=submission)
        .select_related("field")
        .order_by("field__order")
    )


    records = []
    context_fields = _dynamic_work_context_fields(submission)

    # -------------------------------------------------
    # AGGREGATED MODE
    # -------------------------------------------------
    if template.submission_mode == "AGGREGATED":

        fields = {
            "Submission_ID": str(submission.submission_id),
            "Template_Code": template.code,
            "Template_Name": template.name,
            "Submitted_By": submitted_by_display,
            "Submitted_At": int(submission.submitted_at.timestamp() * 1000),
            **context_fields,
        }

        for v in values:
            raw_value = v.value
            field = v.field

            # 🔑 FIX: NUMBER FIELD CASTING
            if field.data_type == "NUMBER":
                number_value = normalize_bitable_number(raw_value)

                # ⛔ Skip invalid / empty numbers
                if number_value is None:
                    continue

                fields[field.label] = number_value

            else:
                # Non-number fields unchanged
                if raw_value not in (None, "", "None"):
                    fields[field.label] = raw_value

        records.append(fields)
    # -------------------------------------------------
    # FULL MODE
    # -------------------------------------------------
    else:

        for v in values:
            raw_value = v.value
            field = v.field

            # 🔑 Normalize number fields
            if field.data_type == "NUMBER":
                result_value = normalize_bitable_number(raw_value)
            else:
                result_value = raw_value

            # ⛔ Skip empty values
            if result_value in (None, "", "None"):
                continue

            record = {
                "Submission_ID": str(submission.submission_id),
                "Field_ID": str(field.id),
                "Field_Label": field.label,
                "Result": result_value,
                "Submitted_By": submitted_by_display,
                "Submitted_At": int(submission.submitted_at.timestamp() * 1000),
                **context_fields,
            }

            records.append(record)


    payload = {
        "app_token": app_token.strip(),
        "table_id": table_id.strip(),
        "records": records,
    }

    # -------------------------------------------------
    # LOG PAYLOAD
    # -------------------------------------------------
    log.request_payload = payload
    log.save(update_fields=["request_payload"])


    # -------------------------------------------------
    # SEND TO CLOUDFLARE
    # -------------------------------------------------

    try:
        response = requests.post(
            settings.CLOUDFLARE_RELAY_URL,
            json=payload,
            headers={
                "X-RELAY-SECRET": settings.CLOUDFLARE_RELAY_SECRET
            },
            timeout=15,
        )

        log.http_status = response.status_code
        log.response_payload = response.text

        if response.ok:
            log.status = "SUCCESS"
        else:
            log.status = "FAILED"
            log.error = f"HTTP {response.status_code}"

        log.save(update_fields=[
            "status",
            "http_status",
            "response_payload",
            "error",
        ])

    except Exception as e:

        log.status = "FAILED"
        log.error = str(e)
        log.response_payload = traceback.format_exc()
        log.save(update_fields=[
            "status",
            "error",
            "response_payload",
        ])
