# integrations/bitable/approval_sender.py

import requests
import threading
from django.conf import settings
from django.utils.crypto import get_random_string
from dynamic_forms.models import DynamicFormTemplate
from core.identity.context import get_user_role
from forms_engine.models import ChecklistTemplate

def send_submission_approval_record(submission):
    """
    CHECKLIST approval sender (CATEGORY-BASED)

    Uses:
    - ApprovalCategory
    - ChecklistApprovalStep
    - Public checklist approval links
    """

    # --------------------------------------------------
    # SAFETY: TOKEN MUST EXIST
    # --------------------------------------------------
    token = submission.public_approval_token
    if not token:
        token = get_random_string(32)
        submission.public_approval_token = token
        submission.save(update_fields=["public_approval_token"])

    base_url = settings.SITE_BASE_URL.rstrip("/")

    template = submission.template_version.template
    if not isinstance(template, ChecklistTemplate):
        return

    # --------------------------------------------------
    # FETCH REQUIRED APPROVAL STEPS (ORDERED)
    # --------------------------------------------------
    steps = (
        template.approval_steps
        .select_related("category")
        .filter(is_required=True)
        .order_by("order")
    )

    if not steps.exists():
        return

    # --------------------------------------------------
    # BUILD CATEGORY-BASED APPROVAL LINKS
    # --------------------------------------------------
    approval_links = {}
    for step in steps:
        category = step.category
        approval_links[category.code] = (
            f"{base_url}/public-approval/"
            f"{token}/{category.code}/"
        )

    # --------------------------------------------------
    # CONTEXT FIELDS
    # --------------------------------------------------
    wc = submission.work_context
    user = submission.submitted_by

    submitted_by_display = (
        f"{user.get_full_name()} ({user.username})"
        if user.get_full_name()
        else user.username
    )

    # --------------------------------------------------
    # BASE FIELDS (CHECKLIST)
    # --------------------------------------------------
    fields = {
        "Submission_ID": str(submission.submission_id),
        "Template_Name": template.name,

        "Plant": submission.plant.name if submission.plant else "",
        "Line": submission.line.name if submission.line else "",
        "Shift": wc.shift if wc else "",
        "Work_Date": int(submission.submitted_at.timestamp() * 1000),

        "Product": submission.product.name if submission.product else "",
        "Color": wc.model_color if wc else "",

        "Submitted_By": submitted_by_display,
        "Submitted_At": int(submission.submitted_at.timestamp() * 1000),

        "Final_Status": "PENDING",
    }

    # --------------------------------------------------
    # ADD ONLY REQUIRED CATEGORY LINKS
    # --------------------------------------------------
    for code, url in approval_links.items():
        fields[f"{code}_Approval_Link"] = url

    # --------------------------------------------------
    # BITABLE PAYLOAD
    # --------------------------------------------------
    # Retrieve Bitable credentials from admin config, fallback to settings
    from notifications.models import BitableConfig
    _config = BitableConfig.objects.filter(name="Approval").first()
    if _config:
        _app_token = _config.app_token.strip()
        _table_id = _config.table_id.strip()
    else:
        _app_token = settings.BITABLE_APPROVAL_APP_TOKEN.strip()
        _table_id = settings.BITABLE_APPROVAL_TABLE_ID.strip()

    payload = {
        "app_token": _app_token,
        "table_id": _table_id,
        "records": [fields],
        "match_field": "Submission_ID",
    }

    # --------------------------------------------------
    # ASYNC SEND
    # --------------------------------------------------
    def _send_async():
        try:
            requests.post(
                settings.CLOUDFLARE_UPSERT_RELAY_URL,
                json=payload,
                headers={
                    "X-RELAY-SECRET": settings.CLOUDFLARE_UPSERT_RELAY_SECRET
                },
                timeout=15,
            )
        except Exception as e:
            print("❌ Checklist Approval Worker error:", e)

    threading.Thread(target=_send_async, daemon=True).start()
    
    
