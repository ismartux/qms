import threading
from django.utils import timezone
from submissions.models import SubmissionResponse
from integrations.bitable.upsert_client import upsert_bitable_record_via_relay
from django.conf import settings
import traceback

app_token = settings.CAPA_BITABLE_APP_TOKEN
table_id = settings.CAPA_BITABLE_TABLE_ID


# =========================================================
# HELPERS
# =========================================================

from submissions.models import SubmissionResponse
from forms_engine.models import ChecklistItem


def _format_failed_nc_points(submission):
    """
    Build multi-line failed NC points using item label + remark.
    Compatible with schema where SubmissionResponse has item_id (NOT FK).
    """

    # 1️⃣ Get failed responses only
    failed_responses = (
        SubmissionResponse.objects
        .filter(submission=submission, is_non_conformance=True)
    )

    if not failed_responses.exists():
        return ""

    # 2️⃣ Map responses by item_id (string for safe matching)
    response_map = {
        str(r.item_id): r
        for r in failed_responses
    }

    # 3️⃣ Fetch checklist items of this template version
    items = (
        ChecklistItem.objects
        .filter(section__version=submission.template_version)
        .order_by("order")
    )

    lines = []
    counter = 1

    # 4️⃣ Match items with failed responses
    for item in items:
        response = response_map.get(str(item.id))

        if not response:
            continue

        remark = f" - {response.remark}" if response.remark else ""

        lines.append(f"{counter}. {item.label}{remark}")
        counter += 1

    return "\n".join(lines)

def _get_user_department(user, plant):
    """
    Get department name of user for given plant.
    """

    scope = (
        user.scopes
        .filter(plant=plant)
        .select_related("department")
        .first()
    )

    if scope and scope.department:
        return scope.department.name

    return ""


# =========================================================
# CREATE SYNC
# =========================================================

def send_capa_create_async(capa, creator):

    def _send():
        try:
            print("🚀 CAPA SYNC STARTED:", capa.capa_id)

            submission = capa.submission
            work_context = submission.work_context
            plant = work_context.plant if work_context else None

            fields = {
                "CAPA_ID": str(capa.capa_id),
                "Submission_ID": str(submission.submission_id),
                "Template_Name": submission.template_version.template.name,
                "Plant": plant.name if plant else "",
                "Department": _get_user_department(creator, plant),
                "Line": work_context.line.name if work_context and work_context.line else "",
                "Work_Date": int(timezone.make_aware(timezone.datetime.combine(work_context.work_date, timezone.datetime.min.time())).timestamp() * 1000) if work_context and work_context.work_date else None,
                "Product": work_context.product.name if work_context and work_context.product else "",
                "Shift": work_context.shift if work_context else "",
                "Title": capa.title,
                "Description": capa.description,
                "Severity": capa.severity,
                "Status": capa.status,
                "Due_Date": int(timezone.make_aware(timezone.datetime.combine(capa.due_date, timezone.datetime.min.time())).timestamp() * 1000) if capa.due_date else None,
                "Failed_NC_Points": _format_failed_nc_points(submission),
                "Created_By": creator.username,
                "Created_At": int(capa.created_at.timestamp() * 1000),
            }

            result = upsert_bitable_record_via_relay(
                app_token=settings.CAPA_BITABLE_APP_TOKEN.strip(),
                table_id=settings.CAPA_BITABLE_TABLE_ID.strip(),
                records=[fields],
                match_field="CAPA_ID",
            )

        except Exception:
            print("❌ CAPA CREATE sync failed")
            traceback.print_exc()

    threading.Thread(target=_send, daemon=True).start()



# =========================================================
# UPDATE SYNC
# =========================================================

def send_capa_update_async(capa, actor):

    def _send():
        try:
            submission = capa.submission
            template = submission.template_version.template

            fields = {
                "CAPA_ID": str(capa.capa_id),
                "Status": capa.status,
                "RCA_Summary": capa.rca_summary or "",
                "RCA_By": capa.rca_submitted_by.username if capa.rca_submitted_by else "",
                "RCA_Submitted_At": (
                    int(capa.rca_submitted_at.timestamp() * 1000)
                    if capa.rca_submitted_at else None
                ),
                "CAPA_Plan": capa.capa_plan or "",
                "CAPA_By": capa.capa_submitted_by.username if capa.capa_submitted_by else "",
                "CAPA_Submitted_At": (
                    int(capa.capa_submitted_at.timestamp() * 1000)
                    if capa.capa_submitted_at else None
                ),
                "Rejection_Reason": capa.rejection_reason or "",
                "Closed_At": (
                    int(capa.closed_at.timestamp() * 1000)
                    if capa.closed_at else None
                ),
            }

            # Only add Approved_By if closed
            if capa.status == "CLOSED":
                fields["Approved_By"] = actor.username

            upsert_bitable_record_via_relay(
                app_token=settings.CAPA_BITABLE_APP_TOKEN.strip(),
                table_id=settings.CAPA_BITABLE_TABLE_ID.strip(),
                records=[fields],
                match_field="CAPA_ID",
            )

        except Exception as e:
            print("❌ CAPA UPDATE sync failed")
            traceback.print_exc()

    threading.Thread(target=_send, daemon=True).start()
