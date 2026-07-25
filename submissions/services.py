from django.db import transaction, IntegrityError
from django.utils import timezone

from submissions.models import (
    Submission,
    SubmissionResponse,
    SubmissionSyncLog,
    WorkContext,
    SubmissionAttachment,
)

from forms_engine.models import (
    ChecklistTemplate,
    ChecklistItem,
    ChecklistItemOption,
)

from core.workflow.states import WorkflowState
from core.audit.models import AuditLog, DomainEvent
from capa.services import maybe_trigger_capa

from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from integrations.bitable.full_submission_sender import (
    send_full_submission_to_worker,
)
from integrations.bitable.approval_sender import (
    send_submission_approval_record,
)

# 🔐 Tenant context support (middleware compatible)
from core.tenant.context import set_current_plant


# =====================================================
# Approval Flow Resolver
# =====================================================

def get_required_approval_roles(*args, **kwargs):
    raise RuntimeError(
        "get_required_approval_roles is deprecated. "
        "Use ApprovalCategory + ApprovalStep instead."
    )


# =====================================================
# Draft handling (Race-safe with DB constraint support)
# =====================================================

def get_or_create_draft_submission(user, template, work_context):

    if not work_context or not work_context.is_active:
        raise ValueError("No active work context")

    version = template.versions.filter(is_active=True).first()
    if not version:
        raise ValueError("No active template version found")

    submission = Submission.objects.filter(
        submitted_by=user,
        template_version=version,
        work_context=work_context,
        workflow_state=WorkflowState.DRAFT,
    ).first()

    if submission:
        return submission

    try:
        return Submission.objects.create(
            submitted_by=user,
            template_version=version,
            work_context=work_context,
            plant=work_context.plant,
            shop=work_context.shop,
            line=work_context.line,
            product=work_context.product,
            workflow_state=WorkflowState.DRAFT,
        )
    except IntegrityError:
        # Stronger retry safety under race condition
        return Submission.objects.select_for_update().get(
            submitted_by=user,
            template_version=version,
            work_context=work_context,
            workflow_state=WorkflowState.DRAFT,
        )


# =====================================================
# Save responses (Safe + optimized, no behavior change)
# =====================================================

@transaction.atomic
def save_submission_responses(submission, post_data, files=None):

    if files is None:
        files = {}

    # Preload existing responses once (performance optimization)
    existing_responses = {
        str(r.item_id): r
        for r in SubmissionResponse.objects.filter(submission=submission)
    }

    for key, value in post_data.items():

        if not key.startswith("item_"):
            continue

        suffix = key.replace("item_", "")

        if not suffix.isdigit():
            continue

        item_id = int(suffix)

        item = ChecklistItem.objects.filter(id=item_id).first()
        if not item:
            continue

        # DROPDOWN VALIDATION
        if item.item_type == "DROPDOWN":
            value = value.strip()
            option = ChecklistItemOption.objects.filter(
                item=item,
                value__iexact=value
            ).first()

            if not option:
                continue

            value = option.value

        # BOOLEAN VALIDATION
        if item.item_type == "BOOLEAN":
            if value not in ("YES", "NO", "NA"):
                continue

        remark_key = f"item_remark_{item_id}"

        existing_remark = (
            existing_responses.get(str(item_id)).remark
            if str(item_id) in existing_responses
            else ""
        )

        if remark_key in post_data:
            remark = post_data.get(remark_key, "").strip()
        else:
            remark = existing_remark or ""

        SubmissionResponse.objects.update_or_create(
            submission=submission,
            item_id=str(item_id),
            defaults={
                "value": value,
                "remark": remark,
                "is_non_conformance": (
                    value == "NO" if item.item_type == "BOOLEAN" else False
                ),
            },
        )

    # --------------------------------
    # Attachments
    # --------------------------------

    for key, file in files.items():

        if key.startswith("item_file_"):
            suffix = key.replace("item_file_", "")
            attachment_type = "BASE"

        elif key.startswith("item_rule_photo_"):
            suffix = key.replace("item_rule_photo_", "")
            attachment_type = "RULE"

        else:
            continue

        if not suffix.isdigit():
            continue

        item_id = int(suffix)

        SubmissionAttachment.objects.filter(
            submission=submission,
            checklist_item_id=item_id,
            attachment_type=attachment_type,
        ).delete()

        SubmissionAttachment.objects.create(
            submission=submission,
            checklist_item_id=item_id,
            attachment_type=attachment_type,
            file=file,
        )