def send_dynamic_submission_approval_record(submission):
    """
    DYNAMIC FORM approval sender (CHECKLIST-PARITY)

    - Triggers AFTER submission
    - Uses TemplateApprovalStep as single authority
    - NO role re-validation
    - NO requires_work_context checks
    """

    # --------------------------------------------------
    # TEMPLATE SAFETY
    # --------------------------------------------------
    template = submission.template_version.template
    if not isinstance(template, DynamicFormTemplate):
        return

    # --------------------------------------------------
    # SAFETY: TOKEN MUST EXIST
    # --------------------------------------------------
    token = submission.public_approval_token
    if not token:
        token = get_random_string(32)
        submission.public_approval_token = token
        submission.save(update_fields=["public_approval_token"])

    base_url = settings.SITE_BASE_URL.rstrip("/")

    # --------------------------------------------------
    # FETCH REQUIRED APPROVAL STEPS (ORDERED)
    # --------------------------------------------------
    steps = (
        template.approval_steps
        .select_related("category")
        .filter(is_required=True)
        .order_by("order")
    )

    if not steps.exists():
        return  # No approvals configured

    # --------------------------------------------------
    # BUILD CATEGORY-BASED APPROVAL LINKS
    # --------------------------------------------------
    approval_links = {}
    for step in steps:
        category = step.category
        approval_links[category.code] = (
            f"{base_url}/public-dynamic-approval/"
            f"{token}/{category.code}/"
        )

    # --------------------------------------------------
    # CONTEXT FIELDS (SAFE)
    # --------------------------------------------------
    wc = submission.work_context
    user = submission.submitted_by

    submitted_by_display = (
        f"{user.get_full_name()} ({user.username})"
        if user.get_full_name()
        else user.username
    )

    def _val(v):
        if isinstance(v, str):
            return v
        return getattr(v, "name", "") if v else ""

    # --------------------------------------------------
    # BASE FIELDS (MATCH CHECKLIST)
    # --------------------------------------------------
    fields = {
        "Submission_ID": str(submission.submission_id),
        "Template_Name": template.name,

        "Plant": _val(getattr(wc, "plant", None)),
        "Line": _val(getattr(wc, "line", None)),
        "Shift": _val(getattr(wc, "shift", None)),
        "Work_Date": int(submission.submitted_at.timestamp() * 1000),

        "Product": _val(getattr(wc, "product", None)),
        "Color": getattr(wc, "model_color", "") if wc else "",

        "Submitted_By": submitted_by_display,
        "Submitted_At": int(submission.submitted_at.timestamp() * 1000),

        "Final_Status": "PENDING",
    }

    # --------------------------------------------------
    # ADD ONLY REQUIRED CATEGORY LINKS
    # --------------------------------------------------
    for code, url in approval_links.items():
        fields[f"{code}_Approval_Link"] = url

    # --------------------------------------------------
    # BITABLE PAYLOAD
    # --------------------------------------------------
    # Retrieve Bitable credentials from admin config, fallback to settings
    from notifications.models import BitableConfig
    _config = BitableConfig.objects.filter(name="Approval").first()
    if _config:
        _app_token = _config.app_token.strip()
        _table_id = _config.table_id.strip()
    else:
        _app_token = settings.BITABLE_APPROVAL_APP_TOKEN.strip()
        _table_id = settings.BITABLE_APPROVAL_TABLE_ID.strip()

    payload = {
        "app_token": _app_token,
        "table_id": _table_id,
        "records": [fields],
        "match_field": "Submission_ID",
    }

    # --------------------------------------------------
    # ASYNC SEND
    # --------------------------------------------------
    def _send_async():
        try:
            requests.post(
                settings.CLOUDFLARE_UPSERT_RELAY_URL,
                json=payload,
                headers={
                    "X-RELAY-SECRET": settings.CLOUDFLARE_UPSERT_RELAY_SECRET
                },
                timeout=15,
            )
        except Exception as e:
            print("❌ Dynamic Approval Sender Error:", e)

    threading.Thread(target=_send_async, daemon=True).start()