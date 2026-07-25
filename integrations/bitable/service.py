# integrations/bitable/service.py

from django.db import transaction
from django.utils import timezone
from submissions.models import (
    SubmissionResponse,
    SubmissionAttachment,
    SubmissionSyncLog,
)
from forms_engine.models import ChecklistItem
from .cloudflare_client import create_bitable_record_via_relay
from django.conf import settings


ITEMS_PER_RUN = 25
MAX_SYNC_ATTEMPTS = 5   # 🔒 retry protection


def sync_submission_chunk_bitable(submission, log):

    # =====================================================
    # 🔒 Distributed DB lock + state machine
    # =====================================================
    with transaction.atomic():

        log = (
            SubmissionSyncLog.objects
            .select_for_update()
            .get(pk=log.pk)
        )

        # ✅ Already done
        if log.status == "SUCCESS":
            return

        # 🔒 Already running somewhere else
        if log.status == "IN_PROGRESS":
            return

        # ❌ Too many failures
        if log.attempts >= MAX_SYNC_ATTEMPTS:
            log.status = "FAILED"
            log.error = "Max retry attempts exceeded"
            log.save(update_fields=["status", "error"])
            return

        # 🔐 Lock state
        log.status = "IN_PROGRESS"
        log.attempts += 1
        log.save(update_fields=["status", "attempts"])

        template = submission.template_version.template
        version = submission.template_version
        work_context = submission.work_context

        items = (
            ChecklistItem.objects
            .filter(section__version=version)
            .order_by("order")
        )

        responses = {
            r.item_id: r
            for r in SubmissionResponse.objects.filter(submission=submission)
        }

        # 📦 Chunk selection
        chunk = items[log.cursor : log.cursor + ITEMS_PER_RUN]

        # ✅ No more data
        if not chunk:
            log.status = "SUCCESS"
            log.save(update_fields=["status"])
            return

        records = []

        for item in chunk:

            response = responses.get(str(item.id))

            value = response.value if response else ""
            remark = response.remark if response else ""

            photo = (
                SubmissionAttachment.objects
                .filter(submission=submission, checklist_item=item)
                .first()
            )

            photo_url = None
            if photo:
                file_url = photo.file.url
                photo_url = file_url if file_url.startswith("http") else f"{settings.SITE_BASE_URL}{file_url}"

            date_ms = None
            if work_context and work_context.work_date:
                date_ms = int(
                    timezone.make_aware(
                        timezone.datetime.combine(
                            work_context.work_date,
                            timezone.datetime.min.time()
                        )
                    ).timestamp() * 1000
                )

            # =====================================================
            # 🧠 IDEMPOTENCY FIELDS (CRITICAL)
            # =====================================================
            fields = {
                # 🔑 Deterministic identity
                "Submission_ID": str(submission.submission_id),
                "Item_ID": str(item.id),   # 👈 unique row key

                # Business fields
                "Template_Code": template.code,
                "Template_Name": template.name,
                "Field_Name": item.label,
                "Result": value,
                "Remark": remark,
                "Date": date_ms,
                "Plant": submission.plant.name if submission.plant else "",
                "Line": submission.line.name if submission.line else "",
                "Product": submission.product.name if submission.product else "",
                "Shift": work_context.shift if work_context else "",
                "Color": work_context.model_color if work_context else "",
                "Severity": submission.severity_score,
                "Submitted_By": submission.submitted_by.username,
                "Submitted_At": int(submission.submitted_at.timestamp() * 1000),
            }

            if photo_url:
                fields["Photo_URL"] = photo_url

            records.append(fields)

    # =====================================================
    # 🚀 OUTSIDE TRANSACTION (network call)
    # =====================================================
    result = create_bitable_record_via_relay(
        app_token=template.bitable_app_token.strip(),
        table_id=template.bitable_table_id.strip(),
        records=records,
    )

    # =====================================================
    # ❌ Failure handling
    # =====================================================
    if not result.get("success"):
        with transaction.atomic():
            log = SubmissionSyncLog.objects.select_for_update().get(pk=log.pk)
            log.status = "FAILED"
            log.error = str(result)
            log.save(update_fields=["status", "error"])
        return

    # =====================================================
    # 🔒 Cursor update (safe commit)
    # =====================================================
    with transaction.atomic():
        log = SubmissionSyncLog.objects.select_for_update().get(pk=log.pk)

        log.cursor += len(chunk)

        if log.cursor >= items.count():
            log.status = "SUCCESS"
        else:
            log.status = "PENDING"

        log.save(update_fields=["cursor", "status"])
