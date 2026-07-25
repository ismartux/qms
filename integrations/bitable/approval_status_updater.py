import threading
import requests
from django.conf import settings
from submissions.models import SubmissionApproval, DynamicSubmissionApproval


def update_approval_status_async(submission, approval):
    """
    CHECKLIST approval status updater (ASYNC)

    Category-based approval engine.
    Mirrors Dynamic approval updater exactly.
    """

    import threading
    import requests
    from django.conf import settings

    def _send():
        try:

            # -------------------------------------------------
            # Reload submission (CRITICAL)
            # -------------------------------------------------
            submission.refresh_from_db()

            # -------------------------------------------------
            # Timestamp
            # -------------------------------------------------
            approved_at_ms = (
                int(approval.created_at.timestamp() * 1000)
                if approval.created_at
                else None
            )

            category = approval.category.code  # 🔑 category code

            # -------------------------------------------------
            # Base Category Fields
            # -------------------------------------------------
            fields = {
                "Submission_ID": str(submission.submission_id),

                f"{category}_Status": approval.status,
                f"{category}_Rejection_Reason": approval.rejection_reason or "",
                f"{category}_Approved_By": approval.approver_name or "",
                f"{category}_Approved_At": approved_at_ms,
            }

            # -------------------------------------------------
            # 🚀 FINAL STATUS LOGIC (CHECKLIST – CATEGORY ENGINE)
            # -------------------------------------------------

            # 🔴 ANY rejection → FINAL = REJECTED
            if SubmissionApproval.objects.filter(
                submission=submission,
                status="REJECTED",
            ).exists():
                fields["Final_Status"] = "REJECTED"

            else:
                template = submission.template_version.template

                # Required approval steps
                required_steps = (
                    template.approval_steps
                    .select_related("category")
                    .filter(is_required=True)
                    .order_by("order")
                )

                required_categories = {
                    step.category.code for step in required_steps
                }

                approved_categories = set(
                    SubmissionApproval.objects.filter(
                        submission=submission,
                        status="APPROVED",
                    ).values_list("category__code", flat=True)
                )

                # 🟢 All required categories approved → FINAL = APPROVED
                if required_categories.issubset(approved_categories):
                    fields["Final_Status"] = "APPROVED"

            # -------------------------------------------------
            # Payload
            # -------------------------------------------------
            payload = {
                "app_token": settings.BITABLE_APPROVAL_APP_TOKEN.strip(),
                "table_id": settings.BITABLE_APPROVAL_TABLE_ID.strip(),
                "records": [fields],
                "match_field": "Submission_ID",
            }

            print("🔥 Sending CHECKLIST approval update to worker...")

            requests.post(
                settings.CLOUDFLARE_UPSERT_RELAY_URL,
                json=payload,
                headers={
                    "X-RELAY-SECRET": settings.CLOUDFLARE_UPSERT_RELAY_SECRET
                },
                timeout=20,
            )

        except Exception as e:
            print("❌ Checklist approval status update failed:", str(e))

    threading.Thread(target=_send, daemon=True).start()
    