# =====================================================
# Severity calculation
# =====================================================

def calculate_severity_score(submission):
    return SubmissionResponse.objects.filter(
        submission=submission,
        is_non_conformance=True
    ).count()


# =====================================================
# Submit (Transaction safe + external safe + tenant safe)
# =====================================================

@transaction.atomic
def submit_submission(submission, user):

    # --------------------------------------------------
    # Ensure tenant context active for middleware isolation
    # --------------------------------------------------
    set_current_plant(submission.plant)

    if submission.workflow_state != WorkflowState.DRAFT:
        raise ValueError("Only DRAFT submissions can be submitted")

    template = submission.template_version.template

    # --------------------------------------------------
    # Bitable configuration guard
    # --------------------------------------------------
    if not template.bitable_app_token or not template.bitable_table_id:
        raise ValidationError(
            {
                "bitable": (
                    f"Bitable is not configured for checklist template "
                    f"'{template.code}'. "
                    f"Please set Bitable App Token and Table ID."
                )
            }
        )

    # --------------------------------------------------
    # Validation & preprocessing (UNCHANGED)
    # --------------------------------------------------
    auto_fill_na_for_missing_required_booleans(submission)
    validate_required_items(submission)

    severity = calculate_severity_score(submission)

    # --------------------------------------------------
    # 🔑 REQUIRED APPROVAL CATEGORIES (NEW ENGINE)
    # --------------------------------------------------
    required_categories = list(
        template.approval_steps
        .filter(is_required=True)
        .select_related("category")
        .order_by("order")
        .values_list("category__code", flat=True)
    )

    # --------------------------------------------------
    # WORKFLOW TRANSITION (UNCHANGED SEMANTICS)
    # --------------------------------------------------
    submission.workflow_state = (
        WorkflowState.CLOSED
        if not required_categories
        else WorkflowState.SUBMITTED
    )

    submission.submitted_by = user
    submission.submitted_at = timezone.now()
    submission.severity_score = severity
    submission.save()

    # --------------------------------------------------
    # AUDIT LOG (UNCHANGED)
    # --------------------------------------------------
    AuditLog.objects.create(
        actor=user,
        action="SUBMISSION_SUBMITTED",
        object_type="Submission",
        object_id=str(submission.submission_id),
        metadata={"severity": severity},
    )

    # --------------------------------------------------
    # DOMAIN EVENT (UNCHANGED)
    # --------------------------------------------------
    DomainEvent.objects.create(
        event_type="SUBMISSION_SUBMITTED",
        object_type="Submission",
        object_id=str(submission.submission_id),
        payload={
            "severity": severity,
            "plant_id": submission.plant_id,
        },
    )

    # --------------------------------------------------
    # CAPA LOGIC (UNCHANGED)
    # --------------------------------------------------
    maybe_trigger_capa(submission)

    # --------------------------------------------------
    # POST-COMMIT EXTERNAL ACTIONS (UNCHANGED STRUCTURE)
    # --------------------------------------------------
    def post_commit_actions():

        # 🔑 Send approval record ONLY if approval is required
        if required_categories:
            send_submission_approval_record(submission)

        send_full_submission_to_worker(submission)

    transaction.on_commit(post_commit_actions)


# =====================================================
# Sync helpers
# =====================================================

