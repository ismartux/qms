import threading
import requests
from django.conf import settings
from submissions.models import SubmissionApproval, DynamicSubmissionApproval


def update_approval_status_async(submission, approval):
    """
    CHECKLIST approval status updater (ASYNC)

    Category-based approval engine.
    Mirrors Dynamic approval updater exactly.

    🔑 FIX: Also clears the approval link for the approved category
    so that already-approved categories show "Approved" instead of
    a pending approval link.
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
            # 🔑 FIX: Clear the approval link for the approved category
            # so already-approved categories show "Approved" instead
            # of a pending approval link in Bitable/email.
            # -------------------------------------------------
            if approval.status == "APPROVED":
                fields[f"{category}_Approval_Link"] = "Approved"

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
            # -------------------------------------------------
            # 🔑 FIX: Clear the approval link for the approved category
            # so already-approved categories show "Approved" instead
            # of a pending approval link in Bitable/email.
            # -------------------------------------------------
            if approval.status == "APPROVED":
                fields[f"{category.code}_Approval_Link"] = "Approved"

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

    threading.Thread(target=_send, daemon=True).start()
