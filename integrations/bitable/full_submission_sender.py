# integrations/bitable/full_submission_sender.py

import requests
import threading
from django.conf import settings
from submissions.models import SubmissionResponse, SubmissionAttachment
from forms_engine.models import ChecklistItem
from django.utils import timezone


def send_full_submission_to_worker(submission):

    template = submission.template_version.template
    work_context = submission.work_context

    responses = {
        str(r.item_id): r
        for r in SubmissionResponse.objects.filter(submission=submission)
    }

    items = (
        ChecklistItem.objects
        .filter(section__version=submission.template_version)
        .order_by("order")
    )

    records = []
    
    u = submission.submitted_by

    submitted_by_display = (
        f"{u.get_full_name()} ({u.username})"
        if u.get_full_name()
        else u.username
    )

    for item in items:

        response = responses.get(str(item.id))
        value = response.value if response else ""
        remark = response.remark if response else ""

        photo = (
            SubmissionAttachment.objects
            .filter(submission=submission, checklist_item=item)
            .first()
        )

        photo_field = None
        if photo:
            file_url = photo.file.url

            # If already absolute (R2 / S3 etc), use directly
            if file_url.startswith("http"):
                full_url = file_url
            else:
                full_url = f"{settings.SITE_BASE_URL}{file_url}"

            photo_field = {
                "link": full_url,
                "text": "View Photo"
            }

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

        fields = {
            "Submission_ID": str(submission.submission_id),
            "Item_ID": str(item.id),
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
            "Submitted_By": submitted_by_display,
            "Submitted_At": int(submission.submitted_at.timestamp() * 1000),
        }

        if photo_field:
            fields["Photo_URL"] = photo_field

        records.append(fields)

    payload = {
        "app_token": template.bitable_app_token.strip(),
        "table_id": template.bitable_table_id.strip(),
        "records": records,
    }

    # 🔥 TRUE FIRE-AND-FORGET
    def _send_async():
        try:
            print("🔥 Sending to worker...")
            r = requests.post(
                settings.CLOUDFLARE_RELAY_URL,
                json=payload,
                headers={
                    "X-RELAY-SECRET": settings.CLOUDFLARE_RELAY_SECRET
                },
                timeout=5
            )
            print("Worker status:", r.status_code)
            print("Worker response:", r.text)

        except Exception as e:
            print("Worker error:", e)
            
    threading.Thread(target=_send_async, daemon=True).start()
