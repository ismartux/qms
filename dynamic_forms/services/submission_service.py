from django.db import transaction, IntegrityError
from django.utils import timezone
from django.core.exceptions import ValidationError

from core.workflow.states import WorkflowState

from dynamic_forms.models import (
    DynamicFormTemplate,
    DynamicFormVersion,
    DynamicFormField,
    DynamicTemplateRole,
)

from submissions.models import (
    WorkContext,
    DynamicFormSubmission,
    DynamicFormSubmissionValue,
)

from dynamic_forms.services.validation_service import (
    validate_dynamic_submission,
)

from integrations.bitable.dynamic_service import (
    sync_dynamic_submission,
)
from integrations.bitable.approval_sender import (
    send_dynamic_submission_approval_record,
)

from django.core.files.storage import default_storage
from django.utils.text import get_valid_filename
import uuid


# =========================================================
# DRAFT CREATION (ROLE + CONTEXT AWARE)
# =========================================================
def get_or_create_dynamic_form_draft(
    *,
    user,
    template: DynamicFormTemplate,
    role,
    work_context: WorkContext | None,
) -> DynamicFormSubmission:
    """
    Returns an existing DRAFT or creates a new one.

    Rules:
    - Superuser bypasses role checks
    - Non-superuser must have role assigned to template
    - requires_work_context is VALIDATED
    - WorkContext is ALWAYS attached if provided
    - One DRAFT per (user, version, work_context)
    """

    # -----------------------------------------------------
    # ACTIVE + PUBLISHED VERSION
    # -----------------------------------------------------
    version = template.versions.filter(
        is_active=True,
        is_published=True,
    ).first()

    if not version:
        raise ValidationError(
            f"No active published version for template '{template.code}'"
        )

    # -----------------------------------------------------
    # SUPERUSER BYPASS
    # -----------------------------------------------------
    if user.is_superuser:
        normalized_work_context = work_context

    else:
        # -------------------------------------------------
        # ROLE CHECK
        # -------------------------------------------------
        if not role:
            raise PermissionError(
                "No active role available for submission"
            )

        assignment = DynamicTemplateRole.objects.filter(
            template=template,
            role=role,
        ).first()

        if not assignment:
            raise PermissionError(
                f"Role '{role.code}' is not allowed to submit this template"
            )

        # -------------------------------------------------
        # WORK CONTEXT VALIDATION (NOT DROPPING)
        # -------------------------------------------------
        if assignment.requires_work_context:
            if not work_context or not work_context.is_active:
                raise ValidationError(
                    "Active Work Context is required for this template"
                )

        # 🔑 FIX: ALWAYS KEEP WORK CONTEXT IF PROVIDED
        normalized_work_context = work_context

    # -----------------------------------------------------
    # EXISTING DRAFT
    # -----------------------------------------------------
    draft = DynamicFormSubmission.objects.filter(
        submitted_by=user,
        template_version=version,
        work_context=normalized_work_context,
        workflow_state=WorkflowState.DRAFT,
    ).first()

    if draft:
        return draft

    # -----------------------------------------------------
    # CREATE DRAFT (RACE-SAFE)
    # -----------------------------------------------------
    try:
        return DynamicFormSubmission.objects.create(
            submitted_by=user,
            template_version=version,
            work_context=normalized_work_context,
            workflow_state=WorkflowState.DRAFT,
        )

    except IntegrityError:
        return DynamicFormSubmission.objects.select_for_update().get(
            submitted_by=user,
            template_version=version,
            work_context=normalized_work_context,
            workflow_state=WorkflowState.DRAFT,
        )


# =========================================================
# SAVE FIELD VALUES (IDEMPOTENT)
# =========================================================
@transaction.atomic
def save_dynamic_form_values(
    *,
    submission: DynamicFormSubmission,
    payload: dict,
    files=None,
):
    """
    Saves dynamic form values.
    - TEXT / NUMBER / DROPDOWN → stored directly
    - IMAGE → uploaded to Cloudflare R2, URL stored
    """

    if submission.workflow_state != WorkflowState.DRAFT:
        raise ValidationError("Only draft submissions can be modified")

    files = files or {}

    # -----------------------------------------------------
    # FIELD MAP
    # -----------------------------------------------------
    fields = {
        f.id: f
        for f in DynamicFormField.objects.filter(
            version=submission.template_version
        )
    }

    # -----------------------------------------------------
    # SAVE NON-IMAGE FIELDS
    # -----------------------------------------------------
    for raw_key, raw_value in payload.items():

        if not raw_key.startswith("field_"):
            continue

        try:
            field_id = int(raw_key.split("_", 1)[1])
        except (IndexError, ValueError):
            continue

        field = fields.get(field_id)
        if not field or field.data_type == "IMAGE":
            continue

        value = "" if raw_value is None else str(raw_value).strip()

        DynamicFormSubmissionValue.objects.update_or_create(
            submission=submission,
            field_id=field_id,
            defaults={
                "value": value,
                "remark": "",
                "is_non_conformance": False,
            },
        )

    # -----------------------------------------------------
    # SAVE IMAGE FIELDS → CLOUDFLARE R2
    # -----------------------------------------------------
    for raw_key, uploaded_file in files.items():

        if not raw_key.startswith("field_"):
            continue

        try:
            field_id = int(raw_key.split("_", 1)[1])
        except (IndexError, ValueError):
            continue

        field = fields.get(field_id)
        if not field or field.data_type != "IMAGE":
            continue

        if not uploaded_file:
            continue

        safe_name = get_valid_filename(uploaded_file.name)
        unique_name = f"{uuid.uuid4().hex}_{safe_name}"

        storage_path = (
            f"dynamic_forms/"
            f"{submission.template_version.template.code}/"
            f"{submission.pk}/"
            f"{unique_name}"
        )

        saved_path = default_storage.save(
            storage_path,
            uploaded_file,
        )

        public_url = default_storage.url(saved_path)

        DynamicFormSubmissionValue.objects.update_or_create(
            submission=submission,
            field_id=field_id,
            defaults={
                "value": public_url,
                "remark": "",
                "is_non_conformance": False,
            },
        )


# =========================================================
# SUBMIT (FINAL AUTHORITY)
# =========================================================
@transaction.atomic
def submit_dynamic_form_submission(
    *,
    submission: DynamicFormSubmission,
    user,
    enforce_standards: bool = False,
):
    """
    Final submission step.
    THIS IS THE SINGLE SOURCE OF TRUTH.
    """

    if submission.workflow_state != WorkflowState.DRAFT:
        raise ValidationError("Only draft submissions can be submitted")

    # -----------------------------------------------------
    # VALIDATION
    # -----------------------------------------------------
    validate_dynamic_submission(
        submission,
        enforce_standards=False,
    )

    # -----------------------------------------------------
    # FINALIZE
    # -----------------------------------------------------
    submission.workflow_state = WorkflowState.SUBMITTED
    submission.submitted_at = timezone.now()
    submission.submitted_by = user
    submission.save(update_fields=[
        "workflow_state",
        "submitted_at",
        "submitted_by",
    ])

    # -----------------------------------------------------
    # POST-COMMIT INTEGRATION
    # -----------------------------------------------------
    transaction.on_commit(
        lambda: (
            sync_dynamic_submission(submission),
            send_dynamic_submission_approval_record(submission),
        )
    )

    return submission