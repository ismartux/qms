# ui/utils/required_validation.py

from submissions.models import SubmissionAttachment
from submissions.models import DynamicFormSubmission


def get_missing_required_items(
    *,
    submission,
    section,
    post_data,
    files,
):
    """
    Checklist-only required field validation.

    IMPORTANT:
    - This function MUST NOT run for dynamic forms
    - Dynamic forms validation is handled by runtime engine
    """

    # =====================================================
    # 🔒 ENGINE GUARD (CRITICAL)
    # =====================================================
    if isinstance(submission, DynamicFormSubmission):
        # Dynamic forms do NOT use section/item validation
        return []

    missing_items = []

    # =====================================================
    # EXISTING ATTACHMENTS
    # =====================================================
    attachments = SubmissionAttachment.objects.filter(
        submission=submission
    )

    attachment_map = {}
    for att in attachments:
        try:
            attachment_map.setdefault(
                int(att.checklist_item_id), set()
            ).add(att.attachment_type)
        except (TypeError, ValueError):
            continue

    # =====================================================
    # EXISTING RESPONSES
    # =====================================================
    responses = {}
    for r in submission.responses.all():
        try:
            responses[int(r.item_id)] = r
        except (TypeError, ValueError):
            # Skip corrupted legacy rows like "file_3"
            continue

    # =====================================================
    # VALIDATION LOOP (UNCHANGED LOGIC)
    # =====================================================
    for item in section.items.filter(required=True):
        item_id = item.id
        has_value = False

        # ---------- BASE VALUE ----------
        if item.item_type == "BOOLEAN":
            has_value = (
                f"item_{item_id}" in post_data
                or item_id in responses
            )

        elif item.item_type in ("TEXT", "NUMBER", "DROPDOWN"):
            has_value = (
                post_data.get(f"item_{item_id}", "").strip()
                or (responses.get(item_id) and responses[item_id].value)
            )

        elif item.item_type == "PHOTO":
            has_value = (
                f"item_file_{item_id}" in files
                or "BASE" in attachment_map.get(item_id, set())
            )

        # ---------- CURRENT RESPONSE VALUE ----------
        response_value = (
            post_data.get(f"item_{item_id}")
            or (responses.get(item_id).value if responses.get(item_id) else "")
        )

        # 🚫 STRICT RULE: NA IS A COMPLETE ANSWER
        if response_value == "NA":
            if not has_value:
                missing_items.append(item)
            continue

        # ---------- RULE VALIDATION ----------
        for rule in item.rules.all():

            if rule.condition_value and response_value != rule.condition_value:
                continue

            # PHOTO_REQUIRED
            if rule.rule_type == "PHOTO_REQUIRED":
                if "RULE" not in attachment_map.get(item_id, set()):
                    has_value = False

            # REMARK_REQUIRED
            if rule.rule_type == "REMARK_REQUIRED":
                remark = (
                    post_data.get(f"item_remark_{item_id}", "").strip()
                    or (responses.get(item_id).remark if responses.get(item_id) else "")
                )
                if not remark:
                    has_value = False

        if not has_value:
            missing_items.append(item)

    return missing_items