def update_dynamic_approval_status_async(submission, approval):
    """
    Dynamic Form approval status updater (ASYNC)

    Category-based (NO hardcoded PD/PE/PQE)

    Uses:
    - DynamicFormSubmission
    - DynamicSubmissionApproval
    - TemplateApprovalStep
    - ApprovalCategory
    """

    def _send():
        try:

            # -------------------------------------------------
            # Reload submission (CRITICAL)
            # -------------------------------------------------
            submission.refresh_from_db()

            # -------------------------------------------------
            # Timestamp
            # -------------------------------------------------
            approved_at_ms = (
                int(approval.created_at.timestamp() * 1000)
                if approval.created_at
                else None
            )

            category = approval.category  # 🔑 ApprovalCategory

            # -------------------------------------------------
            # Base Category Fields
            # -------------------------------------------------
            fields = {
                "Submission_ID": str(submission.submission_id),

                f"{category.code}_Status": approval.status,
                f"{category.code}_Rejection_Reason": approval.rejection_reason or "",
                f"{category.code}_Approved_By": approval.approver_name or "",
                f"{category.code}_Approved_At": approved_at_ms,
            }

            # -------------------------------------------------
            # 🚀 FINAL STATUS LOGIC (CATEGORY-BASED)
            # -------------------------------------------------

            # 🔴 ANY rejection → FINAL = REJECTED
            if DynamicSubmissionApproval.objects.filter(
                submission=submission,
                status="REJECTED",
            ).exists():
                fields["Final_Status"] = "REJECTED"

            else:
                template = submission.template_version.template

                # Required approval categories (ordered, active)
                required_categories = list(
                    template.approval_steps
                    .filter(is_required=True)
                    .values_list("category__code", flat=True)
                )

                approved_categories = set(
                    DynamicSubmissionApproval.objects.filter(
                        submission=submission,
                        status="APPROVED",
                    ).values_list("category__code", flat=True)
                )

                # 🟢 All required approvals satisfied
                if required_categories and set(required_categories).issubset(
                    approved_categories
                ):
                    fields["Final_Status"] = "APPROVED"

            # -------------------------------------------------
            # Payload
            # -------------------------------------------------
            payload = {
                "app_token": settings.BITABLE_APPROVAL_APP_TOKEN.strip(),
                "table_id": settings.BITABLE_APPROVAL_TABLE_ID.strip(),
                "records": [fields],
                "match_field": "Submission_ID",
            }

            print("🔥 Sending DYNAMIC approval update to worker...")

            requests.post(
                settings.CLOUDFLARE_UPSERT_RELAY_URL,
                json=payload,
                headers={
                    "X-RELAY-SECRET": settings.CLOUDFLARE_UPSERT_RELAY_SECRET
                },
                timeout=20,
            )

        except Exception as e:
            print("❌ Dynamic approval status update failed:", str(e))


import threading
import requests
from django.conf import settings
from django.db import transaction


def update_approval_status_async(submission, approval):

    def _send():
        try:
            from submissions.services import get_required_approval_roles
            from submissions.models import SubmissionApproval

            # -------------------------------------------------
            # Reload submission from DB (CRITICAL FIX)
            # -------------------------------------------------
            submission.refresh_from_db()

            # -------------------------------------------------
            # Timestamp
            # -------------------------------------------------
            approved_at_ms = None
            if approval.created_at:
                approved_at_ms = int(
                    approval.created_at.timestamp() * 1000
                )

            role = approval.role  # "PD", "PE", or "PQE"

            # -------------------------------------------------
            # Base Role Fields
            # -------------------------------------------------
            fields = {
                "Submission_ID": str(submission.submission_id),

                f"{role}_Status": approval.status,
                f"{role}_Rejection_Reason": approval.rejection_reason or "",
                f"{role}_Approved_By": approval.approver_name or "",
                f"{role}_Approved_At": approved_at_ms,
            }

            # -------------------------------------------------
            # 🚀 FINAL STATUS LOGIC (Deterministic + Safe)
            # -------------------------------------------------

            # 🔴 ANY rejection → FINAL = REJECTED
            if SubmissionApproval.objects.filter(
                submission=submission,
                status="REJECTED"
            ).exists():
                fields["Final_Status"] = "REJECTED"

            # 🟢 PQE approval → FINAL = APPROVED
            elif approval.role == "PQE" and approval.status == "APPROVED":
                fields["Final_Status"] = "APPROVED"

            else:
                # Fallback dynamic logic
                required_roles = get_required_approval_roles(submission)

                approved_roles = set(
                    SubmissionApproval.objects.filter(
                        submission=submission,
                        status="APPROVED"
                    ).values_list("role", flat=True)
                )

                if required_roles and set(required_roles).issubset(approved_roles):
                    fields["Final_Status"] = "APPROVED"

            # -------------------------------------------------
            # Payload
            # -------------------------------------------------
            payload = {
                "app_token": settings.BITABLE_APPROVAL_APP_TOKEN.strip(),
                "table_id": settings.BITABLE_APPROVAL_TABLE_ID.strip(),
                "records": [fields],
                "match_field": "Submission_ID",
            }

            print("🔥 Sending approval update to worker...")

            r = requests.post(
                settings.CLOUDFLARE_UPSERT_RELAY_URL,
                json=payload,
                headers={
                    "X-RELAY-SECRET": settings.CLOUDFLARE_UPSERT_RELAY_SECRET
                },
                timeout=20
            )

        except Exception as e:
            print("❌ Approval status update failed:", str(e))

    threading.Thread(target=_send, daemon=True).start()