def mark_sync_pending(submission, target):
    SubmissionSyncLog.objects.get_or_create(
        submission=submission,
        target=target,
        defaults={"status": "PENDING"},
    )


# =====================================================
# Offline submission support (Tenant Safe)
# =====================================================

@transaction.atomic
def submit_submission_from_payload(payload: dict, user: User):

    template_code = payload.get("template_code")
    work_context_id = payload.get("work_context_id")

    if not template_code or not work_context_id:
        raise ValueError("Invalid offline payload")

    work_context = get_object_or_404(
        WorkContext,
        id=work_context_id,
        is_active=True,
    )

    # Ensure tenant context active
    set_current_plant(work_context.plant)

    template = get_object_or_404(
        ChecklistTemplate,
        code=template_code,
        is_active=True,
    )

    submission = get_or_create_draft_submission(
        user=user,
        template=template,
        work_context=work_context,
    )

    save_submission_responses(
        submission=submission,
        post_data=payload,
        files=None,
    )

    validate_required_items(submission)

    submit_submission(
        submission=submission,
        user=user,
    )

    return submission


# =====================================================
# Rule validation
# =====================================================

def validate_submission_rules(submission):

    responses = {
        str(r.item_id): r
        for r in SubmissionResponse.objects.filter(submission=submission)
    }

    items = ChecklistItem.objects.filter(
        section__version=submission.template_version
    ).prefetch_related("rules")

    errors = []

    for item in items:
        response = responses.get(str(item.id))
        response_value = response.value if response else ""

        for rule in item.rules.all():

            if response_value == "NA":
                continue

            if rule.condition_value and response_value != rule.condition_value:
                continue

            if rule.rule_type == "REMARK_REQUIRED":
                remark = (response.remark or "").strip() if response else ""
                if not remark:
                    errors.append(f"Remark required for: {item.label}")

    if errors:
        raise ValueError(errors)



# =====================================================
# Required validation (FINAL AUTHORITY)
# =====================================================

def validate_required_items(submission):

    # ---------------- RESPONSES ----------------
    responses = {
        str(r.item_id): r
        for r in SubmissionResponse.objects.filter(submission=submission)
    }

    # ---------------- ATTACHMENTS ----------------
    attachments = {}
    for att in SubmissionAttachment.objects.filter(submission=submission):
        try:
            attachments.setdefault(str(att.checklist_item_id), []).append(att)
        except Exception:
            continue

    # ---------------- REQUIRED ITEMS ----------------
    items = ChecklistItem.objects.filter(
        section__version=submission.template_version,
        required=True
    )

    errors = []

    for item in items:
        item_id = str(item.id)

        # ============================================
        # PHOTO ITEMS → validate via attachments
        # ============================================
        if item.item_type == "PHOTO":
            if item_id not in attachments:
                errors.append(f"{item.label} is required")
            continue

        # ============================================
        # NON-PHOTO ITEMS → validate via response
        # ============================================
        response = responses.get(item_id)

        if not response:
            errors.append(f"{item.label} is required")
            continue

        value = (response.value or "").strip()

        if value == "":
            errors.append(f"{item.label} is required")
            continue

        # NA is valid
        if value == "NA":
            continue

    if errors:
        raise ValidationError(errors)

# =====================================================
# Auto-fill missing boolean required
# =====================================================

def auto_fill_na_for_missing_required_booleans(submission):

    existing_ids = set(
        SubmissionResponse.objects.filter(submission=submission)
        .values_list("item_id", flat=True)
    )

    required_boolean_items = ChecklistItem.objects.filter(
        section__version=submission.template_version,
        required=True,
        item_type="BOOLEAN",
    )

    for item in required_boolean_items:
        if str(item.id) not in existing_ids:
            SubmissionResponse.objects.create(
                submission=submission,
                item_id=str(item.id),
                value="NA",
                remark="",
                is_non_conformance=False,
            )
            
      
